package bot

import (
	"context"
	"fmt"
	"log/slog"
	"regexp"
	"strings"
	"time"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/types"
	"github.com/mymmrac/telego"
	tu "github.com/mymmrac/telego/telegoutil"
	"github.com/redis/go-redis/v9"
	"github.com/rs/xid"
)

var fourDigitPattern = regexp.MustCompile(`^\d{4}$`)

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

	chatIDStr := fmt.Sprintf("%d", message.Chat.ID)
	sender := NewTelegramSender(bot, message.Chat.ID)

	// 1. Check whitelist — if verified, forward to agent
	if m.isWhitelisted(teamID, chatIDStr) {
		m.forwardTeamMessage(bot, message, teamID)
		return
	}

	// 2. Not whitelisted — check if message is a 4-digit code
	text := strings.TrimSpace(message.Text)
	if !fourDigitPattern.MatchString(text) {
		// Not a 4-digit number — silently discard
		return
	}

	// 3. Rate limiting check via Redis
	ctx := context.Background()
	rateLimitKey := fmt.Sprintf("tg_verify:%s:%s", teamID, chatIDStr)
	attempts, err := m.redis.Get(ctx, rateLimitKey).Int()
	if err != nil && err != redis.Nil {
		slog.Warn("Redis rate limit check failed, proceeding without limit",
			"team_id", teamID, "chat_id", chatIDStr, "error", err)
	}
	if attempts >= 3 {
		_ = sender.SendText(ctx, "Too many failed attempts. Please try again in 10 minutes.")
		return
	}

	// 4. Check verification code
	storedCode := m.getVerificationCode(teamID)
	if storedCode == "" {
		slog.Warn("No verification code set for team", "team_id", teamID)
		return
	}

	if text == storedCode {
		// Correct — add to whitelist
		chatName := getChatName(message.Chat)
		m.addToWhitelist(teamID, chatIDStr, chatName)

		// Clear rate limit
		m.redis.Del(ctx, rateLimitKey)

		slog.Info("Chat verified and added to whitelist",
			"team_id", teamID, "chat_id", chatIDStr, "chat_name", chatName)
		_ = sender.SendText(ctx, "Verified! This chat is now connected.")
	} else {
		// Wrong code — increment rate limit
		pipe := m.redis.Pipeline()
		pipe.Incr(ctx, rateLimitKey)
		pipe.Expire(ctx, rateLimitKey, 10*time.Minute)
		_, _ = pipe.Exec(ctx)

		_ = sender.SendText(ctx, "Wrong verification code.")
	}
}

// forwardTeamMessage sends a whitelisted team message to the lead agent.
func (m *Manager) forwardTeamMessage(bot *telego.Bot, message telego.Message, teamID string) {
	chatIDStr := fmt.Sprintf("%d", message.Chat.ID)

	// Intercept /default command — set this chat as the push channel
	if strings.TrimSpace(message.Text) == "/default" {
		sender := NewTelegramSender(bot, message.Chat.ID)
		if err := m.apiClient.SetPushChannel(context.Background(), teamID, "telegram", chatIDStr, false); err != nil {
			slog.Error("Failed to set push channel", "team_id", teamID, "error", err)
			_ = sender.SendText(context.Background(), "Failed to set push channel.")
		} else {
			_ = sender.SendText(context.Background(), "This chat is now the default push channel.")
		}
		return
	}

	slog.Info("Received team message", "team_id", teamID, "chat_id", message.Chat.ID)
	_ = bot.SendChatAction(context.Background(), tu.ChatAction(tu.ID(message.Chat.ID), telego.ChatActionTyping))

	telegramID := fmt.Sprintf("%d", message.From.ID)

	payload := map[string]interface{}{
		"team_id":     teamID,
		"telegram_id": telegramID,
		"chat_id":     chatIDStr,
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
		chatIDStr := fmt.Sprintf("%d", chatID)
		// Check whitelist for team callbacks
		if !m.isWhitelisted(agentID, chatIDStr) {
			// agentID is actually teamID for team callbacks
			return
		}

		payload := map[string]interface{}{
			"team_id":     agentID,
			"telegram_id": fmt.Sprintf("%d", query.From.ID),
			"chat_id":     chatIDStr,
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
