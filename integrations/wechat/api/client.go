package api

import (
	"fmt"
	"log/slog"
	"time"

	"github.com/crestalnetwork/intentkit/integrations/types"
	"github.com/go-resty/resty/v2"
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

// ExecuteWechatTeamLead calls the /core/lead/wechat/execute endpoint.
func (c *Client) ExecuteWechatTeamLead(payload map[string]interface{}) ([]types.ChatMessage, error) {
	var result []types.ChatMessage
	resp, err := c.client.R().
		SetHeader("Content-Type", "application/json").
		SetBody(payload).
		SetResult(&result).
		Post(c.baseURL + "/core/lead/wechat/execute")

	if err != nil {
		return nil, fmt.Errorf("failed to execute wechat team lead: %w", err)
	}

	if resp.IsError() {
		slog.Error("Core API returned error for wechat team lead", "status", resp.StatusCode(), "body", string(resp.Body()))
		return nil, fmt.Errorf("core api returned error status: %d", resp.StatusCode())
	}

	return result, nil
}
