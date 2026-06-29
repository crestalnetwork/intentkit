package bot

import (
	"context"
	"encoding/json"
	"fmt"
	"html"
	"log/slog"
	"net/http"
	"path"
	"regexp"
	"strings"
	"time"

	"github.com/rs/xid"
	"github.com/slack-go/slack"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/slack/slackclient"
	"github.com/crestalnetwork/intentkit/integrations/types"
)

// channelType is the team_channels.channel_type value this integration serves.
const channelType = "slack"

// pushCommand makes the current chat the team's default proactive-push target.
const pushCommand = "/default"

// Slack message text encodes control sequences in angle brackets: links
// (<url|label> or <url>) and entities — <@U…|label> (user), <#C…|label>
// (channel), <!here>/<!subteam^S…|label> (special). We unwrap links and rewrite
// entities to readable text before forwarding to the LLM.
var (
	linkRe     = regexp.MustCompile(`<(https?://[^|>]+)\|([^>]+)>`)
	bareLinkRe = regexp.MustCompile(`<(https?://[^>]+)>`)
	// slackEntityRe matches <prefix id> or <prefix id|label>, prefix being @
	// (user), # (channel) or ! (special/subteam).
	slackEntityRe = regexp.MustCompile(`<([@#!])([^>|]*)(?:\|([^>]*))?>`)
)

// messageEnvelope is the slice of the Socket Mode events_api payload we need.
// slack-go's MessageEvent omits the top-level files array, so we parse the raw
// envelope ourselves to recover inbound attachments.
type messageEnvelope struct {
	Event inboundMessage `json:"event"`
}

type inboundMessage struct {
	Type        string       `json:"type"`
	Subtype     string       `json:"subtype"`
	User        string       `json:"user"`
	BotID       string       `json:"bot_id"`
	Text        string       `json:"text"`
	Channel     string       `json:"channel"`
	ChannelType string       `json:"channel_type"`
	TS          string       `json:"ts"`
	Files       []slack.File `json:"files"`
}

// handleMessageEvent processes one inbound message / app_mention event: it
// extracts text + files, intercepts /default, and forwards the rest to the lead
// agent. Runs on its own goroutine so a slow stream never blocks the event loop.
func (m *Manager) handleMessageEvent(client *slackclient.Client, teamID string, payload []byte) {
	ctx := context.Background()

	var env messageEnvelope
	if err := json.Unmarshal(payload, &env); err != nil {
		slog.Error("slack: failed to parse message payload", "team_id", teamID, "error", err)
		return
	}
	msg := env.Event

	// Drop bot messages (including our own — prevents reply loops) and edits/
	// joins/etc. Only fresh user messages (no subtype) and file shares pass.
	if msg.BotID != "" || msg.User == "" || msg.Channel == "" {
		return
	}
	if msg.Subtype != "" && msg.Subtype != "file_share" {
		return
	}

	text := cleanText(msg.Text)
	var attachments []types.ChatMessageAttach
	for i := range msg.Files {
		if att, ok := m.ingest(ctx, client, teamID, &msg.Files[i]); ok {
			attachments = append(attachments, att)
		}
	}

	if text == "" && len(attachments) == 0 {
		return
	}

	slog.Info("slack: received message", "team_id", teamID, "from", msg.User, "channel", msg.Channel)

	if text == pushCommand {
		m.handlePushCommand(ctx, client, teamID, msg.Channel)
		return
	}

	if text == "" {
		text = summarizeAttachments(attachments)
	}

	m.forwardToLead(ctx, client, teamID, msg.User, msg.Channel, text, attachments)
}

// handleInteraction processes a choice-button click: it forwards the selected
// option (carried as the button's value) to the lead agent. The event loop has
// already ack'd the interaction, so the user's click is acknowledged instantly.
func (m *Manager) handleInteraction(client *slackclient.Client, teamID string, callback *slack.InteractionCallback) {
	if callback.Type != slack.InteractionTypeBlockActions {
		return
	}
	channelID := callback.Channel.ID
	if channelID == "" {
		return
	}
	for _, action := range callback.ActionCallback.BlockActions {
		if action == nil || !strings.HasPrefix(action.ActionID, slackclient.ChoiceActionPrefix) {
			continue
		}
		if action.Value == "" {
			continue
		}
		slog.Info("slack: choice selected", "team_id", teamID, "from", callback.User.ID, "option", action.Value)
		// Forward only the first matched choice; a single click yields one reply.
		m.forwardToLead(context.Background(), client, teamID, callback.User.ID, channelID, action.Value, nil)
		return
	}
}

// handlePushCommand binds the current chat as the team's default push target.
func (m *Manager) handlePushCommand(ctx context.Context, client *slackclient.Client, teamID, chatID string) {
	if err := m.apiClient.SetPushChannel(ctx, teamID, channelType, chatID, false); err != nil {
		slog.Error("slack: failed to set push channel", "team_id", teamID, "error", err)
		_ = client.PostText(ctx, chatID, "Failed to set push channel.")
		return
	}
	_ = client.PostText(ctx, chatID, "This chat is now the default push channel.")
}

