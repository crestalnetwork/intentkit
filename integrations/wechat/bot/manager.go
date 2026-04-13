package bot

import (
	"context"
	"log/slog"
	"os"
	"sync"
	"time"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/types"
	"github.com/crestalnetwork/intentkit/integrations/wechat/api"
	"github.com/crestalnetwork/intentkit/integrations/wechat/config"
	"github.com/crestalnetwork/intentkit/integrations/wechat/ilink"
	"github.com/crestalnetwork/intentkit/integrations/wechat/store"
	"gorm.io/gorm"
)

type botEntry struct {
	client           *ilink.Client
	typingTicket     string
	lastContextToken string // cached to avoid DB write on every message
}

// Manager manages WeChat bot lifecycles for team channels.
type Manager struct {
	db          *gorm.DB
	cfg         *config.Config
	apiClient   *api.Client
	bots        map[string]*botEntry
	cancelFuncs map[string]context.CancelFunc
	tokenHashes map[string]string
	mu          sync.RWMutex
	stopCh      chan struct{}
}

func NewManager(db *gorm.DB, cfg *config.Config, apiClient *api.Client) *Manager {
	return &Manager{
		db:          db,
		cfg:         cfg,
		apiClient:   apiClient,
		bots:        make(map[string]*botEntry),
		cancelFuncs: make(map[string]context.CancelFunc),
		tokenHashes: make(map[string]string),
		stopCh:      make(chan struct{}),
	}
}

func (m *Manager) Start() {
	ticker := time.NewTicker(time.Duration(m.cfg.WxNewChannelPollInterval) * time.Second)
	defer ticker.Stop()

	// Initial sync
	m.syncBots()

	for {
		select {
		case <-ticker.C:
			m.syncBots()
		case <-m.stopCh:
			return
		}
	}
}

const heartbeatFile = "/tmp/healthy"

func writeHeartbeat() {
	if err := os.WriteFile(heartbeatFile, []byte("ok"), 0644); err != nil {
		slog.Error("Failed to write heartbeat file", "error", err)
	}
}

func (m *Manager) Stop() {
	close(m.stopCh)
	m.mu.Lock()
	defer m.mu.Unlock()

	for id, cancel := range m.cancelFuncs {
		cancel()
		slog.Info("Stopped wechat bot", "id", id)
	}
}

// syncBots queries team_channels for enabled WeChat channels and manages their bots.
// Only queries team_channels — WeChat does NOT support individual agents.
func (m *Manager) syncBots() {
	var teamChannels []store.TeamChannel
	if err := m.db.Where("channel_type = ? AND enabled = ?", "wechat", true).Find(&teamChannels).Error; err != nil {
		slog.Error("Failed to fetch wechat team channels", "error", err)
		return
	}

	activeIDs := make(map[string]bool)

	for _, tc := range teamChannels {
		key := "team:" + tc.TeamID
		activeIDs[key] = true
		m.ensureTeamBotRunning(&tc)
	}

	// Stop bots for disabled/removed channels
	m.mu.Lock()
	for id, cancel := range m.cancelFuncs {
		if !activeIDs[id] {
			cancel()
			delete(m.bots, id)
			delete(m.cancelFuncs, id)
			delete(m.tokenHashes, id)
			slog.Info("Stopped and removed wechat bot", "id", id)
		}
	}
	m.mu.Unlock()

	writeHeartbeat()
}

func (m *Manager) ensureTeamBotRunning(tc *store.TeamChannel) {
	token := getStringFromConfig(tc.Config, "bot_token")
	baseURL := getStringFromConfig(tc.Config, "baseurl")
	botID := getStringFromConfig(tc.Config, "ilink_bot_id")
	if token == "" || baseURL == "" {
		slog.Warn("WeChat team channel missing bot_token or baseurl", "team_id", tc.TeamID)
		return
	}

	key := "team:" + tc.TeamID

	m.mu.RLock()
	_, exists := m.bots[key]
	oldToken := m.tokenHashes[key]
	m.mu.RUnlock()

	if exists && oldToken == token {
		return
	}

	if exists && oldToken != token {
		slog.Info("WeChat bot token changed, restarting", "team_id", tc.TeamID)
		m.mu.Lock()
		if cancel, ok := m.cancelFuncs[key]; ok {
			cancel()
		}
		delete(m.bots, key)
		delete(m.cancelFuncs, key)
		delete(m.tokenHashes, key)
		m.mu.Unlock()
	}

	client := ilink.NewClient(baseURL, token, botID)

	// GetConfig requires a user_id and context_token from a real message,
	// which we don't have at startup. typing_ticket will be fetched on first message.
	typingTicket := ""

	// Save runtime data
	m.updateTeamChannelData(tc.TeamID, typingTicket)

	// Start long-poll loop
	ctx, cancel := context.WithCancel(context.Background())

	entry := &botEntry{
		client:       client,
		typingTicket: typingTicket,
	}

	go m.pollLoop(ctx, entry, tc.TeamID)

	m.mu.Lock()
	m.bots[key] = entry
	m.cancelFuncs[key] = cancel
	m.tokenHashes[key] = token
	m.mu.Unlock()

	slog.Info("Started wechat bot for team channel", "team_id", tc.TeamID)
}

