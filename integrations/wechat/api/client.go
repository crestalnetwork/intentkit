package api

import (
	"context"
	"fmt"
	"time"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"resty.dev/v3"
)

type Client struct {
	client  *resty.Client
	baseURL string
}

func NewClient(baseURL string) *Client {
	return &Client{
		client:  resty.New().SetTimeout(10 * time.Minute),
		baseURL: baseURL,
	}
}

// CheckHealth checks if the Core API is reachable.
func (c *Client) CheckHealth() error {
	resp, err := c.client.R().Get(c.baseURL + "/health")
	if err != nil {
		return fmt.Errorf("failed to connect to core api: %w", err)
	}
	if resp.StatusCode() != 200 {
		return fmt.Errorf("core api health check failed with status: %d", resp.StatusCode())
	}
	return nil
}

// StreamWechatTeamLead calls the /core/lead/wechat/stream endpoint with SSE streaming.
func (c *Client) StreamWechatTeamLead(ctx context.Context, payload map[string]interface{}, cb shared.StreamCallback) error {
	return shared.StreamRequest(ctx, c.baseURL, "/core/lead/wechat/stream", payload, cb)
}
