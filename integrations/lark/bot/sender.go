package bot

import (
	"context"
	"fmt"
	"log/slog"
	"strings"

	"github.com/crestalnetwork/intentkit/integrations/lark/larkclient"
	"github.com/crestalnetwork/intentkit/integrations/shared"
)

// LarkSender implements shared.MessageSender for a single Lark/Feishu chat.
// Text and structured output render as interactive cards (so markdown, link
// buttons, and choice buttons display natively); media is uploaded to Lark and
// sent inline. Every rich path degrades to plain text if the card/upload fails,
// so a reply is never silently dropped.
type LarkSender struct {
	client *larkclient.Client
	chatID string
}

func NewLarkSender(client *larkclient.Client, chatID string) *LarkSender {
	return &LarkSender{client: client, chatID: chatID}
}

// SendText renders text as a markdown card, falling back to a plain-text
// message if the card can't be built or sent.
func (s *LarkSender) SendText(ctx context.Context, text string) error {
	if text == "" {
		return nil
	}
	cardJSON, err := larkclient.TextCard(text)
	if err != nil {
		slog.Warn("lark: build markdown card failed, falling back to text", "error", err)
		return s.client.SendText(ctx, s.chatID, text)
	}
	if err := s.client.SendCardJSON(ctx, s.chatID, cardJSON); err != nil {
		slog.Warn("lark: markdown card send failed, falling back to text", "error", err)
		return s.client.SendText(ctx, s.chatID, text)
	}
	return nil
}

// sendFallback posts a URL (optionally prefixed) as plain text when media
// upload/send fails. Plain text is used so the fallback itself can't be
// rejected the way a card might.
func (s *LarkSender) sendFallback(ctx context.Context, url, prefix string) error {
	text := url
	if prefix != "" {
		text = prefix + "\n" + url
	}
	return s.client.SendText(ctx, s.chatID, text)
}

// sendCaption posts a trailing caption (after media) as a markdown card.
func (s *LarkSender) sendCaption(ctx context.Context, caption string) {
	if caption == "" {
		return
	}
	if err := s.SendText(ctx, caption); err != nil {
		slog.Warn("lark: failed to send caption", "error", err)
	}
}

func (s *LarkSender) SendImage(ctx context.Context, url string, caption string) error {
	data, err := shared.DownloadFromURL(ctx, url)
	if err != nil {
		slog.Error("lark: image download failed, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, caption)
	}
	imageKey, err := s.client.UploadImage(ctx, data)
	if err != nil {
		slog.Error("lark: image upload failed, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, caption)
	}
	if err := s.client.SendImageKey(ctx, s.chatID, imageKey); err != nil {
		slog.Error("lark: image send failed, falling back to text", "error", err)
		return s.sendFallback(ctx, url, caption)
	}
	s.sendCaption(ctx, caption)
	return nil
}

func (s *LarkSender) SendVideo(ctx context.Context, url string, caption string) error {
	data, err := shared.DownloadFromURL(ctx, url)
	if err != nil {
		slog.Error("lark: video download failed, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, caption)
	}
	name := shared.EnsureFileExtension(shared.FilenameFromURL(url), data)

	// Upload once. An mp4 is sent as an inline media message; anything else (or
	// an mp4 whose media-send is rejected) is sent as a generic file. The
	// file_key is reusable across both message types, so we never re-upload.
	isMP4 := strings.HasSuffix(strings.ToLower(name), ".mp4")
	fileType := larkclient.FileTypeStream
	if isMP4 {
		fileType = larkclient.FileTypeMP4
	}
	fileKey, err := s.client.UploadFile(ctx, fileType, name, data)
	if err != nil {
		slog.Error("lark: video upload failed, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, caption)
	}

	if isMP4 {
		if err := s.client.SendMediaKey(ctx, s.chatID, fileKey); err == nil {
			s.sendCaption(ctx, caption)
			return nil
		} else {
			slog.Warn("lark: media send failed, trying file message", "error", err)
		}
	}
	if err := s.client.SendFileKey(ctx, s.chatID, fileKey); err != nil {
		slog.Error("lark: video send failed, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, caption)
	}
	s.sendCaption(ctx, caption)
	return nil
}

func (s *LarkSender) SendFile(ctx context.Context, url string, name string, caption string) error {
	data, err := shared.DownloadFromURL(ctx, url)
	if err != nil {
		slog.Error("lark: file download failed, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, name)
	}
	fileName := name
	if fileName == "" {
		fileName = shared.FilenameFromURL(url)
	}
	fileName = shared.EnsureFileExtension(fileName, data)

	fileKey, err := s.client.UploadFile(ctx, larkclient.FileTypeStream, fileName, data)
	if err != nil {
		slog.Error("lark: file upload failed, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, name)
	}
	if err := s.client.SendFileKey(ctx, s.chatID, fileKey); err != nil {
		slog.Error("lark: file send failed, falling back to text", "error", err)
		return s.sendFallback(ctx, url, name)
	}
	s.sendCaption(ctx, caption)
	return nil
}

func (s *LarkSender) SendCard(ctx context.Context, title, description, imageURL, linkURL, label string) error {
	// A card cover must be an uploaded image_key, not a raw URL. Try to upload
	// it; on any failure just render the card without an image.
	imgKey := ""
	if imageURL != "" {
		if data, err := shared.DownloadFromURL(ctx, imageURL); err == nil {
			if key, upErr := s.client.UploadImage(ctx, data); upErr == nil {
				imgKey = key
			} else {
				slog.Warn("lark: card image upload failed, sending card without image", "error", upErr)
			}
		}
	}

	cardJSON, err := larkclient.RichCard(title, description, imgKey, linkURL, label)
	if err != nil {
		slog.Warn("lark: build card failed, falling back to text", "error", err)
		return s.sendCardText(ctx, title, description, linkURL, label)
	}
	if err := s.client.SendCardJSON(ctx, s.chatID, cardJSON); err != nil {
		slog.Warn("lark: card send failed, falling back to text", "error", err)
		return s.sendCardText(ctx, title, description, linkURL, label)
	}
	return nil
}

// sendCardText renders a card attachment as plain text (mirroring the wechat
// sender's layout) when the interactive card can't be built or sent.
func (s *LarkSender) sendCardText(ctx context.Context, title, description, linkURL, label string) error {
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
	return s.client.SendText(ctx, s.chatID, strings.Join(parts, "\n"))
}

func (s *LarkSender) SendChoice(ctx context.Context, question string, options []string) error {
	cardJSON, err := larkclient.ChoiceCard(question, options)
	if err != nil {
		slog.Warn("lark: build choice card failed, falling back to text", "error", err)
		return s.sendChoiceText(ctx, question, options)
	}
	if err := s.client.SendCardJSON(ctx, s.chatID, cardJSON); err != nil {
		slog.Warn("lark: choice card send failed, falling back to text", "error", err)
		return s.sendChoiceText(ctx, question, options)
	}
	return nil
}

// sendChoiceText renders a choice as a numbered list (users can reply with the
// option text) when the interactive card can't be built or sent.
func (s *LarkSender) sendChoiceText(ctx context.Context, question string, options []string) error {
	var sb strings.Builder
	if question != "" {
		sb.WriteString("❓ " + question + "\n")
	}
	for i, opt := range options {
		sb.WriteString(fmt.Sprintf("%d. %s\n", i+1, opt))
	}
	return s.client.SendText(ctx, s.chatID, strings.TrimRight(sb.String(), "\n"))
}

var _ shared.MessageSender = (*LarkSender)(nil)
