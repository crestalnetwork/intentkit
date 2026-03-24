package store

import (
	"time"

	"gorm.io/datatypes"
)

// TeamChannel represents a team's bound communication channel.
// WeChat integration only uses team channels (no individual agents).
type TeamChannel struct {
	TeamID      string            `gorm:"primaryKey"`
	ChannelType string            `gorm:"primaryKey"`
	Enabled     bool              `gorm:"default:true"`
	Config      datatypes.JSONMap `gorm:"type:jsonb"`
	UpdatedAt   time.Time
}

func (TeamChannel) TableName() string {
	return "team_channels"
}

// TeamChannelData represents runtime data for a team channel bot.
type TeamChannelData struct {
	TeamID      string            `gorm:"primaryKey"`
	ChannelType string            `gorm:"primaryKey"`
	Data        datatypes.JSONMap `gorm:"type:jsonb"`
}

func (TeamChannelData) TableName() string {
	return "team_channel_data"
}
