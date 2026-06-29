package bot

import (
	"context"
	"fmt"
	"log/slog"
	"strings"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/slack/slackclient"
)

// SlackSender implements shared.MessageSender for a single Slack channel/DM.
// Text and structured output render as Block Kit messages (so markdown, link
// buttons, and choice buttons display natively); media is uploaded to the
// channel inline. Every rich path degrades to plain text if the blocks/upload
// fail, so a reply is never silently dropped.
type SlackSender struct {
	client *slackclient.Client
	chatID string
}

func NewSlackSender(client *slackclient.Client, chatID string) *SlackSender {
	return &SlackSender{client: client, chatID: chatID}
}

// SendText renders text as a native-markdown block, falling back to a plain
// message if the block can't be sent.
func (s *SlackSender) SendText(ctx context.Context, text string) error {
	if text == "" {
		return nil
	}
	if err := s.client.PostBlocks(ctx, s.chatID, text, slackclient.TextBlocks(text)); err != nil {
		slog.Warn("slack: markdown block send failed, falling back to text", "error", err)
		return s.client.PostText(ctx, s.chatID, text)
	}
	return nil
}

// sendMedia downloads url and uploads the bytes to the channel with caption as
// the accompanying message. On any failure it posts the URL as plain text so
// the media is never silently dropped. Slack treats image/video/file uploads
// uniformly, so all three media methods share this path.
func (s *SlackSender) sendMedia(ctx context.Context, url, name, caption string) error {
	data, err := shared.DownloadFromURL(ctx, url)
	if err != nil {
		slog.Error("slack: media download failed, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, caption)
	}
	fileName := name
	if fileName == "" {
		fileName = shared.FilenameFromURL(url)
	}
	fileName = shared.EnsureFileExtension(fileName, data)

	if err := s.client.UploadMedia(ctx, s.chatID, fileName, caption, data); err != nil {
		slog.Error("slack: media upload failed, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, caption)
	}
	return nil
}

func (s *SlackSender) SendImage(ctx context.Context, url string, caption string) error {
	return s.sendMedia(ctx, url, "", caption)
}

func (s *SlackSender) SendVideo(ctx context.Context, url string, caption string) error {
	return s.sendMedia(ctx, url, "", caption)
}

func (s *SlackSender) SendFile(ctx context.Context, url string, name string, caption string) error {
	return s.sendMedia(ctx, url, name, caption)
}

// sendFallback posts a URL (optionally prefixed by a caption) as plain text
// when media upload/send fails.
func (s *SlackSender) sendFallback(ctx context.Context, url, caption string) error {
	text := url
	if caption != "" {
		text = caption + "\n" + url
	}
	return s.client.PostText(ctx, s.chatID, text)
}

func (s *SlackSender) SendCard(ctx context.Context, title, description, imageURL, linkURL, label string) error {
	fallback := title
	if fallback == "" {
		fallback = description
	}
	blocks := slackclient.CardBlocks(title, description, imageURL, linkURL, label)
	if err := s.client.PostBlocks(ctx, s.chatID, fallback, blocks); err != nil {
		slog.Warn("slack: card send failed, falling back to text", "error", err)
		return s.sendCardText(ctx, title, description, linkURL, label)
	}
	return nil
}

// sendCardText renders a card attachment as plain text when the Block Kit
// message can't be sent.
func (s *SlackSender) sendCardText(ctx context.Context, title, description, linkURL, label string) error {
	var parts []string
	if title != "" {
		parts = append(parts, "📋 "+title)
	}
	if description != "" {
		parts = append(parts, description)
	}
	if linkURL != "" {
		linkText := linkURL
		if label != "" {
			linkText = label + ": " + linkURL
		}
		parts = append(parts, "🔗 "+linkText)
	}
	if len(parts) == 0 {
		return nil
	}
	return s.client.PostText(ctx, s.chatID, strings.Join(parts, "\n"))
}

func (s *SlackSender) SendChoice(ctx context.Context, question string, options []string) error {
	blocks := slackclient.ChoiceBlocks(question, options)
	if err := s.client.PostBlocks(ctx, s.chatID, question, blocks); err != nil {
		slog.Warn("slack: choice send failed, falling back to text", "error", err)
		return s.sendChoiceText(ctx, question, options)
	}
	return nil
}

// sendChoiceText renders a choice as a numbered list (users can reply with the
// option text) when the Block Kit message can't be sent.
func (s *SlackSender) sendChoiceText(ctx context.Context, question string, options []string) error {
	var sb strings.Builder
	if question != "" {
		sb.WriteString("❓ " + question + "\n")
	}
	for i, opt := range options {
		sb.WriteString(fmt.Sprintf("%d. %s\n", i+1, opt))
	}
	return s.client.PostText(ctx, s.chatID, strings.TrimRight(sb.String(), "\n"))
}

var _ shared.MessageSender = (*SlackSender)(nil)
