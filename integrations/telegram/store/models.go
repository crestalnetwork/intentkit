package store

import (
	"time"

	"gorm.io/datatypes"
)

// Agent represents the agent configuration in the database.
type Agent struct {
	ID                        string            `gorm:"primaryKey;type:varchar"`
	TelegramEntrypointEnabled bool              `gorm:"default:false"`
	TelegramConfig            datatypes.JSONMap `gorm:"type:jsonb"`
	DeployedAt                *time.Time
	UpdatedAt                 time.Time
}

// TableName overrides the table name for Agent
func (Agent) TableName() string {
	return "agents"
}

// AgentData represents the runtime data for an agent.
type AgentData struct {
	ID               string `gorm:"primaryKey;type:varchar"`
	TelegramID       *string
	TelegramUsername *string
	TelegramName     *string
}

// TableName overrides the table name for AgentData
func (AgentData) TableName() string {
	return "agent_data"
}
