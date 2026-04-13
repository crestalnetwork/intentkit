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

// uploadAndBuildMedia downloads a file from URL, uploads it to WeChat CDN,
// and returns the CDNMedia reference along with the AES key, file size, and resolved filename.
func (s *WechatSender) uploadAndBuildMedia(ctx context.Context, url string, mediaType int, fileName string) (ilink.CDNMedia, string, int, string, error) {
	data, err := shared.DownloadFromURL(ctx, url)
	if err != nil {
		return ilink.CDNMedia{}, "", 0, "", fmt.Errorf("download file: %w", err)
	}

	fileSize := len(data)
	if fileName == "" {
		fileName = shared.FilenameFromURL(url)
	}
	fileName = shared.EnsureFileExtension(fileName, data)

	uploadResp, err := s.client.GetUploadURL(ctx, mediaType, fileSize, fileName)
	if err != nil {
		return ilink.CDNMedia{}, "", 0, "", fmt.Errorf("get upload url: %w", err)
	}

	encryptQueryParam, err := s.client.UploadToCDN(ctx, uploadResp.UploadParam.UploadURL, uploadResp.UploadParam.FileID, uploadResp.UploadParam.AESKey, data)
	if err != nil {
		return ilink.CDNMedia{}, "", 0, "", fmt.Errorf("upload to cdn: %w", err)
	}

	media := ilink.CDNMedia{
		EncryptQueryParam: encryptQueryParam,
		AESKey:            uploadResp.UploadParam.AESKey,
		EncryptType:       1,
	}

	return media, uploadResp.UploadParam.AESKey, fileSize, fileName, nil
}

func (s *WechatSender) SendImage(ctx context.Context, url string, caption string) error {
	media, aesKey, fileSize, _, err := s.uploadAndBuildMedia(ctx, url, ilink.ItemTypeImage, "")
	if err != nil {
		slog.Error("Failed to upload image to WeChat CDN, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, caption)
	}

	if err := s.client.SendImage(ctx, s.toUserID, s.contextToken, media, aesKey, fileSize); err != nil {
		slog.Error("Failed to send image message, falling back to text", "error", err)
		return s.sendFallback(ctx, url, caption)
	}

	if caption != "" {
		_ = s.SendText(ctx, caption)
	}
	return nil
}

func (s *WechatSender) SendVideo(ctx context.Context, url string, caption string) error {
	media, _, _, _, err := s.uploadAndBuildMedia(ctx, url, ilink.ItemTypeVideo, "")
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
	media, _, fileSize, resolvedName, err := s.uploadAndBuildMedia(ctx, url, ilink.ItemTypeFile, name)
	if err != nil {
		slog.Error("Failed to upload file to WeChat CDN, falling back to text", "error", err, "url", url)
		return s.sendFallback(ctx, url, name)
	}

	if err := s.client.SendFile(ctx, s.toUserID, s.contextToken, resolvedName, media, fileSize); err != nil {
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
