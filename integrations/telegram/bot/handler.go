package bot

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/mymmrac/telego"
	tu "github.com/mymmrac/telego/telegoutil"
	"github.com/rs/xid"
)

func (m *Manager) handleMessage(bot *telego.Bot, message telego.Message, agentID string) {
	if message.Text == "" {
		return
	}

	slog.Info("Received message", "agent_id", agentID, "chat_id", message.Chat.ID)

	_ = bot.SendChatAction(context.Background(), tu.ChatAction(tu.ID(message.Chat.ID), telego.ChatActionTyping))

	userID := fmt.Sprintf("%d", message.From.ID)
	if message.From.Username != "" {
		userID = message.From.Username
	}

	payload := map[string]interface{}{
		"id":          xid.New().String(),
		"agent_id":    agentID,
		"chat_id":     fmt.Sprintf("%d", message.Chat.ID),
		"user_id":     userID,
		"author_id":   userID,
		"author_type": "telegram",
		"thread_type": "telegram",
		"message":     message.Text,
	}

	resp, err := m.apiClient.ExecuteAgent(payload)
	if err != nil {
		slog.Error("Failed to execute agent", "error", err)
		_, _ = bot.SendMessage(context.Background(), tu.Message(tu.ID(message.Chat.ID), "Sorry, I encountered an error processing your request."))
		return
	}

	for _, chatMsg := range resp {
		if chatMsg.IsAgentResponse() {
			_, _ = bot.SendMessage(context.Background(), tu.Message(tu.ID(message.Chat.ID), chatMsg.Message))
		}
	}
}
