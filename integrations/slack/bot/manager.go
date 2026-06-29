package bot

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/slack-go/slack"
	"gorm.io/gorm"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/slack/api"
	"github.com/crestalnetwork/intentkit/integrations/slack/config"
	"github.com/crestalnetwork/intentkit/integrations/slack/slackclient"
	"github.com/crestalnetwork/intentkit/integrations/slack/store"
)

// Manager runs the public HTTP webhook that receives Slack Events API and
// interaction callbacks for the single distributed Slack app. Each team installs
// the app into its own workspace via OAuth (handled by the Python API), which
// stores {workspace_id, bot_token} on the team's slack channel row. The manager
// resolves the owning team + that workspace's bot token from the event's
// workspace id, so one webhook serves every team without per-team connections.
type Manager struct {
	db        *gorm.DB
	cfg       *config.Config
	apiClient *api.Client
	storage   *shared.S3Storage
	server    *http.Server
}

func NewManager(db *gorm.DB, cfg *config.Config, apiClient *api.Client, storage *shared.S3Storage) *Manager {
	return &Manager{db: db, cfg: cfg, apiClient: apiClient, storage: storage}
}

func (m *Manager) Start() {
	mux := http.NewServeMux()
	mux.HandleFunc("/slack/events", m.handleEventsRequest)
	mux.HandleFunc("/slack/interactions", m.handleInteractionRequest)
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
	slog.Info("Slack webhook listening", "addr", m.cfg.ListenAddr)
	if err := m.server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		slog.Error("Slack webhook server failed", "error", err)
	}
}

func (m *Manager) Stop() {
	if m.server == nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = m.server.Shutdown(ctx)
	slog.Info("Stopped slack webhook server")
}

const heartbeatFile = "/tmp/healthy"

func writeHeartbeat() {
	if err := os.WriteFile(heartbeatFile, []byte("ok"), 0644); err != nil {
		slog.Error("Failed to write heartbeat file", "error", err)
	}
}

// resolveWorkspace finds the IntentKit team + a Web API client for a Slack
// workspace id (the event's team_id). Returns ok=false if no enabled team has
// installed the app for that workspace.
func (m *Manager) resolveWorkspace(workspaceID string) (string, *slackclient.Client, bool) {
	if workspaceID == "" {
		return "", nil, false
	}
	var tc store.TeamChannel
	err := m.db.Where("channel_type = ? AND enabled = ? AND config->>'workspace_id' = ?",
		channelType, true, workspaceID).First(&tc).Error
	if err != nil {
		return "", nil, false
	}
	botToken := getStringFromConfig(tc.Config, "bot_token")
	if botToken == "" {
		return "", nil, false
	}
	api := slack.New(botToken, slack.OptionDebug(m.cfg.Debug))
	return tc.TeamID, slackclient.NewFromAPI(api), true
}

func getStringFromConfig(config map[string]interface{}, key string) string {
	if val, ok := config[key]; ok {
		if s, ok := val.(string); ok {
			return s
		}
	}
	return ""
}
