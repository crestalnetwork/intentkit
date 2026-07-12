package shared

import (
	"context"
	"fmt"
	"log/slog"
	"strings"

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

	case types.AuthorTypeTool:
		// Status lines are sent from the pending frame, which arrives when
		// the tool calls start; the result messages that follow carry only
		// attachments (IM channels never show parameters or results).
		if msg.Pending {
			if len(msg.ToolCalls) > 0 {
				// Prefer the agent-written status lines over raw tool names.
				lines := make([]string, 0, len(msg.ToolCalls))
				for _, tc := range msg.ToolCalls {
					// write_todos gets a todo-aware rendering (checklist or
					// progress line) in place of the generic status line.
					if tc.Name == "write_todos" {
						if todoText := renderTodoStatus(tc.Parameters); todoText != "" {
							lines = append(lines, todoText)
							continue
						}
					}
					if status := strings.TrimSpace(tc.DisplayMessage); status != "" {
						lines = append(lines, "🔧 "+status)
					} else {
						lines = append(lines, fmt.Sprintf("🔧 Running %s...", tc.Name))
					}
				}
				if err := sender.SendText(ctx, strings.Join(lines, "\n")); err != nil {
					slog.Error("Failed to send tool status", "error", err)
				}
			}
			return
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

// renderTodoStatus renders a write_todos call for IM channels. A fresh plan
// (no item completed yet) renders as a full checklist; later updates render
// as a compact one-line progress note, so an evolving list costs no more
// messages than the generic status line it replaces. Language-neutral by
// design: only symbols plus the model-written item text. Returns "" when
// the parameters don't have the expected shape (caller falls back to the
// generic status line).
func renderTodoStatus(params map[string]interface{}) string {
	rawList, ok := params["todos"].([]interface{})
	if !ok || len(rawList) == 0 {
		return ""
	}
	type todoItem struct {
		content string
		status  string
	}
	todos := make([]todoItem, 0, len(rawList))
	completed := 0
	current := ""
	for _, raw := range rawList {
		m, ok := raw.(map[string]interface{})
		if !ok {
			return ""
		}
		content, _ := m["content"].(string)
		status, _ := m["status"].(string)
		if content == "" || status == "" {
			return ""
		}
		todos = append(todos, todoItem{content: content, status: status})
		switch status {
		case "completed":
			completed++
		case "in_progress":
			if current == "" {
				current = content
			}
		}
	}
	if completed == 0 {
		lines := make([]string, 0, len(todos)+1)
		lines = append(lines, fmt.Sprintf("📋 0/%d", len(todos)))
		for _, t := range todos {
			marker := "⬜"
			if t.status == "in_progress" {
				marker = "🔄"
			}
			lines = append(lines, marker+" "+t.content)
		}
		return strings.Join(lines, "\n")
	}
	if current != "" {
		return fmt.Sprintf("📋 %d/%d · 🔄 %s", completed, len(todos), current)
	}
	return fmt.Sprintf("📋 %d/%d", completed, len(todos))
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
