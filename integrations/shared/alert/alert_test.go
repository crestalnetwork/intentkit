package alert

import (
	"log/slog"
	"strings"
	"testing"
)

func TestWrapNoConfigReturnsInner(t *testing.T) {
	inner := slog.NewTextHandler(&strings.Builder{}, nil)
	got, shutdown := Wrap(inner, nil, nil)
	defer shutdown()
	if got != inner {
		t.Fatal("expected Wrap(nil cfg) to return inner handler")
	}
}

func TestWrapNoBackendReturnsInner(t *testing.T) {
	inner := slog.NewTextHandler(&strings.Builder{}, nil)
	got, shutdown := Wrap(inner, &Config{}, nil)
	defer shutdown()
	if got != inner {
		t.Fatal("expected Wrap(empty cfg) to return inner handler")
	}
}

func TestWrapNoRedisReturnsInner(t *testing.T) {
	inner := slog.NewTextHandler(&strings.Builder{}, nil)
	cfg := &Config{TgBotToken: "x", TgChatID: "y"}
	got, shutdown := Wrap(inner, cfg, nil)
	defer shutdown()
	if got != inner {
		t.Fatal("expected Wrap with nil redis to return inner handler")
	}
}

func TestBackendPriority(t *testing.T) {
	cases := []struct {
		name    string
		cfg     Config
		backend Backend
	}{
		{"none", Config{}, BackendNone},
		{"telegram-only", Config{TgBotToken: "t", TgChatID: "c"}, BackendTelegram},
		{"slack-only", Config{SlackToken: "t", SlackChannel: "c"}, BackendSlack},
		{
			"telegram-wins",
			Config{TgBotToken: "t", TgChatID: "c", SlackToken: "s", SlackChannel: "k"},
			BackendTelegram,
		},
		{"telegram-incomplete-falls-to-slack", Config{TgBotToken: "t", SlackToken: "s", SlackChannel: "k"}, BackendSlack},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := tc.cfg.Backend(); got != tc.backend {
				t.Fatalf("got %v, want %v", got, tc.backend)
			}
		})
	}
}
