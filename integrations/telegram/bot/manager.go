package bot

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"sync"
	"time"

	"github.com/crestalnetwork/intentkit/integrations/telegram/api"
	"github.com/crestalnetwork/intentkit/integrations/telegram/config"
	"github.com/crestalnetwork/intentkit/integrations/telegram/store"
	"github.com/mymmrac/telego"
	tu "github.com/mymmrac/telego/telegoutil"
	"gorm.io/gorm"
)

type Manager struct {
	db          *gorm.DB
	cfg         *config.Config
	apiClient   *api.Client
	bots        map[string]*telego.Bot
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
		bots:        make(map[string]*telego.Bot),
		cancelFuncs: make(map[string]context.CancelFunc),
		tokenHashes: make(map[string]string),
		stopCh:      make(chan struct{}),
	}
}

func (m *Manager) Start() {
	ticker := time.NewTicker(time.Duration(m.cfg.TgNewAgentPollInterval) * time.Second)
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

// writeHeartbeat writes a heartbeat file for Docker healthcheck.
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
		slog.Info("Stopped bot", "agent_id", id)
	}
}

func (m *Manager) syncBots() {
	var agents []store.Agent
	if err := m.db.Where("telegram_entrypoint_enabled = ?", true).Find(&agents).Error; err != nil {
		slog.Error("Failed to fetch agents", "error", err)
		return
	}

	activeIDs := make(map[string]bool)

	for _, agent := range agents {
		activeIDs[agent.ID] = true
		m.ensureBotRunning(&agent)
	}

	// Sync team channel bots
	var teamChannels []store.TeamChannel
	if err := m.db.Where("channel_type = ? AND enabled = ?", "telegram", true).Find(&teamChannels).Error; err != nil {
		slog.Error("Failed to fetch team channels", "error", err)
	} else {
		for _, tc := range teamChannels {
			key := "team:" + tc.TeamID
			activeIDs[key] = true
			m.ensureTeamBotRunning(&tc)
		}
	}

	// Stop bots for disabled/removed agents and team channels
	m.mu.Lock()
	for id, cancel := range m.cancelFuncs {
		if !activeIDs[id] {
			cancel()
			delete(m.bots, id)
			delete(m.cancelFuncs, id)
			delete(m.tokenHashes, id)
			slog.Info("Stopped and removed bot", "id", id)
		}
	}
	m.mu.Unlock()
	// Write heartbeat after successful sync
	writeHeartbeat()
}

func (m *Manager) ensureBotRunning(agent *store.Agent) {
	token := getTokenFromConfig(agent.TelegramConfig)
	if token == "" {
		slog.Warn("Agent has enabled telegram but no valid token", "agent_id", agent.ID)
		return
	}

	m.mu.RLock()
	_, exists := m.bots[agent.ID]
	oldToken := m.tokenHashes[agent.ID]
	m.mu.RUnlock()

	if exists && oldToken == token {
		return
	}

	if exists && oldToken != token {
		slog.Info("Bot token changed, restarting bot", "agent_id", agent.ID)
		m.mu.Lock()
		if cancel, ok := m.cancelFuncs[agent.ID]; ok {
			cancel()
		}
		delete(m.bots, agent.ID)
		delete(m.cancelFuncs, agent.ID)
		delete(m.tokenHashes, agent.ID)
		m.mu.Unlock()
	}

	bot, err := telego.NewBot(token, telego.WithDefaultDebugLogger())
	if err != nil {
		slog.Error("Failed to create bot", "agent_id", agent.ID, "error", err)
		return
	}

	// Update AgentData on first run
	if err := m.updateAgentData(agent.ID, bot); err != nil {
		slog.Error("Failed to update agent data", "agent_id", agent.ID, "error", err)
	}

	// Start Long Polling
	ctx, cancel := context.WithCancel(context.Background())
	updates, err := bot.UpdatesViaLongPolling(ctx, nil)
	if err != nil {
		slog.Error("Failed to get updates channel", "agent_id", agent.ID, "error", err)
		cancel()
		return
	}

	go func() {
		for update := range updates {
			if update.Message != nil {
				m.handleMessage(bot, *update.Message, agent.ID)
			}
		}
	}()

	m.mu.Lock()
	m.bots[agent.ID] = bot
	m.cancelFuncs[agent.ID] = cancel
	m.tokenHashes[agent.ID] = token
	m.mu.Unlock()

	slog.Info("Started bot for agent", "agent_id", agent.ID)
}

func (m *Manager) updateAgentData(agentID string, bot *telego.Bot) error {
	me, err := bot.GetMe(context.Background())
	if err != nil {
		return err
	}

	username := me.Username
	fullName := me.FirstName + " " + me.LastName
	if me.LastName == "" {
		fullName = me.FirstName
	}

	idStr := fmt.Sprintf("%d", me.ID)

	// Upsert AgentData
	// We use FirstOrCreate to ensure the record exists, then Update to set values
	var agentData store.AgentData
	if err := m.db.FirstOrCreate(&agentData, store.AgentData{ID: agentID}).Error; err != nil {
		return err
	}

	return m.db.Model(&store.AgentData{}).Where("id = ?", agentID).Updates(map[string]interface{}{
		"telegram_id":       idStr,
		"telegram_username": username,
		"telegram_name":     fullName,
	}).Error
}

