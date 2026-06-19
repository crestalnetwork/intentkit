package bot

import (
	"context"
	"log/slog"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"gorm.io/gorm"

	larkcore "github.com/larksuite/oapi-sdk-go/v3/core"
	"github.com/larksuite/oapi-sdk-go/v3/event/dispatcher"
	callback "github.com/larksuite/oapi-sdk-go/v3/event/dispatcher/callback"
	larkim "github.com/larksuite/oapi-sdk-go/v3/service/im/v1"
	larkws "github.com/larksuite/oapi-sdk-go/v3/ws"

	"github.com/crestalnetwork/intentkit/integrations/lark/api"
	"github.com/crestalnetwork/intentkit/integrations/lark/config"
	"github.com/crestalnetwork/intentkit/integrations/lark/larkclient"
	"github.com/crestalnetwork/intentkit/integrations/lark/store"
	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/shared/alert"
	"github.com/crestalnetwork/intentkit/integrations/shared/outage"
)

const (
	initialBackoff = 2 * time.Second
	maxBackoff     = 4 * time.Minute
)

// botEntry holds the live REST client for one team's lark bot. The WebSocket
// client itself lives in the per-team runClient goroutine (rebuilt on each
// reconnect attempt), so it isn't stored here.
type botEntry struct {
	client *larkclient.Client
}

// Manager maintains one Lark WebSocket long connection per enabled team
// channel. It mirrors the wechat/telegram managers (DB-driven sync on a
// ticker) but, because Lark connects outbound over a WebSocket, there is no
// poll loop — the SDK pushes events to per-team dispatchers.
type Manager struct {
	db        *gorm.DB
	cfg       *config.Config
	apiClient *api.Client
	storage   *shared.S3Storage

	bots        map[string]*botEntry
	cancelFuncs map[string]context.CancelFunc
	credHashes  map[string]string
	outage      *outage.Tracker
	mu          sync.RWMutex
	stopCh      chan struct{}
}

func NewManager(db *gorm.DB, cfg *config.Config, apiClient *api.Client, storage *shared.S3Storage) *Manager {
	return &Manager{
		db:          db,
		cfg:         cfg,
		apiClient:   apiClient,
		storage:     storage,
		bots:        make(map[string]*botEntry),
		cancelFuncs: make(map[string]context.CancelFunc),
		credHashes:  make(map[string]string),
		outage:      outage.NewTracker(),
		stopCh:      make(chan struct{}),
	}
}

func (m *Manager) Start() {
	ticker := time.NewTicker(time.Duration(m.cfg.LkNewChannelPollInterval) * time.Second)
	defer ticker.Stop()

	m.syncBots()

	for {
		select {
		case <-ticker.C:
			// Outage deadlines (gather window, re-alert interval) are
			// event-driven; this tick bounds alert latency when reconnect
			// backoff would otherwise delay the next NoteFailure.
			m.emitOutageAlertIfDue()
			m.syncBots()
		case <-m.stopCh:
			return
		}
	}
}

func (m *Manager) Stop() {
	close(m.stopCh)
	m.mu.Lock()
	defer m.mu.Unlock()
	for id, cancel := range m.cancelFuncs {
		cancel()
		slog.Info("Stopped lark bot", "id", id)
	}
}

const heartbeatFile = "/tmp/healthy"

func writeHeartbeat() {
	if err := os.WriteFile(heartbeatFile, []byte("ok"), 0644); err != nil {
		slog.Error("Failed to write heartbeat file", "error", err)
	}
}

func botKey(teamID string) string { return "team:" + teamID }

// emitOutageAlertIfDue sends the aggregated WebSocket outage alert when one is
// due. This Error log is the only connection failure that reaches the alert
// channel; per-team failures log at Warn.
func (m *Manager) emitOutageAlertIfDue() {
	if sum := m.outage.Flush(); sum != nil {
		slog.Error("Lark websocket outage",
			"affected_teams", strings.Join(sum.Affected, ","),
			"team_count", len(sum.Affected),
			"duration", sum.Duration.Round(time.Second).String(),
			"sample_error", sum.LastErr,
		)
	}
}

// syncBots queries team_channels for enabled Lark channels and reconciles the
// running bots. Only queries team_channels — Lark does NOT support individual
// agents.
func (m *Manager) syncBots() {
	var teamChannels []store.TeamChannel
	if err := m.db.Where("channel_type = ? AND enabled = ?", channelType, true).Find(&teamChannels).Error; err != nil {
		slog.Error("Failed to fetch lark team channels", "error", err)
		return
	}

	activeIDs := make(map[string]bool)
	for i := range teamChannels {
		tc := &teamChannels[i]
		activeIDs[botKey(tc.TeamID)] = true
		m.ensureTeamBotRunning(tc)
	}

	// Stop bots for disabled/removed channels.
	m.mu.Lock()
	for id, cancel := range m.cancelFuncs {
		if !activeIDs[id] {
			cancel()
			delete(m.bots, id)
			delete(m.cancelFuncs, id)
			delete(m.credHashes, id)
			slog.Info("Stopped and removed lark bot", "id", id)
		}
	}
	m.mu.Unlock()

	writeHeartbeat()
}