// forwardToLead streams a user message (with any attachments) through the lead
// agent and dispatches each reply chunk back to the chat.
func (m *Manager) forwardToLead(
	ctx context.Context,
	client *slackclient.Client,
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

	sender := NewSlackSender(client, chatID)
	err := m.apiClient.StreamTeamLead(ctx, payload, func(cm types.ChatMessage) error {
		shared.DispatchMessage(ctx, cm, sender)
		return nil
	})
	if err != nil {
		slog.Error("slack: stream team lead failed", "team_id", teamID, "error", err)
		if sendErr := sender.SendText(ctx, "Sorry, I encountered an error processing your request."); sendErr != nil {
			slog.Error("slack: failed to send error reply", "team_id", teamID, "error", sendErr)
		}
	}
}

// ingest downloads an inbound file, re-hosts it on S3, and builds the
// attachment to forward to the LLM. Returns ok=false on any failure (logged),
// so one bad file is dropped rather than aborting the whole message.
func (m *Manager) ingest(
	ctx context.Context, client *slackclient.Client, teamID string, f *slack.File,
) (types.ChatMessageAttach, bool) {
	if f.URLPrivateDownload == "" {
		return types.ChatMessageAttach{}, false
	}
	if f.Size > shared.MaxMediaSize {
		slog.Warn("slack: inbound file exceeds max size, skipping",
			"team_id", teamID, "name", f.Name, "size", f.Size)
		return types.ChatMessageAttach{}, false
	}

	// f.Size lets DownloadFile pre-size its buffer (avoids repeated regrowth).
	data, err := client.DownloadFile(ctx, f.URLPrivateDownload, f.Size)
	if err != nil {
		slog.Error("slack: failed to download file", "team_id", teamID, "name", f.Name, "error", err)
		return types.ChatMessageAttach{}, false
	}

	attType, kind, lead := classifyFile(f)

	contentType := f.Mimetype
	if contentType == "" {
		contentType = http.DetectContentType(data)
	}
	ext := extensionFromFilename(f.Name)
	if ext == "" {
		ext = shared.ExtensionForContentType(contentType)
	}
	if ext == "" {
		ext = f.Filetype // Slack's own type hint, e.g. "png", "mp4", "pdf"
	}
	if ext == "" {
		ext = "bin" // last resort, so the S3 key never ends in a bare dot
	}

	key := fmt.Sprintf("slack/%s/%s/%d_%s.%s",
		teamID, kind, time.Now().UnixMilli(), xid.New().String(), ext)
	url, err := m.storage.StoreMedia(ctx, data, key, contentType)
	if err != nil {
		slog.Error("slack: failed to upload file to S3", "team_id", teamID, "kind", kind, "error", err)
		return types.ChatMessageAttach{}, false
	}
	slog.Info("slack: ingested inbound file", "team_id", teamID, "kind", kind, "url", url)

	return types.ChatMessageAttach{Type: attType, LeadText: &lead, URL: &url}, true
}

// classifyFile maps a Slack file to an attachment type, S3 path label, and the
// placeholder lead text used when the user sent media with no caption.
func classifyFile(f *slack.File) (attType, kind, lead string) {
	switch {
	case strings.HasPrefix(f.Mimetype, "image/"):
		return types.AttachImage, "image", "User sent an image."
	case strings.HasPrefix(f.Mimetype, "video/"):
		return types.AttachVideo, "video", "User sent a video."
	case strings.HasPrefix(f.Mimetype, "audio/"):
		return types.AttachAudio, "audio", "User sent a voice message."
	default:
		lead = "User sent a file."
		if f.Name != "" {
			lead = "User sent a file: " + f.Name
		}
		return types.AttachFile, "file", lead
	}
}

// cleanText unwraps Slack links and rewrites mention entities to readable text,
// then decodes the HTML entities (&amp; &lt; &gt;) Slack escapes message text
// with, so the LLM sees clean prose instead of raw markup.
func cleanText(s string) string {
	s = linkRe.ReplaceAllString(s, "$2")
	s = bareLinkRe.ReplaceAllString(s, "$1")
	s = slackEntityRe.ReplaceAllStringFunc(s, replaceSlackEntity)
	s = html.UnescapeString(s)
	return strings.TrimSpace(s)
}

// replaceSlackEntity rewrites one <@…>/<#…>/<!…> token to readable text: user
// mentions are dropped (the id is noise to the LLM), channel mentions and
// labelled specials/subteams become their label, and a bare special such as
// <!here> becomes @here.
func replaceSlackEntity(token string) string {
	m := slackEntityRe.FindStringSubmatch(token)
	if m == nil {
		return token
	}
	prefix, id, label := m[1], m[2], m[3]
	switch prefix {
	case "#":
		if label != "" {
			return "#" + label
		}
		return ""
	case "!":
		if label != "" {
			return label
		}
		return "@" + id
	default: // "@" user mention
		return ""
	}
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
