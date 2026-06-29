package bot

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"time"

	lark "github.com/larksuite/oapi-sdk-go/v3"
	"github.com/larksuite/oapi-sdk-go/v3/event/dispatcher"
	callback "github.com/larksuite/oapi-sdk-go/v3/event/dispatcher/callback"
	larkim "github.com/larksuite/oapi-sdk-go/v3/service/im/v1"
	"gorm.io/gorm"

	"github.com/crestalnetwork/intentkit/integrations/lark/api"
	"github.com/crestalnetwork/intentkit/integrations/lark/config"
	"github.com/crestalnetwork/intentkit/integrations/lark/larkclient"
	"github.com/crestalnetwork/intentkit/integrations/lark/store"
	"github.com/crestalnetwork/intentkit/integrations/shared"
)

// Manager runs the public HTTP webhook that receives Lark event-subscription
// callbacks for the single ISV (store) app. Each tenant authorizes the app for
// its own enterprise via OAuth (the install URL is built by the Python API,
// which redirects to the SPA and then drives an authenticated completion). The
// SPA-confirmed completion calls this service's internal /lark/exchange to swap
// the code for a {tenant_key} stored on the team's lark channel row, and
// /lark/push to send proactive messages — both gated by the shared secret. One
// marketplace SDK client serves every tenant — the dispatcher resolves the
// owning team from the event's tenant_key and replies with that tenant's access
// token (the SDK auto-manages the token chain from the app_ticket it captures,
// and decrypts/verifies inbound events).
type Manager struct {
	db         *gorm.DB
	cfg        *config.Config
	apiClient  *api.Client
	storage    *shared.S3Storage
	sharedLark *lark.Client
	dispatcher *dispatcher.EventDispatcher
	server     *http.Server
}

func NewManager(db *gorm.DB, cfg *config.Config, apiClient *api.Client, storage *shared.S3Storage) *Manager {
	m := &Manager{
		db:         db,
		cfg:        cfg,
		apiClient:  apiClient,
		storage:    storage,
		sharedLark: larkclient.NewMarketplaceClient(cfg.LarkAppID, cfg.LarkAppSecret, cfg.LarkDomain, cfg.Debug),
	}
	// NewEventDispatcher decrypts + verifies inbound events and auto-captures the
	// app_ticket; we only wire the message + card-action handlers, each resolving
	// the owning team from the event's tenant_key.
	m.dispatcher = dispatcher.NewEventDispatcher(cfg.LarkVerificationToken, cfg.LarkEncryptKey).
		OnP2MessageReceiveV1(func(_ context.Context, event *larkim.P2MessageReceiveV1) error {
			teamID, client, ok := m.resolveTenant(event.TenantKey())
			if !ok {
				return nil
			}
			go m.handleMessageEvent(client, teamID, event)
			return nil
		}).
		OnP2CardActionTrigger(func(_ context.Context, event *callback.CardActionTriggerEvent) (*callback.CardActionTriggerResponse, error) {
			teamID, client, ok := m.resolveTenant(event.TenantKey())
			if !ok {
				return nil, nil
			}
			return m.handleCardAction(client, teamID, event), nil
		})
	return m
}

func (m *Manager) Start() {
	mux := http.NewServeMux()
	mux.HandleFunc("/lark/events", m.handleEventsRequest)
	// Internal-only (secret-gated) reverse calls from the Python API.
	mux.HandleFunc("/lark/exchange", m.handleExchange)
	mux.HandleFunc("/lark/push", m.handlePush)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeHeartbeat()
		w.WriteHeader(http.StatusOK)
	})

	m.server = &http.Server{
		Addr:              m.cfg.ListenAddr,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
	}
	writeHeartbeat()
	slog.Info("Lark webhook listening", "addr", m.cfg.ListenAddr)
	if err := m.server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		slog.Error("Lark webhook server failed", "error", err)
	}
}

func (m *Manager) Stop() {
	if m.server == nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = m.server.Shutdown(ctx)
	slog.Info("Stopped lark webhook server")
}

const heartbeatFile = "/tmp/healthy"

func writeHeartbeat() {
	if err := os.WriteFile(heartbeatFile, []byte("ok"), 0644); err != nil {
		slog.Error("Failed to write heartbeat file", "error", err)
	}
}

// resolveTenant finds the IntentKit team + a tenant-bound client for a Lark
// tenant_key. Returns ok=false if no enabled team has authorized that tenant.
func (m *Manager) resolveTenant(tenantKey string) (string, *larkclient.Client, bool) {
	if tenantKey == "" {
		return "", nil, false
	}
	var tc store.TeamChannel
	err := m.db.Where("channel_type = ? AND enabled = ? AND config->>'tenant_key' = ?",
		channelType, true, tenantKey).First(&tc).Error
	if err != nil {
		return "", nil, false
	}
	return tc.TeamID, larkclient.ForTenant(m.sharedLark, tenantKey), true
}
