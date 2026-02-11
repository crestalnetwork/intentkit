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
    // Basic text filter for now
    if message.Text == "" {
        return
    }
	    
		slog.Info("Received message", "agent_id", agentID, "chat_id", message.Chat.ID, "text", message.Text)

        // Show typing action
        _ = bot.SendChatAction(context.Background(), tu.ChatAction(tu.ID(message.Chat.ID), telego.ChatActionTyping))

		// Prepare payload for Core API
		// Assuming ChatMessageCreate structure:
		// agent_id, chat_id, user_id, author_id, author_type, thread_type, message
		
		userID := fmt.Sprintf("%d", message.From.ID)
		if message.From.Username != "" {
		    // Prefer username if available as per existing logic, or keep ID?
		    // Existing logic tries to lookup User by TG username. 
		    // For simplicity here we might just use string ID or username if we want to mimic existing specific logic, 
		    // but passing raw ID is safer if we don't have User table access/logic here.
		    // The requirement says "reproduce core logic". 
		    // app/services/tg/bot/kind/ai_relayer/router.py:get_user_id tries to find user by username.
		    // We will stick to simple ID for now or username if present to be recognizable.
		    // However, the safe bet is unique ID. Let's use ID for reliability.
            if message.From.Username != "" {
                userID = message.From.Username
            }
		}

		payload := map[string]interface{}{
		    "id": xid.New().String(),
			"agent_id":    agentID,
			"chat_id":     fmt.Sprintf("%d", message.Chat.ID), // Treat simple chat ID as string
			"user_id":     userID,
			"author_id":   userID,
			"author_type": "telegram",
			"thread_type": "telegram",
			"message":     message.Text,
		}

		// Call Core API
		resp, err := m.apiClient.ExecuteAgent(payload)
		if err != nil {
			slog.Error("Failed to execute agent", "error", err)
			_, _ = bot.SendMessage(context.Background(), tu.Message(tu.ID(message.Chat.ID), "Sorry, I encountered an error processing your request."))
			return
		}

        // Process response
        // Expecting list of messages. We typically want the last one or all new ones.
        // Core API returns list[ChatMessage].
        if len(resp) > 0 {
            for _, msg := range resp {
                if msgMap, ok := msg.(map[string]interface{}); ok {
                    if text, ok := msgMap["message"].(string); ok && text != ""{
                         _, _ = bot.SendMessage(context.Background(), tu.Message(tu.ID(message.Chat.ID), text))
                    }
                }
            }
        }
}
