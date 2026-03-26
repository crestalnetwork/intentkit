package bot

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/types"
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

	sender := NewTelegramSender(bot, message.Chat.ID)
	err := m.apiClient.StreamAgent(context.Background(), payload, func(msg types.ChatMessage) error {
		shared.DispatchMessage(context.Background(), msg, sender)
		return nil
	})
	if err != nil {
		slog.Error("Failed to stream agent", "error", err)
		_ = sender.SendText(context.Background(), "Sorry, I encountered an error processing your request.")
	}
}

func (m *Manager) handleTeamMessage(bot *telego.Bot, message telego.Message, teamID string) {
	if message.Text == "" || message.From == nil {
		return
	}

	slog.Info("Received team message", "team_id", teamID, "chat_id", message.Chat.ID)
	_ = bot.SendChatAction(context.Background(), tu.ChatAction(tu.ID(message.Chat.ID), telego.ChatActionTyping))

	telegramID := fmt.Sprintf("%d", message.From.ID)

	payload := map[string]interface{}{
		"team_id":     teamID,
		"telegram_id": telegramID,
		"chat_id":     fmt.Sprintf("%d", message.Chat.ID),
		"message":     message.Text,
	}

	sender := NewTelegramSender(bot, message.Chat.ID)
	err := m.apiClient.StreamTeamLead(context.Background(), payload, func(msg types.ChatMessage) error {
		shared.DispatchMessage(context.Background(), msg, sender)
		return nil
	})
	if err != nil {
		slog.Error("Failed to stream team lead", "error", err)
		_ = sender.SendText(context.Background(), "Sorry, I encountered an error processing your request.")
	}
}

func (m *Manager) handleCallbackQuery(bot *telego.Bot, query telego.CallbackQuery, agentID string, isTeam bool) {
	// Answer the callback query to remove the loading spinner
	_ = bot.AnswerCallbackQuery(context.Background(), tu.CallbackQuery(query.ID))

	chatID := query.Message.GetChat().ID

	slog.Info("Received callback query", "agent_id", agentID, "chat_id", chatID, "data", query.Data)

	sender := NewTelegramSender(bot, chatID)

	userID := fmt.Sprintf("%d", query.From.ID)
	if query.From.Username != "" {
		userID = query.From.Username
	}

	if isTeam {
		payload := map[string]interface{}{
			"team_id":     agentID,
			"telegram_id": fmt.Sprintf("%d", query.From.ID),
			"chat_id":     fmt.Sprintf("%d", chatID),
			"message":     query.Data,
		}
		err := m.apiClient.StreamTeamLead(context.Background(), payload, func(msg types.ChatMessage) error {
			shared.DispatchMessage(context.Background(), msg, sender)
			return nil
		})
		if err != nil {
			slog.Error("Failed to stream team lead from callback", "error", err)
			_ = sender.SendText(context.Background(), "Sorry, I encountered an error processing your request.")
		}
	} else {
		payload := map[string]interface{}{
			"id":          xid.New().String(),
			"agent_id":    agentID,
			"chat_id":     fmt.Sprintf("%d", chatID),
			"user_id":     userID,
			"author_id":   userID,
			"author_type": "telegram",
			"thread_type": "telegram",
			"message":     query.Data,
		}
		err := m.apiClient.StreamAgent(context.Background(), payload, func(msg types.ChatMessage) error {
			shared.DispatchMessage(context.Background(), msg, sender)
			return nil
		})
		if err != nil {
			slog.Error("Failed to stream agent from callback", "error", err)
			_ = sender.SendText(context.Background(), "Sorry, I encountered an error processing your request.")
		}
	}
}
