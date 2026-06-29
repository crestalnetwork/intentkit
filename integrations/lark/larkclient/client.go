// Package larkclient wraps the Lark/Feishu open-platform Go SDK with the small
// surface the integration needs: sending messages (text, interactive cards,
// image/file/media), uploading media to obtain image/file keys, and downloading
// inbound message resources. A single client serves both Feishu (China) and
// Lark (international) — the host is chosen per channel via the domain.
package larkclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"time"

	lark "github.com/larksuite/oapi-sdk-go/v3"
	larkcore "github.com/larksuite/oapi-sdk-go/v3/core"
	larkim "github.com/larksuite/oapi-sdk-go/v3/service/im/v1"

	"github.com/crestalnetwork/intentkit/integrations/shared"
)

// Message types and resource/upload kinds used against the IM API.
const (
	msgTypeText        = "text"
	msgTypeImage       = "image"
	msgTypeFile        = "file"
	msgTypeMedia       = "media"
	msgTypeInteractive = "interactive"

	imageTypeMessage = "message"

	// FileTypeStream is the catch-all upload type for arbitrary files.
	FileTypeStream = "stream"
	// FileTypeMP4 uploads a video so it can be sent as an inline media message.
	FileTypeMP4 = "mp4"

	// ResourceTypeImage / ResourceTypeFile select which inbound resource kind
	// to download via the message-resource API (audio/video ride on "file").
	ResourceTypeImage = "image"
	ResourceTypeFile  = "file"
)

// ResolveBaseURL maps a channel domain ("feishu" | "lark") to its open-platform
// host. Unknown/empty values fall back to Feishu.
func ResolveBaseURL(domain string) string {
	switch domain {
	case "lark":
		return lark.LarkBaseUrl
	default:
		return lark.FeishuBaseUrl
	}
}

// Client is a per-tenant wrapper over a shared marketplace (ISV) *lark.Client.
// One marketplace client serves every tenant; each Client binds a tenant_key
// that's attached to every request, so the SDK uses that tenant's access token.
type Client struct {
	lark      *lark.Client
	tenantKey string
}

// NewMarketplaceClient builds the single shared ISV (marketplace) SDK client.
// It auto-manages the app_access_token / tenant_access_token chain once the SDK
// event dispatcher has captured the app_ticket Lark pushes to the webhook.
// debug raises the SDK's own log level.
func NewMarketplaceClient(appID, appSecret, domain string, debug bool) *lark.Client {
	logLevel := larkcore.LogLevelError
	if debug {
		logLevel = larkcore.LogLevelDebug
	}
	return lark.NewClient(appID, appSecret,
		lark.WithMarketplaceApp(),
		lark.WithOpenBaseUrl(ResolveBaseURL(domain)),
		lark.WithLogLevel(logLevel),
		lark.WithReqTimeout(2*time.Minute),
	)
}

// ForTenant binds the shared marketplace client to one tenant_key.
func ForTenant(shared *lark.Client, tenantKey string) *Client {
	return &Client{lark: shared, tenantKey: tenantKey}
}

// sendMessage posts one message of the given type to a chat (receive_id_type =
// chat_id). content is the API-specific JSON payload string.
func (c *Client) sendMessage(ctx context.Context, chatID, msgType, content string) error {
	resp, err := c.lark.Im.Message.Create(ctx, larkim.NewCreateMessageReqBuilder().
		ReceiveIdType("chat_id").
		Body(larkim.NewCreateMessageReqBodyBuilder().
			ReceiveId(chatID).
			MsgType(msgType).
			Content(content).
			Build()).
		Build(), larkcore.WithTenantKey(c.tenantKey))
	if err != nil {
		return fmt.Errorf("send %s: %w", msgType, err)
	}
	if !resp.Success() {
		return fmt.Errorf("send %s: code=%d msg=%s", msgType, resp.Code, resp.Msg)
	}
	return nil
}

// SendText sends a plain-text message. Used as the fallback when a card send
// fails; rich agent output goes through SendCardJSON instead.
func (c *Client) SendText(ctx context.Context, chatID, text string) error {
	content, err := json.Marshal(map[string]string{"text": text})
	if err != nil {
		return err
	}
	return c.sendMessage(ctx, chatID, msgTypeText, string(content))
}

// SendCardJSON sends a pre-built interactive card (see card.go).
func (c *Client) SendCardJSON(ctx context.Context, chatID, cardJSON string) error {
	return c.sendMessage(ctx, chatID, msgTypeInteractive, cardJSON)
}

