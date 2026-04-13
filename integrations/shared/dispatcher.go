package shared

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/crestalnetwork/intentkit/integrations/types"
)

type MessageSender interface {
	SendText(ctx context.Context, text string) error
	SendImage(ctx context.Context, url string, caption string) error
	SendVideo(ctx context.Context, url string, caption string) error
	SendFile(ctx context.Context, url string, name string, caption string) error
	SendCard(ctx context.Context, title, description, imageURL, linkURL, label string) error
	SendChoice(ctx context.Context, question string, options []string) error
}

func DispatchMessage(ctx context.Context, msg types.ChatMessage, sender MessageSender) {
	switch msg.AuthorType {
	case types.AuthorTypeThinking:
		return

	case types.AuthorTypeSkill:
		if len(msg.SkillCalls) > 0 {
			text := fmt.Sprintf("🔧 Running %s...", msg.SkillCalls[0].Name)
			if err := sender.SendText(ctx, text); err != nil {
				slog.Error("Failed to send skill status", "error", err)
			}
		}
		for _, att := range msg.Attachments {
			dispatchAttachment(ctx, att, sender)
		}

	case types.AuthorTypeSystem:
		if msg.Message == "" {
			return
		}
		var text string
		if msg.ErrorType != nil && *msg.ErrorType != "" {
			text = "❌ " + msg.Message
		} else {
			text = "ℹ️ " + msg.Message
		}
		if err := sender.SendText(ctx, text); err != nil {
			slog.Error("Failed to send system message", "error", err)
		}

	case types.AuthorTypeAgent:
		if msg.Message != "" {
			if err := sender.SendText(ctx, msg.Message); err != nil {
				slog.Error("Failed to send agent text", "error", err)
			}
		}
		for _, att := range msg.Attachments {
			dispatchAttachment(ctx, att, sender)
		}
	}
}

// attURL and attCaption extract url/caption from an attachment, handling nil pointers.
func attURL(att types.ChatMessageAttach) string {
	if att.URL != nil {
		return *att.URL
	}
	return ""
}

func attCaption(att types.ChatMessageAttach) string {
	if att.LeadText != nil {
		return *att.LeadText
	}
	return ""
}

func dispatchAttachment(ctx context.Context, att types.ChatMessageAttach, sender MessageSender) {
	switch att.Type {
	case types.AttachImage:
		if url := attURL(att); url != "" {
			if err := sender.SendImage(ctx, url, attCaption(att)); err != nil {
				slog.Error("Failed to send image", "error", err)
			}
		}

	case types.AttachVideo:
		if url := attURL(att); url != "" {
			if err := sender.SendVideo(ctx, url, attCaption(att)); err != nil {
				slog.Error("Failed to send video", "error", err)
			}
		}

	case types.AttachFile:
		if url := attURL(att); url != "" {
			name := ""
			if att.JSON != nil {
				name, _ = att.JSON["name"].(string)
			}
			if err := sender.SendFile(ctx, url, name, attCaption(att)); err != nil {
				slog.Error("Failed to send file", "error", err)
			}
		}

	case types.AttachCard:
		if att.JSON == nil {
			return
		}
		title, _ := att.JSON["title"].(string)
		description, _ := att.JSON["description"].(string)
		imageURL, _ := att.JSON["image_url"].(string)
		label, _ := att.JSON["label"].(string)
		// Link URL is in the top-level url field, not in json
		linkURL := attURL(att)
		if err := sender.SendCard(ctx, title, description, imageURL, linkURL, label); err != nil {
			slog.Error("Failed to send card", "error", err)
		}

	case types.AttachChoice:
		if att.JSON == nil {
			return
		}
		// Question is in lead_text, options are keyed objects {"a": {"title":"...", "content":"..."}, ...}
		question := attCaption(att)
		var options []string
		for _, key := range []string{"a", "b", "c"} {
			optRaw, ok := att.JSON[key]
			if !ok {
				continue
			}
			optMap, ok := optRaw.(map[string]interface{})
			if !ok {
				continue
			}
			title, _ := optMap["title"].(string)
			content, _ := optMap["content"].(string)
			if title != "" {
				opt := title
				if content != "" {
					opt += ": " + content
				}
				options = append(options, opt)
			}
		}
		if err := sender.SendChoice(ctx, question, options); err != nil {
			slog.Error("Failed to send choice", "error", err)
		}

	case types.AttachLink, types.AttachXMTP:
		// Skip
	}
}