// credHash fingerprints the credentials that define a connection; a change
// triggers a restart of the team's WebSocket client.
func credHash(appID, appSecret, domain string) string {
	return appID + "|" + appSecret + "|" + domain
}

func (m *Manager) ensureTeamBotRunning(tc *store.TeamChannel) {
	appID := getStringFromConfig(tc.Config, "app_id")
	appSecret := getStringFromConfig(tc.Config, "app_secret")
	domain := getStringFromConfig(tc.Config, "domain")
	if appID == "" || appSecret == "" {
		slog.Warn("Lark team channel missing app_id or app_secret", "team_id", tc.TeamID)
		return
	}

	key := botKey(tc.TeamID)
	hash := credHash(appID, appSecret, domain)

	m.mu.RLock()
	_, exists := m.bots[key]
	oldHash := m.credHashes[key]
	m.mu.RUnlock()

	if exists && oldHash == hash {
		return
	}

	if exists && oldHash != hash {
		slog.Info("Lark bot credentials changed, restarting", "team_id", tc.TeamID)
		m.mu.Lock()
		if cancel, ok := m.cancelFuncs[key]; ok {
			cancel()
		}
		delete(m.bots, key)
		delete(m.cancelFuncs, key)
		delete(m.credHashes, key)
		m.mu.Unlock()
	}

	entry := &botEntry{client: larkclient.NewClient(appID, appSecret, domain, m.cfg.Debug)}
	baseURL := entry.client.BaseURL()

	ctx, cancel := context.WithCancel(context.Background())
	go m.runClient(ctx, entry, tc.TeamID, appID, appSecret, baseURL)

	m.mu.Lock()
	m.bots[key] = entry
	m.cancelFuncs[key] = cancel
	m.credHashes[key] = hash
	m.mu.Unlock()

	slog.Info("Started lark bot for team channel", "team_id", tc.TeamID, "domain", baseURL)
}

// runClient maintains the team's WebSocket long connection. The SDK reconnects
// internally (WithAutoReconnect); this loop only re-establishes after a fatal
// return (e.g. bad credentials) with bounded backoff, and tracks outages.
func (m *Manager) runClient(ctx context.Context, entry *botEntry, teamID, appID, appSecret, baseURL string) {
	defer m.outage.Forget(teamID)

	backoff := initialBackoff
	consecutiveErrors := 0

	for {
		if ctx.Err() != nil {
			return
		}

		var ready atomic.Bool
		wsClient := larkws.NewClient(appID, appSecret,
			larkws.WithEventHandler(m.buildDispatcher(entry, teamID)),
			larkws.WithDomain(baseURL),
			larkws.WithLogLevel(m.wsLogLevel()),
			larkws.WithAutoReconnect(true),
			larkws.WithOnReady(func() {
				ready.Store(true)
				slog.Info("lark: websocket ready", "team_id", teamID)
				if sum := m.outage.NoteSuccess(teamID); sum != nil {
					slog.Info("Lark websocket outage recovered",
						"affected_teams", strings.Join(sum.Affected, ","),
						"duration", sum.Duration.Round(time.Second).String(),
						alert.NotifyKey, true,
					)
				}
			}),
		)

		err := wsClient.Start(ctx) // blocks until ctx cancel or fatal error
		if ctx.Err() != nil {
			return
		}

		// A healthy session that later dropped resets the backoff ladder.
		if ready.Load() {
			consecutiveErrors = 0
			backoff = initialBackoff
		}
		consecutiveErrors++
		slog.Warn("lark: websocket connection ended",
			"team_id", teamID,
			"error", err,
			"consecutive_errors", consecutiveErrors,
			"next_backoff", backoff.String(),
		)
		m.outage.NoteFailure(teamID, consecutiveErrors, errString(err))
		m.emitOutageAlertIfDue()

		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
		}
		backoff = min(backoff*2, maxBackoff)
	}
}

// buildDispatcher wires the inbound message and card-action handlers for one
// team. Message handling runs on its own goroutine so a slow lead-agent stream
// never blocks the WebSocket read loop; card actions return synchronously so
// the clicking user gets an immediate toast.
func (m *Manager) buildDispatcher(entry *botEntry, teamID string) *dispatcher.EventDispatcher {
	return dispatcher.NewEventDispatcher("", "").
		OnP2MessageReceiveV1(func(_ context.Context, event *larkim.P2MessageReceiveV1) error {
			go m.handleMessageEvent(entry.client, teamID, event)
			return nil
		}).
		OnP2CardActionTrigger(func(_ context.Context, event *callback.CardActionTriggerEvent) (*callback.CardActionTriggerResponse, error) {
			return m.handleCardAction(entry.client, teamID, event), nil
		})
}

func (m *Manager) wsLogLevel() larkcore.LogLevel {
	if m.cfg.Debug {
		return larkcore.LogLevelDebug
	}
	return larkcore.LogLevelError
}

func getStringFromConfig(config map[string]interface{}, key string) string {
	if val, ok := config[key]; ok {
		if s, ok := val.(string); ok {
			return s
		}
	}
	return ""
}

func errString(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}
