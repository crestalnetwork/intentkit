package bot

import (
	"context"
	"fmt"
	"log/slog"
	"strings"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/wechat/ilink"
)

type WechatSender struct {
	client       *ilink.Client
	toUserID     string
	contextToken string
}

func NewWechatSender(client *ilink.Client, toUserID, contextToken string) *WechatSender {
	return &WechatSender{
		client:       client,
		toUserID:     toUserID,
		contextToken: contextToken,
	}
}

func (s *WechatSender) SendText(ctx context.Context, text string) error {
	return s.client.SendMessage(ctx, s.toUserID, s.contextToken, text)
}

// sendFallback sends a URL as plain text when media upload/send fails.
func (s *WechatSender) sendFallback(ctx context.Context, url, prefix string) error {
	text := url
	if prefix != "" {
		text = prefix + "\n" + url
	}
	return s.client.SendMessage(ctx, s.toUserID, s.contextToken, text)
}

// downloadAndUpload downloads a file from URL and uploads it to WeChat CDN.
// Returns the raw data, CDNMedia reference, and ciphertext size.
func (s *WechatSender) downloadAndUpload(ctx context.Context, fileURL string, uploadMediaType int) ([]byte, ilink.CDNMedia, int, error) {
	data, err := shared.DownloadFromURL(ctx, fileURL)
	if err != nil {
		return nil, ilink.CDNMedia{}, 0, fmt.Errorf("download: %w", err)
	}

	media, ciphertextSize, err := s.client.UploadMedia(ctx, data, uploadMediaType, s.toUserID)
	if err != nil {
		return nil, ilink.CDNMedia{}, 0, fmt.Errorf("upload: %w", err)
	}

	return data, media, ciphertextSize, nil
}

func (s *WechatSender) SendImage(ctx context.Context, url string, caption string) error {
	_, media, ciphertextSize, err := s.downloadAndUpload(ctx, url, ilink.UploadMediaImage)
	if err != nil {
		slog.Error("Failed to upload image to WeChat CDN, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, caption)
	}

	if err := s.client.SendImage(ctx, s.toUserID, s.contextToken, media, ciphertextSize); err != nil {
		slog.Error("Failed to send image message, falling back to text", "error", err)
		return s.sendFallback(ctx, url, caption)
	}

	if caption != "" {
		_ = s.SendText(ctx, caption)
	}
	return nil
}

func (s *WechatSender) SendVideo(ctx context.Context, url string, caption string) error {
	_, media, _, err := s.downloadAndUpload(ctx, url, ilink.UploadMediaVideo)
	if err != nil {
		slog.Error("Failed to upload video to WeChat CDN, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, caption)
	}

	if err := s.client.SendVideo(ctx, s.toUserID, s.contextToken, media); err != nil {
		slog.Error("Failed to send video message, falling back to text", "error", err)
		return s.sendFallback(ctx, url, caption)
	}

	if caption != "" {
		_ = s.SendText(ctx, caption)
	}
	return nil
}

func (s *WechatSender) SendFile(ctx context.Context, url string, name string, caption string) error {
	data, media, ciphertextSize, err := s.downloadAndUpload(ctx, url, ilink.UploadMediaFile)
	if err != nil {
		slog.Error("Failed to upload file to WeChat CDN, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, name)
	}

	fileName := name
	if fileName == "" {
		fileName = shared.FilenameFromURL(url)
	}
	fileName = shared.EnsureFileExtension(fileName, data)

	if err := s.client.SendFile(ctx, s.toUserID, s.contextToken, fileName, media, ciphertextSize); err != nil {
		slog.Error("Failed to send file message, falling back to text", "error", err)
		return s.sendFallback(ctx, url, name)
	}

	if caption != "" {
		_ = s.SendText(ctx, caption)
	}
	return nil
}

func (s *WechatSender) SendCard(ctx context.Context, title, description, imageURL, linkURL, label string) error {
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
	return s.SendText(ctx, strings.Join(parts, "\n"))
}

func (s *WechatSender) SendChoice(ctx context.Context, question string, options []string) error {
	var sb strings.Builder
	if question != "" {
		sb.WriteString("❓ " + question + "\n")
	}
	for i, opt := range options {
		sb.WriteString(fmt.Sprintf("%d. %s\n", i+1, opt))
	}
	return s.SendText(ctx, strings.TrimRight(sb.String(), "\n"))
}

var _ shared.MessageSender = (*WechatSender)(nil)
