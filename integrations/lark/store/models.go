package store

import (
	"time"

	"gorm.io/datatypes"
)

// TeamChannel represents a team's bound communication channel.
// Lark integration only uses team channels (no individual agents). Unlike
// telegram/wechat, lark keeps no per-channel runtime state (no session window,
// typing ticket, or context token), so there is no team_channel_data model
// here — proactive pushes authenticate with the app credentials directly.
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
