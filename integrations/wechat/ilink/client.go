package ilink

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math/rand/v2"
	"net/http"
	"strconv"
	"time"

	"github.com/rs/xid"
)

const channelVersion = "1.0.2"

// Client communicates with the WeChat iLink Bot API.
type Client struct {
	baseURL    string
	botToken   string
	botID      string
	httpClient *http.Client
	updatesBuf string // cursor for long-polling
}

// NewClient creates an authenticated iLink API client.
func NewClient(baseURL, botToken, botID string) *Client {
	return &Client{
		baseURL:  baseURL,
		botToken: botToken,
		botID:    botID,
		httpClient: &http.Client{
			Timeout: 40 * time.Second,
		},
	}
}

// BotID returns the bot's iLink user ID.
func (c *Client) BotID() string {
	return c.botID
}

// generateWechatUIN generates a random X-WECHAT-UIN header value.
func generateWechatUIN() string {
	n := rand.Uint32()
	return base64.StdEncoding.EncodeToString([]byte(strconv.FormatUint(uint64(n), 10)))
}

// setHeaders applies the required auth headers to an HTTP request.
func (c *Client) setHeaders(req *http.Request) {
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("AuthorizationType", "ilink_bot_token")
	req.Header.Set("X-WECHAT-UIN", generateWechatUIN())
	req.Header.Set("Authorization", "Bearer "+c.botToken)
}

// doPost performs a POST request with JSON body and decodes the JSON response.
func (c *Client) doPost(ctx context.Context, path string, body interface{}, result interface{}) error {
	bodyBytes, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+path, bytes.NewReader(bodyBytes))
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	c.setHeaders(req)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("http request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("read response body: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		slog.Error("iLink API error", "path", path, "status", resp.StatusCode, "body", string(respBody))
		return fmt.Errorf("ilink api returned status %d", resp.StatusCode)
	}

	// Log response for non-getupdates calls (getupdates is too noisy)
	if path != "/ilink/bot/getupdates" {
		slog.Info("iLink API response", "path", path, "body", string(respBody))
	}

	if result != nil {
		if err := json.Unmarshal(respBody, result); err != nil {
			return fmt.Errorf("decode response: %w", err)
		}
	}
	return nil
}

// GetUpdates performs long-polling for new messages.
func (c *Client) GetUpdates(ctx context.Context) ([]WeixinMessage, error) {
	reqBody := GetUpdatesRequest{
		GetUpdatesBuf: c.updatesBuf,
		BaseInfo:      BaseInfo{ChannelVersion: channelVersion},
	}

	var resp GetUpdatesResponse
	if err := c.doPost(ctx, "/ilink/bot/getupdates", reqBody, &resp); err != nil {
		return nil, err
	}

	if resp.Ret != 0 {
		return nil, fmt.Errorf("getupdates returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	c.updatesBuf = resp.GetUpdatesBuf
	return resp.Msgs, nil
}

// SendMessage sends a text reply to a WeChat user.
func (c *Client) SendMessage(ctx context.Context, toUserID, contextToken, text string) error {
	reqBody := SendMessageRequest{
		Msg: SendMsg{
			FromUserID:   c.botID,
			ToUserID:     toUserID,
			ClientID:     xid.New().String(),
			MessageType:  MessageTypeBot,
			MessageState: MessageStateFinish,
			ContextToken: contextToken,
			ItemList: []ItemObj{
				{
					Type:     ItemTypeText,
					TextItem: &TextItem{Text: text},
				},
			},
		},
		BaseInfo: BaseInfo{},
	}

	var resp SendMessageResponse
	if err := c.doPost(ctx, "/ilink/bot/sendmessage", reqBody, &resp); err != nil {
		return err
	}

	if resp.Ret != 0 {
		return fmt.Errorf("sendmessage returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return nil
}

// SendTyping sends a typing indicator to a WeChat user.
func (c *Client) SendTyping(ctx context.Context, userID, typingTicket string) error {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	reqBody := SendTypingRequest{
		ILinkUserID:  userID,
		TypingTicket: typingTicket,
		Status:       1,
		BaseInfo:     BaseInfo{},
	}

	var resp SendTypingResponse
	if err := c.doPost(ctx, "/ilink/bot/sendtyping", reqBody, &resp); err != nil {
		return err
	}

	if resp.Ret != 0 {
		return fmt.Errorf("sendtyping returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return nil
}

// GetConfig retrieves bot configuration including the typing_ticket.
func (c *Client) GetConfig(ctx context.Context, userID, contextToken string) (*GetConfigResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	reqBody := GetConfigRequest{
		ILinkUserID:  userID,
		ContextToken: contextToken,
		BaseInfo:     BaseInfo{},
	}

	var resp GetConfigResponse
	if err := c.doPost(ctx, "/ilink/bot/getconfig", reqBody, &resp); err != nil {
		return nil, err
	}

	if resp.Ret != 0 {
		return nil, fmt.Errorf("getconfig returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return &resp, nil
}
