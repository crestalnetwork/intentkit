package bot

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/crestalnetwork/intentkit/integrations/telegram/api"
	"github.com/crestalnetwork/intentkit/integrations/telegram/config"
	"github.com/crestalnetwork/intentkit/integrations/telegram/store"
	"github.com/mymmrac/telego"
	"gorm.io/gorm"
)

type Manager struct {
	db         *gorm.DB
	cfg        *config.Config
	apiClient  *api.Client
	bots       map[string]*telego.Bot
	cancelFuncs map[string]context.CancelFunc
	mu         sync.RWMutex
	stopCh     chan struct{}
}

func NewManager(db *gorm.DB, cfg *config.Config, apiClient *api.Client) *Manager {
	return &Manager{
		db:          db,
		cfg:         cfg,
		apiClient:   apiClient,
		bots:        make(map[string]*telego.Bot),
		cancelFuncs: make(map[string]context.CancelFunc),
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

	activeAgentIDs := make(map[string]bool)

	for _, agent := range agents {
		activeAgentIDs[agent.ID] = true
		m.ensureBotRunning(&agent)
	}

	// Stop bots for disabled/removed agents
	m.mu.Lock()
	for id, cancel := range m.cancelFuncs {
		if !activeAgentIDs[id] {
			cancel()
			delete(m.bots, id)
			delete(m.cancelFuncs, id)
			slog.Info("Stopped and removed bot for agent", "agent_id", id)
		}
	}
	m.mu.Unlock()
}

func (m *Manager) ensureBotRunning(agent *store.Agent) {
	m.mu.RLock()
	_, exists := m.bots[agent.ID]
	m.mu.RUnlock()

	if exists {
		// potential updates check could go here, for now assuming if it's running it's fine
		// untill config changes which we might need to track
		return
	}

	token := getTokenFromConfig(agent.TelegramConfig)
	if token == "" {
		slog.Warn("Agent has enabled telegram but no valid token", "agent_id", agent.ID)
		return
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

func getTokenFromConfig(config map[string]interface{}) string {
	if val, ok := config["token"]; ok {
		if token, ok := val.(string); ok {
			return token
		}
	}
	return ""
}