func (m *Manager) pollLoop(ctx context.Context, entry *botEntry, teamID string) {
	backoff := 2 * time.Second
	const maxBackoff = 60 * time.Second
	consecutiveErrors := 0

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		msgs, err := entry.client.GetUpdates(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return // context cancelled
			}
			consecutiveErrors++
			slog.Error("GetUpdates failed",
				"team_id", teamID,
				"error", err,
				"consecutive_errors", consecutiveErrors,
				"next_backoff", backoff.String(),
			)
			time.Sleep(backoff)
			backoff = min(backoff*2, maxBackoff)
			continue
		}

		if consecutiveErrors > 0 {
			slog.Info("GetUpdates recovered after errors",
				"team_id", teamID,
				"previous_consecutive_errors", consecutiveErrors,
			)
		}
		// Reset backoff on success
		consecutiveErrors = 0
		backoff = 2 * time.Second

		if len(msgs) > 0 {
			slog.Debug("GetUpdates received messages", "team_id", teamID, "msg_count", len(msgs))
		}

		for _, msg := range msgs {
			m.handleTeamMessage(entry, msg, teamID)
		}
	}
}

func (m *Manager) updateTeamChannelData(teamID, typingTicket string) {
	if typingTicket == "" {
		return
	}
	// Use JSONB merge to update only the typing_ticket key without overwriting other data (e.g. context_token)
	err := m.db.Exec(
		`UPDATE team_channel_data SET data = COALESCE(data, '{}'::jsonb) || jsonb_build_object('typing_ticket', to_jsonb(?::text)) WHERE team_id = ? AND channel_type = ?`,
		typingTicket, teamID, "wechat",
	).Error
	if err != nil {
		slog.Error("Failed to update typing_ticket", "team_id", teamID, "error", err)
	}
}

func (m *Manager) updateContextToken(teamID, contextToken string) {
	if contextToken == "" {
		return
	}
	// Update context_token in team_channel_data JSONB
	// Use raw SQL to update only the context_token key without overwriting other data
	err := m.db.Exec(
		`UPDATE team_channel_data SET data = COALESCE(data, '{}'::jsonb) || jsonb_build_object('context_token', to_jsonb(?::text)) WHERE team_id = ? AND channel_type = ?`,
		contextToken, teamID, "wechat",
	).Error
	if err != nil {
		slog.Error("Failed to update context_token", "team_id", teamID, "error", err)
	}
}

func getStringFromConfig(config map[string]interface{}, key string) string {
	if val, ok := config[key]; ok {
		if s, ok := val.(string); ok {
			return s
		}
	}
	return ""
}

func (m *Manager) handleTeamMessage(entry *botEntry, msg ilink.WeixinMessage, teamID string) {
	// Extract text from item_list
	text := ""
	for _, item := range msg.ItemList {
		if item.Type == 1 && item.TextItem != nil {
			text = item.TextItem.Text
			break
		}
	}

	if text == "" || msg.FromUserID == "" {
		return
	}

	slog.Info("Received wechat message", "team_id", teamID, "from", msg.FromUserID)

	// Store latest context_token for proactive messaging (skip DB write if unchanged)
	if msg.ContextToken != entry.lastContextToken {
		entry.lastContextToken = msg.ContextToken
		m.updateContextToken(teamID, msg.ContextToken)
	}

	// Intercept /default command — set this chat as the push channel
	if text == "/default" {
		if err := m.apiClient.SetPushChannel(context.Background(), teamID, "wechat", msg.FromUserID, false); err != nil {
			slog.Error("Failed to set push channel", "team_id", teamID, "error", err)
			_ = entry.client.SendMessage(context.Background(), msg.FromUserID, msg.ContextToken, "Failed to set push channel.")
		} else {
			_ = entry.client.SendMessage(context.Background(), msg.FromUserID, msg.ContextToken, "This chat is now the default push channel.")
		}
		return
	}

	// Lazy-fetch typing_ticket on first message (requires user_id + context_token)
	if entry.typingTicket == "" {
		cfgResp, err := entry.client.GetConfig(context.Background(), msg.FromUserID, msg.ContextToken)
		if err != nil {
			slog.Warn("Failed to get typing_ticket", "team_id", teamID, "error", err)
		} else {
			entry.typingTicket = cfgResp.TypingTicket
			m.updateTeamChannelData(teamID, entry.typingTicket)
		}
	}

	// Start periodic typing indicator while waiting for API response
	typingCtx, typingCancel := context.WithCancel(context.Background())
	if entry.typingTicket != "" {
		_ = entry.client.SendTyping(typingCtx, msg.FromUserID, entry.typingTicket)
		go func() {
			ticker := time.NewTicker(10 * time.Second)
			defer ticker.Stop()
			for {
				select {
				case <-typingCtx.Done():
					return
				case <-ticker.C:
					_ = entry.client.SendTyping(typingCtx, msg.FromUserID, entry.typingTicket)
				}
			}
		}()
	}

	// Call Core API via SSE streaming
	payload := map[string]interface{}{
		"team_id":         teamID,
		"channel_type":    "wechat",
		"channel_user_id": msg.FromUserID,
		"chat_id":         msg.FromUserID,
		"message":         text,
	}

	sender := NewWechatSender(entry.client, msg.FromUserID, msg.ContextToken)
	err := m.apiClient.StreamTeamLead(context.Background(), payload, func(chatMsg types.ChatMessage) error {
		shared.DispatchMessage(context.Background(), chatMsg, sender)
		return nil
	})
	typingCancel() // stop typing indicator

	if err != nil {
		slog.Error("Failed to stream wechat team lead", "error", err)
		if sendErr := entry.client.SendMessage(context.Background(), msg.FromUserID, msg.ContextToken, "Sorry, I encountered an error processing your request."); sendErr != nil {
			slog.Error("Failed to send error reply", "team_id", teamID, "error", sendErr)
		}
		return
	}
}
