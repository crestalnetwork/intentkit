package bot

import (
	"context"
	"fmt"
	"log/slog"
	"math/rand"
	"os"
	"sync"
	"time"

	"github.com/crestalnetwork/intentkit/integrations/telegram/api"
	"github.com/crestalnetwork/intentkit/integrations/telegram/config"
	"github.com/crestalnetwork/intentkit/integrations/telegram/store"
	"github.com/mymmrac/telego"
	"github.com/redis/go-redis/v9"
	"gorm.io/gorm"
)

// whitelistEntry represents a verified chat in memory.
type whitelistEntry struct {
	ChatName   string
	VerifiedAt string
}

type Manager struct {
	db          *gorm.DB
	cfg         *config.Config
	apiClient   *api.Client
	redis       *redis.Client
	bots        map[string]*telego.Bot
	cancelFuncs map[string]context.CancelFunc
	tokenHashes map[string]string
	// In-memory whitelist: key "team:{teamID}" -> map[chatID]whitelistEntry
	whitelists map[string]map[string]whitelistEntry
	// In-memory verification codes: key "team:{teamID}" -> code string
	verifyCodes map[string]string
	// Bot info cache for syncing back to DB
	botInfo map[string]map[string]interface{}
	mu      sync.RWMutex
	stopCh  chan struct{}
}

