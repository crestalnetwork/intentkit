package alert

// Config holds alert-channel and rate-limit settings.
//
// Loaded as a nested struct via github.com/hack-fan/config. Env var names
// mirror the Python side so a single secrets bundle drives both stacks.
type Config struct {
	TgBotToken   string `env:"TG_ALERT_BOT_TOKEN"`
	TgChatID     string `env:"TG_ALERT_CHAT_ID"`
	SlackToken   string `env:"SLACK_ALERT_TOKEN"`
	SlackChannel string `env:"SLACK_ALERT_CHANNEL"`

	MaxMessages int `env:"ALERT_MAX_MESSAGES" default:"3"`
	TimeWindow  int `env:"ALERT_TIME_WINDOW" default:"60"`
}

// Backend reports which transport will be used given the current config.
// Telegram > Slack > None, matching the Python priority.
func (c *Config) Backend() Backend {
	if c.TgBotToken != "" && c.TgChatID != "" {
		return BackendTelegram
	}
	if c.SlackToken != "" && c.SlackChannel != "" {
		return BackendSlack
	}
	return BackendNone
}

type Backend int

const (
	BackendNone Backend = iota
	BackendTelegram
	BackendSlack
)

func (b Backend) String() string {
	switch b {
	case BackendTelegram:
		return "telegram"
	case BackendSlack:
		return "slack"
	default:
		return "none"
	}
}