// sendKeyed sends a message whose content is a single {jsonKey: val} object
// (the shape image/file/media messages share).
func (c *Client) sendKeyed(ctx context.Context, chatID, msgType, jsonKey, val string) error {
	content, err := json.Marshal(map[string]string{jsonKey: val})
	if err != nil {
		return err
	}
	return c.sendMessage(ctx, chatID, msgType, string(content))
}

// SendImageKey sends an image message referencing an already-uploaded key.
func (c *Client) SendImageKey(ctx context.Context, chatID, imageKey string) error {
	return c.sendKeyed(ctx, chatID, msgTypeImage, "image_key", imageKey)
}

// SendFileKey sends a file message referencing an already-uploaded key.
func (c *Client) SendFileKey(ctx context.Context, chatID, fileKey string) error {
	return c.sendKeyed(ctx, chatID, msgTypeFile, "file_key", fileKey)
}

// SendMediaKey sends a video as an inline media message (file uploaded as mp4).
func (c *Client) SendMediaKey(ctx context.Context, chatID, fileKey string) error {
	return c.sendKeyed(ctx, chatID, msgTypeMedia, "file_key", fileKey)
}

// UploadImage uploads image bytes and returns the resulting image_key.
func (c *Client) UploadImage(ctx context.Context, data []byte) (string, error) {
	resp, err := c.lark.Im.Image.Create(ctx, larkim.NewCreateImageReqBuilder().
		Body(larkim.NewCreateImageReqBodyBuilder().
			ImageType(imageTypeMessage).
			Image(bytes.NewReader(data)).
			Build()).
		Build(), larkcore.WithTenantKey(c.tenantKey))
	if err != nil {
		return "", fmt.Errorf("upload image: %w", err)
	}
	if !resp.Success() {
		return "", fmt.Errorf("upload image: code=%d msg=%s", resp.Code, resp.Msg)
	}
	if resp.Data == nil || resp.Data.ImageKey == nil {
		return "", fmt.Errorf("upload image: empty image_key")
	}
	return *resp.Data.ImageKey, nil
}

// UploadFile uploads file bytes and returns the resulting file_key. fileType is
// one of the Lark upload kinds (FileTypeStream, FileTypeMP4, ...).
func (c *Client) UploadFile(ctx context.Context, fileType, fileName string, data []byte) (string, error) {
	resp, err := c.lark.Im.File.Create(ctx, larkim.NewCreateFileReqBuilder().
		Body(larkim.NewCreateFileReqBodyBuilder().
			FileType(fileType).
			FileName(fileName).
			File(bytes.NewReader(data)).
			Build()).
		Build(), larkcore.WithTenantKey(c.tenantKey))
	if err != nil {
		return "", fmt.Errorf("upload file: %w", err)
	}
	if !resp.Success() {
		return "", fmt.Errorf("upload file: code=%d msg=%s", resp.Code, resp.Msg)
	}
	if resp.Data == nil || resp.Data.FileKey == nil {
		return "", fmt.Errorf("upload file: empty file_key")
	}
	return *resp.Data.FileKey, nil
}

// DownloadResource fetches an inbound message resource (image/file/audio/video)
// by message_id + file_key. resType is ResourceTypeImage or ResourceTypeFile.
func (c *Client) DownloadResource(ctx context.Context, messageID, fileKey, resType string) ([]byte, error) {
	resp, err := c.lark.Im.MessageResource.Get(ctx, larkim.NewGetMessageResourceReqBuilder().
		MessageId(messageID).
		FileKey(fileKey).
		Type(resType).
		Build(), larkcore.WithTenantKey(c.tenantKey))
	if err != nil {
		return nil, fmt.Errorf("download resource: %w", err)
	}
	if !resp.Success() {
		return nil, fmt.Errorf("download resource: code=%d msg=%s", resp.Code, resp.Msg)
	}
	if resp.File == nil {
		return nil, fmt.Errorf("download resource: empty body")
	}
	return readLimited(resp.File)
}

// readLimited reads up to MaxMediaSize bytes, erroring if the source exceeds it
// rather than silently truncating (which would corrupt the media).
func readLimited(r io.Reader) ([]byte, error) {
	data, err := io.ReadAll(io.LimitReader(r, shared.MaxMediaSize+1))
	if err != nil {
		return nil, err
	}
	if len(data) > shared.MaxMediaSize {
		return nil, fmt.Errorf("resource exceeds maximum size of %d bytes", shared.MaxMediaSize)
	}
	return data, nil
}
