package bot

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"path"
	"regexp"
	"strings"
	"time"

	"github.com/rs/xid"

	callback "github.com/larksuite/oapi-sdk-go/v3/event/dispatcher/callback"
	larkim "github.com/larksuite/oapi-sdk-go/v3/service/im/v1"

	"github.com/crestalnetwork/intentkit/integrations/lark/larkclient"
	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/types"
)

// channelType is the team_channels.channel_type value this integration serves.
const channelType = "lark"

// pushCommand makes the current chat the team's default proactive-push target.
const pushCommand = "/default"

// mentionRe matches the @_user_N placeholders Lark injects into group-message
// text for @mentions; they're noise to the LLM so we strip them.
var mentionRe = regexp.MustCompile(`@_user_\d+`)

// Inbound message content shapes (msg.content is a JSON string per type).
type textContent struct {
	Text string `json:"text"`
}

type imageContent struct {
	ImageKey string `json:"image_key"`
}

type fileContent struct {
	FileKey  string `json:"file_key"`
	FileName string `json:"file_name"`
}

type audioContent struct {
	FileKey  string `json:"file_key"`
	Duration int    `json:"duration"`
}

type mediaContent struct {
	FileKey  string `json:"file_key"`
	FileName string `json:"file_name"`
}

type postContent struct {
	Title   string          `json:"title"`
	Content [][]postElement `json:"content"`
}

type postElement struct {
	Tag      string `json:"tag"`
	Text     string `json:"text"`
	Href     string `json:"href"`
	ImageKey string `json:"image_key"`
}

// inboundMedia describes how to turn one inbound resource into a ChatMessageAttach.
type inboundMedia struct {
	resType     string // larkclient.ResourceType*
	kind        string // S3 path + log label
	attType     string // types.Attach*
	fileName    string // user-provided name, when known
	defaultExt  string
	defaultMime string
	leadText    string
}

// handleMessageEvent processes one inbound im.message.receive_v1 event: it
// extracts text + media, intercepts /default, and forwards the rest to the
// lead agent. Runs on its own goroutine so a slow stream never blocks the
// WebSocket read loop.
func (m *Manager) handleMessageEvent(client *larkclient.Client, teamID string, event *larkim.P2MessageReceiveV1) {
	ctx := context.Background()
	if event.Event == nil || event.Event.Message == nil || event.Event.Sender == nil {
		return
	}
	msg := event.Event.Message
	sender := event.Event.Sender

	openID := ""
	if sender.SenderId != nil {
		openID = derefStr(sender.SenderId.OpenId)
	}
	chatID := derefStr(msg.ChatId)
	messageID := derefStr(msg.MessageId)
	if openID == "" || chatID == "" {
		return
	}

	msgType := derefStr(msg.MessageType)
	content := derefStr(msg.Content)

	text := ""
	var attachments []types.ChatMessageAttach

	switch msgType {
	case "text":
		text = parseTextContent(content)
	case "post":
		text, attachments = m.parsePostContent(ctx, client, teamID, messageID, content)
	case "image":
		var ic imageContent
		_ = json.Unmarshal([]byte(content), &ic)
		if ic.ImageKey != "" {
			if att, ok := m.ingest(ctx, client, teamID, messageID, ic.ImageKey, inboundMedia{
				resType: larkclient.ResourceTypeImage, kind: "image", attType: types.AttachImage,
				defaultExt: "jpg", defaultMime: "image/jpeg", leadText: "User sent an image.",
			}); ok {
				attachments = append(attachments, att)
			}
		}
	case "file":
		var fc fileContent
		_ = json.Unmarshal([]byte(content), &fc)
		if fc.FileKey != "" {
			lead := "User sent a file."
			if fc.FileName != "" {
				lead = "User sent a file: " + fc.FileName
			}
			if att, ok := m.ingest(ctx, client, teamID, messageID, fc.FileKey, inboundMedia{
				resType: larkclient.ResourceTypeFile, kind: "file", attType: types.AttachFile,
				fileName: fc.FileName, defaultExt: "bin", defaultMime: "application/octet-stream", leadText: lead,
			}); ok {
				attachments = append(attachments, att)
			}
		}
	case "audio":
		var ac audioContent
		_ = json.Unmarshal([]byte(content), &ac)
		if ac.FileKey != "" {
			lead := "User sent a voice message."
			if ac.Duration > 0 {
				lead = fmt.Sprintf("User sent a voice message (%d ms).", ac.Duration)
			}
			if att, ok := m.ingest(ctx, client, teamID, messageID, ac.FileKey, inboundMedia{
				resType: larkclient.ResourceTypeFile, kind: "audio", attType: types.AttachAudio,
				defaultExt: "opus", defaultMime: "audio/opus", leadText: lead,
			}); ok {
				attachments = append(attachments, att)
			}
		}
	case "media":
		var mc mediaContent
		_ = json.Unmarshal([]byte(content), &mc)
		if mc.FileKey != "" {
			if att, ok := m.ingest(ctx, client, teamID, messageID, mc.FileKey, inboundMedia{
				resType: larkclient.ResourceTypeFile, kind: "video", attType: types.AttachVideo,
				fileName: mc.FileName, defaultExt: "mp4", defaultMime: "video/mp4", leadText: "User sent a video.",
			}); ok {
				attachments = append(attachments, att)
			}
		}
	default:
		slog.Debug("lark: ignoring unsupported message type", "team_id", teamID, "type", msgType)
		return
	}

	text = strings.TrimSpace(text)
	if text == "" && len(attachments) == 0 {
		return
	}

	slog.Info("lark: received message", "team_id", teamID, "from", openID, "type", msgType)

	if text == pushCommand {
		m.handlePushCommand(ctx, client, teamID, chatID)
		return
	}

	if text == "" {
		text = summarizeAttachments(attachments)
	}

	m.forwardToLead(ctx, client, teamID, openID, chatID, text, attachments)
}

