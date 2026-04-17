package alert

import (
	"context"
	"fmt"

	"resty.dev/v3"
)

// Sender delivers a single alert message to an external channel.
//
// Implementations are expected to be safe for concurrent use; the alert
// pipeline only calls Send from one goroutine, but tests may exercise it
// concurrently.
type Sender interface {
	Send(ctx context.Context, message string) error
}

func newAlertHTTPClient() *resty.Client {
	return resty.New().
		SetTimeout(alertHTTPTimeout).
		SetRetryCount(2).
		SetRetryWaitTime(alertRetryWait).
		SetRetryMaxWaitTime(alertRetryMaxWait)
}

type telegramSender struct {
	client *resty.Client
	url    string
	chatID string
}

func newTelegramSender(token, chatID string) *telegramSender {
	return &telegramSender{
		client: newAlertHTTPClient(),
		url:    fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", token),
		chatID: chatID,
	}
}

func (s *telegramSender) Send(ctx context.Context, message string) error {
	resp, err := s.client.R().
		SetContext(ctx).
		SetBody(map[string]any{
			"chat_id": s.chatID,
			"text":    message,
		}).
		Post(s.url)
	if err != nil {
		return err
	}
	if resp.IsError() {
		return fmt.Errorf("telegram alert failed: %s", resp.Status())
	}
	return nil
}

type slackSender struct {
	client  *resty.Client
	token   string
	channel string
}

func newSlackSender(token, channel string) *slackSender {
	return &slackSender{client: newAlertHTTPClient(), token: token, channel: channel}
}

// slackResponse mirrors the envelope chat.postMessage returns. Slack
// indicates failure via {"ok": false, "error": "..."} on an HTTP 200, so
// we have to inspect the body — IsError() alone misses bad tokens, wrong
// channels, and most other API rejections.
type slackResponse struct {
	OK    bool   `json:"ok"`
	Error string `json:"error"`
}

func (s *slackSender) Send(ctx context.Context, message string) error {
	var body slackResponse
	resp, err := s.client.R().
		SetContext(ctx).
		SetAuthToken(s.token).
		SetBody(map[string]any{
			"channel": s.channel,
			"text":    message,
		}).
		SetResult(&body).
		Post("https://slack.com/api/chat.postMessage")
	if err != nil {
		return err
	}
	if resp.IsError() {
		return fmt.Errorf("slack alert failed: %s", resp.Status())
	}
	if !body.OK {
		return fmt.Errorf("slack alert rejected: %s", body.Error)
	}
	return nil
}
