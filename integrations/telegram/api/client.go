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

// CheckHealth checks if the Core API is reachable
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

// StreamAgent calls the /core/stream endpoint with SSE streaming.
func (c *Client) StreamAgent(ctx context.Context, payload map[string]interface{}, cb shared.StreamCallback) error {
	return shared.StreamRequest(ctx, c.baseURL, "/core/stream", payload, cb)
}

// StreamTeamLead calls the /core/lead/stream endpoint with SSE streaming.
func (c *Client) StreamTeamLead(ctx context.Context, payload map[string]interface{}, cb shared.StreamCallback) error {
	return shared.StreamRequest(ctx, c.baseURL, "/core/lead/stream", payload, cb)
}

// BindChannelChat binds a chat to the team that owns bindToken and returns the
// resolved team_id. An empty string (no error) means the token didn't match an
// enabled centralized channel (treat as "not bound").
func (c *Client) BindChannelChat(ctx context.Context, channelType, chatID, chatName, bindToken string) (string, error) {
	var out struct {
		TeamID string `json:"team_id"`
	}
	resp, err := c.client.R().
		SetContext(ctx).
		SetBody(map[string]interface{}{
			"channel_type": channelType,
			"chat_id":      chatID,
			"chat_name":    chatName,
			"bind_token":   bindToken,
		}).
		SetResult(&out).
		Post(c.baseURL + "/core/lead/channel-bind")
	if err != nil {
		return "", fmt.Errorf("channel bind: %w", err)
	}
	if resp.StatusCode() == 404 {
		return "", nil
	}
	if resp.StatusCode() != 200 {
		return "", fmt.Errorf("channel bind: status %d", resp.StatusCode())
	}
	return out.TeamID, nil
}

// SetPushChannel sets (or conditionally sets) the push channel for a team.
func (c *Client) SetPushChannel(ctx context.Context, teamID, channelType, chatID string, ifEmpty bool) error {
	resp, err := c.client.R().
		SetContext(ctx).
		SetBody(map[string]interface{}{
			"team_id":      teamID,
			"channel_type": channelType,
			"chat_id":      chatID,
			"if_empty":     ifEmpty,
		}).
		Post(c.baseURL + "/core/lead/set-push-channel")
	if err != nil {
		return fmt.Errorf("set push channel: %w", err)
	}
	if resp.StatusCode() != 200 {
		return fmt.Errorf("set push channel: status %d", resp.StatusCode())
	}
	return nil
}