func NewManager(db *gorm.DB, cfg *config.Config, apiClient *api.Client, redisClient *redis.Client) *Manager {
	return &Manager{
		db:          db,
		cfg:         cfg,
		apiClient:   apiClient,
		redis:       redisClient,
		bots:        make(map[string]*telego.Bot),
		cancelFuncs: make(map[string]context.CancelFunc),
		tokenHashes: make(map[string]string),
		whitelists:  make(map[string]map[string]whitelistEntry),
		verifyCodes: make(map[string]string),
		botInfo:     make(map[string]map[string]interface{}),
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
		// First pass: ensure all bots are running (may write new codes to DB)
		for _, tc := range teamChannels {
			key := "team:" + tc.TeamID
			activeIDs[key] = true
			m.ensureTeamBotRunning(&tc)
		}

		// Second pass: batch-load fresh data from DB (after any writes from ensureTeamBotRunning)
		// and sync whitelist into memory (handles removals from frontend)
		var allChannelData []store.TeamChannelData
		if err := m.db.Where("channel_type = ?", "telegram").Find(&allChannelData).Error; err != nil {
			slog.Error("Failed to fetch team channel data", "error", err)
		} else {
			dataByTeam := make(map[string]*store.TeamChannelData, len(allChannelData))
			for i := range allChannelData {
				dataByTeam[allChannelData[i].TeamID] = &allChannelData[i]
			}
			for _, tc := range teamChannels {
				if data, ok := dataByTeam[tc.TeamID]; ok {
					m.syncWhitelistFromData(tc.TeamID, data)
				}
			}
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
			delete(m.whitelists, id)
			delete(m.verifyCodes, id)
			delete(m.botInfo, id)
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
			if update.CallbackQuery != nil {
				m.handleCallbackQuery(bot, *update.CallbackQuery, agent.ID, false)
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
		delete(m.whitelists, key)
		delete(m.verifyCodes, key)
		delete(m.botInfo, key)
		m.mu.Unlock()
	}

	bot, err := telego.NewBot(token, telego.WithDefaultDebugLogger())
	if err != nil {
		slog.Error("Failed to create team channel bot", "team_id", tc.TeamID, "error", err)
		m.updateTeamChannelStatus(tc.TeamID, "error", err.Error())
		return
	}

	if err := m.initTeamChannelData(tc.TeamID, bot); err != nil {
		slog.Error("Failed to init team channel data", "team_id", tc.TeamID, "error", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	updates, err := bot.UpdatesViaLongPolling(ctx, nil)
	if err != nil {
		slog.Error("Failed to get updates for team channel", "team_id", tc.TeamID, "error", err)
		cancel()
		m.updateTeamChannelStatus(tc.TeamID, "error", err.Error())
		return
	}

	go func() {
		for update := range updates {
			if update.Message != nil {
				m.handleTeamMessage(bot, *update.Message, tc.TeamID)
			}
			if update.CallbackQuery != nil {
				m.handleCallbackQuery(bot, *update.CallbackQuery, tc.TeamID, true)
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

// initTeamChannelData loads existing data, sets status to listening,
// generates a verification code, and loads whitelist into memory.
func (m *Manager) initTeamChannelData(teamID string, bot *telego.Bot) error {
	me, err := bot.GetMe(context.Background())
	if err != nil {
		return err
	}

	fullName := me.FirstName + " " + me.LastName
	if me.LastName == "" {
		fullName = me.FirstName
	}

	key := "team:" + teamID

	// Load existing data from DB to preserve whitelist
	var existing store.TeamChannelData
	result := m.db.Where("team_id = ? AND channel_type = ?", teamID, "telegram").First(&existing)

	// Load whitelist from existing data into memory
	var wl map[string]whitelistEntry
	var existingWhitelist []interface{}
	if result.Error == nil && existing.Data != nil {
		wl, existingWhitelist = parseWhitelistFromData(existing.Data)
	}
	if wl == nil {
		wl = make(map[string]whitelistEntry)
	}

	// Generate verification code
	code := generateVerificationCode()

	m.mu.Lock()
	m.whitelists[key] = wl
	m.verifyCodes[key] = code
	m.botInfo[key] = map[string]interface{}{
		"bot_id":       fmt.Sprintf("%d", me.ID),
		"bot_username": me.Username,
		"bot_name":     fullName,
	}
	m.mu.Unlock()

	// Build data to write
	jsonData := map[string]interface{}{
		"bot_id":            fmt.Sprintf("%d", me.ID),
		"bot_username":      me.Username,
		"bot_name":          fullName,
		"status":            "listening",
		"status_message":    nil,
		"verification_code": code,
		"whitelist":         existingWhitelist,
	}

	if result.Error != nil {
		data := store.TeamChannelData{
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

// updateTeamChannelStatus writes an error/status to team_channel_data without touching whitelist.
func (m *Manager) updateTeamChannelStatus(teamID string, status string, message string) {
	var existing store.TeamChannelData
	result := m.db.Where("team_id = ? AND channel_type = ?", teamID, "telegram").First(&existing)

	jsonData := map[string]interface{}{
		"status":         status,
		"status_message": message,
	}

	if result.Error != nil {
		jsonData["whitelist"] = []interface{}{}
		data := store.TeamChannelData{
			TeamID:      teamID,
			ChannelType: "telegram",
			Data:        jsonData,
		}
		if err := m.db.Create(&data).Error; err != nil {
			slog.Error("Failed to create team channel status", "team_id", teamID, "error", err)
		}
		return
	}

	// Merge into existing data
	if existing.Data == nil {
		existing.Data = make(map[string]interface{})
	}
	for k, v := range jsonData {
		existing.Data[k] = v
	}

	if err := m.db.Model(&store.TeamChannelData{}).
		Where("team_id = ? AND channel_type = ?", teamID, "telegram").
		Update("data", existing.Data).Error; err != nil {
		slog.Error("Failed to update team channel status", "team_id", teamID, "error", err)
	}
}

// syncTeamChannelData writes the full in-memory state (bot info + whitelist + code) to DB.
func (m *Manager) syncTeamChannelData(teamID string) {
	key := "team:" + teamID

	m.mu.RLock()
	wl := m.whitelists[key]
	code := m.verifyCodes[key]
	info := m.botInfo[key]
	m.mu.RUnlock()

	// Build whitelist array
	whitelist := make([]map[string]interface{}, 0, len(wl))
	for chatID, entry := range wl {
		whitelist = append(whitelist, map[string]interface{}{
			"chat_id":     chatID,
			"chat_name":   entry.ChatName,
			"verified_at": entry.VerifiedAt,
		})
	}

	jsonData := map[string]interface{}{
		"status":            "listening",
		"status_message":    nil,
		"verification_code": code,
		"whitelist":         whitelist,
	}
	// Merge bot info
	for k, v := range info {
		jsonData[k] = v
	}

	if err := m.db.Model(&store.TeamChannelData{}).
		Where("team_id = ? AND channel_type = ?", teamID, "telegram").
		Update("data", jsonData).Error; err != nil {
		slog.Error("Failed to sync team channel data", "team_id", teamID, "error", err)
	}
}

// syncWhitelistFromData updates the in-memory whitelist from pre-fetched channel data.
// This handles removals made via the frontend/API.
func (m *Manager) syncWhitelistFromData(teamID string, data *store.TeamChannelData) {
	key := "team:" + teamID

	m.mu.RLock()
	_, exists := m.bots[key]
	m.mu.RUnlock()
	if !exists || data == nil || data.Data == nil {
		return
	}

	wl, _ := parseWhitelistFromData(data.Data)
	if wl == nil {
		wl = make(map[string]whitelistEntry)
	}

	// Also sync verification code from DB (in case it was updated externally)
	code, _ := data.Data["verification_code"].(string)

	m.mu.Lock()
	m.whitelists[key] = wl
	if code != "" {
		m.verifyCodes[key] = code
	}
	m.mu.Unlock()
}

// parseWhitelistFromData extracts whitelist entries from a JSONB data map.
// Returns the parsed map and the raw slice (for re-serialization).
func parseWhitelistFromData(data map[string]interface{}) (map[string]whitelistEntry, []interface{}) {
	rawWL, ok := data["whitelist"]
	if !ok {
		return nil, nil
	}
	wlSlice, ok := rawWL.([]interface{})
	if !ok {
		return nil, nil
	}
	wl := make(map[string]whitelistEntry, len(wlSlice))
	for _, item := range wlSlice {
		if entry, ok := item.(map[string]interface{}); ok {
			chatID, _ := entry["chat_id"].(string)
			chatName, _ := entry["chat_name"].(string)
			verifiedAt, _ := entry["verified_at"].(string)
			if chatID != "" {
				wl[chatID] = whitelistEntry{ChatName: chatName, VerifiedAt: verifiedAt}
			}
		}
	}
	return wl, wlSlice
}

// addToWhitelist adds a chat to the in-memory whitelist and syncs to DB.
// Returns the new verification code.
func (m *Manager) addToWhitelist(teamID string, chatID string, chatName string) string {
	key := "team:" + teamID
	now := time.Now().UTC().Format(time.RFC3339)
	newCode := generateVerificationCode()

	m.mu.Lock()
	if m.whitelists[key] == nil {
		m.whitelists[key] = make(map[string]whitelistEntry)
	}
	m.whitelists[key][chatID] = whitelistEntry{ChatName: chatName, VerifiedAt: now}
	m.verifyCodes[key] = newCode
	m.mu.Unlock()

	// Sync to DB
	m.syncTeamChannelData(teamID)

	// Auto-set as push channel if none is set yet
	go func() {
		if err := m.apiClient.SetPushChannel(context.Background(), teamID, "telegram", chatID, true); err != nil {
			slog.Warn("Failed to auto-set push channel", "team_id", teamID, "chat_id", chatID, "error", err)
		}
	}()

	return newCode
}

// isWhitelisted checks if a chat is in the whitelist (memory lookup).
func (m *Manager) isWhitelisted(teamID string, chatID string) bool {
	key := "team:" + teamID
	m.mu.RLock()
	defer m.mu.RUnlock()
	if wl, ok := m.whitelists[key]; ok {
		_, found := wl[chatID]
		return found
	}
	return false
}

// getVerificationCode returns the current verification code for a team.
func (m *Manager) getVerificationCode(teamID string) string {
	key := "team:" + teamID
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.verifyCodes[key]
}

func generateVerificationCode() string {
	return fmt.Sprintf("%04d", rand.Intn(10000))
}

func getTokenFromConfig(config map[string]interface{}) string {
	if val, ok := config["token"]; ok {
		if token, ok := val.(string); ok {
			return token
		}
	}
	return ""
}

// getChatName extracts a display name from a Telegram chat.
func getChatName(chat telego.Chat) string {
	if chat.Title != "" {
		return chat.Title
	}
	name := chat.FirstName
	if chat.LastName != "" {
		name += " " + chat.LastName
	}
	return name
}