// handlePushCommand binds the current chat as the team's default push target.
func (m *Manager) handlePushCommand(ctx context.Context, client *larkclient.Client, teamID, chatID string) {
	if err := m.apiClient.SetPushChannel(ctx, teamID, channelType, chatID, false); err != nil {
		slog.Error("lark: failed to set push channel", "team_id", teamID, "error", err)
		_ = client.SendText(ctx, chatID, "Failed to set push channel.")
		return
	}
	_ = client.SendText(ctx, chatID, "This chat is now the default push channel.")
}

// handleCardAction processes a choice-button click: it forwards the selected
// option to the lead agent (async) and immediately returns a toast so the
// clicking user gets instant feedback.
func (m *Manager) handleCardAction(
	client *larkclient.Client, teamID string, event *callback.CardActionTriggerEvent,
) *callback.CardActionTriggerResponse {
	if event.Event == nil || event.Event.Action == nil {
		return nil
	}
	option, _ := event.Event.Action.Value[larkclient.ChoiceValueKey].(string)
	if option == "" {
		return nil
	}

	openID := ""
	if event.Event.Operator != nil {
		openID = event.Event.Operator.OpenID
	}
	chatID := ""
	if event.Event.Context != nil {
		chatID = event.Event.Context.OpenChatID
	}
	if chatID == "" {
		return nil
	}

	slog.Info("lark: choice selected", "team_id", teamID, "from", openID, "option", option)
	go m.forwardToLead(context.Background(), client, teamID, openID, chatID, option, nil)

	// Lark toasts are short; cap the echoed option so it isn't truncated/rejected.
	return &callback.CardActionTriggerResponse{
		Toast: &callback.Toast{Type: "info", Content: "✅ " + truncateRunes(option, 24)},
	}
}

// truncateRunes shortens s to at most max runes, appending an ellipsis when cut.
func truncateRunes(s string, max int) string {
	r := []rune(s)
	if len(r) <= max {
		return s
	}
	return string(r[:max]) + "…"
}

// forwardToLead streams a user message (with any attachments) through the lead
// agent and dispatches each reply chunk back to the chat.
func (m *Manager) forwardToLead(
	ctx context.Context,
	client *larkclient.Client,
	teamID, channelUserID, chatID, text string,
	attachments []types.ChatMessageAttach,
) {
	payload := map[string]interface{}{
		"team_id":         teamID,
		"channel_type":    channelType,
		"channel_user_id": channelUserID,
		"chat_id":         chatID,
		"message":         text,
	}
	if len(attachments) > 0 {
		payload["attachments"] = attachments
	}

	sender := NewLarkSender(client, chatID)
	err := m.apiClient.StreamTeamLead(ctx, payload, func(cm types.ChatMessage) error {
		shared.DispatchMessage(ctx, cm, sender)
		return nil
	})
	if err != nil {
		slog.Error("lark: stream team lead failed", "team_id", teamID, "error", err)
		if sendErr := sender.SendText(ctx, "Sorry, I encountered an error processing your request."); sendErr != nil {
			slog.Error("lark: failed to send error reply", "team_id", teamID, "error", sendErr)
		}
	}
}

