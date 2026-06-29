// Package slackclient wraps the slack-go Web API client with the small surface
// the integration needs: posting messages (plain text and Block Kit), uploading
// outbound media to a channel, and downloading inbound file attachments. The
// Socket Mode (long-connection) client that receives events lives in the bot
// manager; this wrapper only covers the outbound REST calls, and shares the
// same underlying *slack.Client so a single bot token authenticates both.
package slackclient

import (
	"bytes"
	"context"
	"fmt"

	"github.com/slack-go/slack"

	"github.com/crestalnetwork/intentkit/integrations/shared"
)

// Client is a thin wrapper over *slack.Client bound to one workspace bot token.
type Client struct {
	api *slack.Client
}

// NewFromAPI wraps an existing *slack.Client (shared with the Socket Mode
// client) so both outbound REST and inbound events use one authenticated client.
func NewFromAPI(api *slack.Client) *Client {
	return &Client{api: api}
}

// PostText posts a plain-text message. Used as the fallback when a Block Kit
// send fails; rich agent output goes through PostBlocks instead.
func (c *Client) PostText(ctx context.Context, channelID, text string) error {
	_, _, err := c.api.PostMessageContext(ctx, channelID, slack.MsgOptionText(text, false))
	if err != nil {
		return fmt.Errorf("post text: %w", err)
	}
	return nil
}

// PostBlocks posts a Block Kit message. fallbackText is the notification/
// accessibility preview shown where blocks can't render (push notifications,
// screen readers); it should be the plain-text form of the same content.
func (c *Client) PostBlocks(ctx context.Context, channelID, fallbackText string, blocks []slack.Block) error {
	_, _, err := c.api.PostMessageContext(ctx, channelID,
		slack.MsgOptionBlocks(blocks...),
		slack.MsgOptionText(fallbackText, false),
	)
	if err != nil {
		return fmt.Errorf("post blocks: %w", err)
	}
	return nil
}

// UploadMedia uploads bytes to a channel via the external-upload flow
// (get URL → PUT bytes → complete). Slack retired the single-shot files.upload
// API in 2025, so this three-step flow is the supported path. caption becomes
// the message posted alongside the file.
func (c *Client) UploadMedia(ctx context.Context, channelID, fileName, caption string, data []byte) error {
	up, err := c.api.GetUploadURLExternalContext(ctx, slack.GetUploadURLExternalParameters{
		FileName: fileName,
		FileSize: len(data),
	})
	if err != nil {
		return fmt.Errorf("get upload url: %w", err)
	}
	if err := c.api.UploadToURL(ctx, slack.UploadToURLParameters{
		UploadURL: up.UploadURL,
		Reader:    bytes.NewReader(data),
		Filename:  fileName,
	}); err != nil {
		return fmt.Errorf("upload to url: %w", err)
	}
	if _, err := c.api.CompleteUploadExternalContext(ctx, slack.CompleteUploadExternalParameters{
		Files:          []slack.FileSummary{{ID: up.FileID, Title: fileName}},
		Channel:        channelID,
		InitialComment: caption,
	}); err != nil {
		return fmt.Errorf("complete upload: %w", err)
	}
	return nil
}

// DownloadFile downloads an inbound file's private URL using the bot token
// (the slack-go client adds the Authorization header), capped at MaxMediaSize
// so an oversized file errors rather than exhausting memory. sizeHint (the
// file's reported size, 0 if unknown) pre-sizes the buffer to avoid repeated
// regrowth on large files.
func (c *Client) DownloadFile(ctx context.Context, urlPrivateDownload string, sizeHint int) ([]byte, error) {
	w := &cappedWriter{limit: shared.MaxMediaSize}
	if sizeHint > 0 && sizeHint <= shared.MaxMediaSize {
		w.buf.Grow(sizeHint)
	}
	if err := c.api.GetFileContext(ctx, urlPrivateDownload, w); err != nil {
		return nil, fmt.Errorf("download file: %w", err)
	}
	return w.buf.Bytes(), nil
}

// cappedWriter accumulates bytes in memory but errors once more than limit
// bytes are written, so a runaway download can't exhaust memory.
type cappedWriter struct {
	buf   bytes.Buffer
	limit int
}

func (w *cappedWriter) Write(p []byte) (int, error) {
	if w.buf.Len()+len(p) > w.limit {
		return 0, fmt.Errorf("resource exceeds maximum size of %d bytes", w.limit)
	}
	return w.buf.Write(p)
}