func (m *Manager) ensureTeamBotRunning(tc *store.TeamChannel) {
	token := getTokenFromConfig(tc.Config)
	if token == "" {
		slog.Warn("Team channel has no valid token", "team_id", tc.TeamID)
		return
	}

	key := "team:" + tc.TeamID

	m.mu.RLock()
	_, exists := m.bots[key]
	oldToken := m.tokenHashes[key]
	// Check if this token is already in use by any other bot (agent or team)
	tokenInUse := false
	for id, t := range m.tokenHashes {
		if t == token && id != key {
			tokenInUse = true
			break
		}
	}
	m.mu.RUnlock()

	if tokenInUse {
		slog.Warn("Token already in use by another bot, skipping team channel", "team_id", tc.TeamID)
		return
	}

	if exists && oldToken == token {
		return
	}

	if exists && oldToken != token {
		slog.Info("Team channel bot token changed, restarting", "team_id", tc.TeamID)
		m.mu.Lock()
		if cancel, ok := m.cancelFuncs[key]; ok {
			cancel()
		}
		delete(m.bots, key)
		delete(m.cancelFuncs, key)
		delete(m.tokenHashes, key)
		m.mu.Unlock()
	}

	bot, err := telego.NewBot(token, telego.WithDefaultDebugLogger())
	if err != nil {
		slog.Error("Failed to create team channel bot", "team_id", tc.TeamID, "error", err)
		return
	}

	if err := m.updateTeamChannelData(tc.TeamID, bot); err != nil {
		slog.Error("Failed to update team channel data", "team_id", tc.TeamID, "error", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	updates, err := bot.UpdatesViaLongPolling(ctx, nil)
	if err != nil {
		slog.Error("Failed to get updates for team channel", "team_id", tc.TeamID, "error", err)
		cancel()
		return
	}

	go func() {
		for update := range updates {
			if update.Message != nil {
				m.handleTeamMessage(bot, *update.Message, tc.TeamID)
			}
		}
	}()

	m.mu.Lock()
	m.bots[key] = bot
	m.cancelFuncs[key] = cancel
	m.tokenHashes[key] = token
	m.mu.Unlock()

	slog.Info("Started bot for team channel", "team_id", tc.TeamID)
}

func (m *Manager) updateTeamChannelData(teamID string, bot *telego.Bot) error {
	me, err := bot.GetMe(context.Background())
	if err != nil {
		return err
	}

	fullName := me.FirstName + " " + me.LastName
	if me.LastName == "" {
		fullName = me.FirstName
	}

	jsonData := map[string]interface{}{
		"bot_id":       fmt.Sprintf("%d", me.ID),
		"bot_username": me.Username,
		"bot_name":     fullName,
	}

	var data store.TeamChannelData
	result := m.db.Where("team_id = ? AND channel_type = ?", teamID, "telegram").First(&data)
	if result.Error != nil {
		data = store.TeamChannelData{
			TeamID:      teamID,
			ChannelType: "telegram",
			Data:        jsonData,
		}
		return m.db.Create(&data).Error
	}

	return m.db.Model(&store.TeamChannelData{}).
		Where("team_id = ? AND channel_type = ?", teamID, "telegram").
		Update("data", jsonData).Error
}

func (m *Manager) handleTeamMessage(bot *telego.Bot, message telego.Message, teamID string) {
	if message.Text == "" || message.From == nil {
		return
	}

	slog.Info("Received team message", "team_id", teamID, "chat_id", message.Chat.ID)

	_ = bot.SendChatAction(context.Background(), tu.ChatAction(tu.ID(message.Chat.ID), telego.ChatActionTyping))

	telegramID := fmt.Sprintf("%d", message.From.ID)

	payload := map[string]interface{}{
		"team_id":     teamID,
		"telegram_id": telegramID,
		"chat_id":     fmt.Sprintf("%d", message.Chat.ID),
		"message":     message.Text,
	}

	resp, err := m.apiClient.ExecuteTeamLead(payload)
	if err != nil {
		slog.Error("Failed to execute team lead", "error", err)
		_, _ = bot.SendMessage(context.Background(), tu.Message(tu.ID(message.Chat.ID), "Sorry, I encountered an error processing your request."))
		return
	}

	for _, chatMsg := range resp {
		if chatMsg.IsAgentResponse() {
			_, _ = bot.SendMessage(context.Background(), tu.Message(tu.ID(message.Chat.ID), chatMsg.Message))
		}
	}
}

func getTokenFromConfig(config map[string]interface{}) string {
	if val, ok := config["token"]; ok {
		if token, ok := val.(string); ok {
			return token
		}
	}
	return ""
}