// parsePostContent flattens a rich-text (post) message into text plus any
// embedded images (downloaded and re-hosted on S3).
func (m *Manager) parsePostContent(
	ctx context.Context, client *larkclient.Client, teamID, messageID, content string,
) (string, []types.ChatMessageAttach) {
	var pc postContent
	if err := json.Unmarshal([]byte(content), &pc); err != nil {
		return "", nil
	}
	var sb strings.Builder
	if pc.Title != "" {
		sb.WriteString(pc.Title)
		sb.WriteString("\n")
	}
	var attachments []types.ChatMessageAttach
	for _, line := range pc.Content {
		for _, el := range line {
			switch el.Tag {
			case "text":
				sb.WriteString(el.Text)
			case "a":
				sb.WriteString(el.Text)
				if el.Href != "" {
					sb.WriteString("(" + el.Href + ")")
				}
			case "img":
				if el.ImageKey != "" {
					if att, ok := m.ingest(ctx, client, teamID, messageID, el.ImageKey, inboundMedia{
						resType: larkclient.ResourceTypeImage, kind: "image", attType: types.AttachImage,
						defaultExt: "jpg", defaultMime: "image/jpeg", leadText: "User sent an image.",
					}); ok {
						attachments = append(attachments, att)
					}
				}
			}
		}
		sb.WriteString("\n")
	}
	return strings.TrimSpace(sb.String()), attachments
}

// ingest downloads an inbound resource, re-hosts it on S3, and builds the
// attachment to forward to the LLM. Returns ok=false on any failure (logged),
// so one bad item is dropped rather than aborting the whole message.
func (m *Manager) ingest(
	ctx context.Context, client *larkclient.Client, teamID, messageID, fileKey string, spec inboundMedia,
) (types.ChatMessageAttach, bool) {
	data, err := client.DownloadResource(ctx, messageID, fileKey, spec.resType)
	if err != nil {
		slog.Error("lark: failed to download resource",
			"team_id", teamID, "kind", spec.kind, "error", err)
		return types.ChatMessageAttach{}, false
	}

	contentType := http.DetectContentType(data)
	ext := extensionFromFilename(spec.fileName)
	if ext == "" {
		ext = shared.ExtensionForContentType(contentType)
	}
	if ext == "" {
		ext = spec.defaultExt
		contentType = spec.defaultMime
	}

	key := fmt.Sprintf("lark/%s/%s/%d_%s.%s",
		teamID, spec.kind, time.Now().UnixMilli(), xid.New().String(), ext)
	url, err := m.storage.StoreMedia(ctx, data, key, contentType)
	if err != nil {
		slog.Error("lark: failed to upload resource to S3",
			"team_id", teamID, "kind", spec.kind, "error", err)
		return types.ChatMessageAttach{}, false
	}
	slog.Info("lark: ingested inbound media", "team_id", teamID, "kind", spec.kind, "url", url)

	lead := spec.leadText
	return types.ChatMessageAttach{Type: spec.attType, LeadText: &lead, URL: &url}, true
}

func parseTextContent(content string) string {
	var tc textContent
	if err := json.Unmarshal([]byte(content), &tc); err != nil {
		return ""
	}
	return strings.TrimSpace(mentionRe.ReplaceAllString(tc.Text, ""))
}

// summarizeAttachments builds a short placeholder when the user sent only media.
func summarizeAttachments(attachments []types.ChatMessageAttach) string {
	var images, audios, videos, files int
	for _, att := range attachments {
		switch att.Type {
		case types.AttachImage:
			images++
		case types.AttachAudio:
			audios++
		case types.AttachVideo:
			videos++
		case types.AttachFile:
			files++
		}
	}
	var parts []string
	parts = appendNoun(parts, images, "an image", "images")
	parts = appendNoun(parts, audios, "a voice message", "voice messages")
	parts = appendNoun(parts, videos, "a video", "videos")
	parts = appendNoun(parts, files, "a file", "files")
	if len(parts) == 0 {
		return "User sent an attachment."
	}
	return "User sent " + strings.Join(parts, ", ") + "."
}

func appendNoun(parts []string, count int, singular, plural string) []string {
	if count == 1 {
		return append(parts, singular)
	}
	if count > 1 {
		return append(parts, fmt.Sprintf("%d %s", count, plural))
	}
	return parts
}

// extensionFromFilename returns the lowercased extension (without the dot), or
// "" if none. Uses path.Ext (always forward-slash) not filepath.Ext.
func extensionFromFilename(name string) string {
	ext := path.Ext(name)
	if len(ext) <= 1 {
		return ""
	}
	return strings.ToLower(ext[1:])
}

func derefStr(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
