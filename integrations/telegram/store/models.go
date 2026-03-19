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

// TeamChannel represents a team's bound communication channel.
type TeamChannel struct {
	TeamID      string            `gorm:"primaryKey"`
	ChannelType string            `gorm:"primaryKey"`
	Enabled     bool              `gorm:"default:true"`
	Config      datatypes.JSONMap `gorm:"type:jsonb"`
	UpdatedAt   time.Time
}

// TableName overrides the table name for TeamChannel
func (TeamChannel) TableName() string {
	return "team_channels"
}

// TeamChannelData represents runtime data for a team channel bot.
// Platform-specific data is stored in the JSONB `data` column.
type TeamChannelData struct {
	TeamID      string            `gorm:"primaryKey"`
	ChannelType string            `gorm:"primaryKey"`
	Data        datatypes.JSONMap `gorm:"type:jsonb"`
}

// TableName overrides the table name for TeamChannelData
func (TeamChannelData) TableName() string {
	return "team_channel_data"
}
