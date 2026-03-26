# Rich Media Messaging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable Telegram and WeChat Go integrations to send rich media (images, videos, files, cards, choices) and real-time skill status via SSE streaming.

**Architecture:** Merge three Go modules into one at `integrations/`, add shared SSE client and message dispatcher, implement platform-specific senders via a common interface. Add SSE streaming lead endpoints on the Python side.

**Tech Stack:** Go 1.26, resty v3 (SSE), telego (Telegram Bot API), iLink Bot API (WeChat), FastAPI SSE (Python)

---

## Task 1: Merge Go Modules into Single Module

Consolidate `integrations/telegram/`, `integrations/wechat/`, `integrations/types/` into one Go module.

**Files:**
- Create: `integrations/go.mod`
- Create: `integrations/go.sum`
- Create: `integrations/cmd/telegram/main.go` (move from `integrations/telegram/main.go`)
- Create: `integrations/cmd/wechat/main.go` (move from `integrations/wechat/main.go`)
- Delete: `integrations/telegram/main.go`
- Delete: `integrations/wechat/main.go`
- Delete: `integrations/telegram/go.mod`, `integrations/telegram/go.sum`
- Delete: `integrations/wechat/go.mod`, `integrations/wechat/go.sum`
- Delete: `integrations/types/go.mod`
- Modify: `integrations/Dockerfile.dev`
- Create: `integrations/Dockerfile.telegram` (rename from `integrations/telegram/Dockerfile`)
- Create: `integrations/Dockerfile.wechat` (rename from `integrations/wechat/Dockerfile`)
- Delete: `integrations/telegram/Dockerfile`, `integrations/wechat/Dockerfile`
- Modify: `docker-compose.yml:206-260` (update volume mounts and build paths)
- Modify: all `.go` files with import path changes

**Step 1: Create unified go.mod**

```
cd integrations
```

Create `integrations/go.mod` with module name `github.com/crestalnetwork/intentkit/integrations`. Merge dependencies from both `telegram/go.mod` and `wechat/go.mod`. Remove all `replace` directives.

**Step 2: Move main.go files to cmd/**

```bash
mkdir -p integrations/cmd/telegram integrations/cmd/wechat
mv integrations/telegram/main.go integrations/cmd/telegram/main.go
mv integrations/wechat/main.go integrations/cmd/wechat/main.go
```

Update import paths in both `cmd/*/main.go`:
- `cmd/telegram/main.go`: Change imports from `github.com/crestalnetwork/intentkit/integrations/telegram/...` — these stay the same since the package paths within the module are unchanged.
- `cmd/wechat/main.go`: Same — imports stay the same.

**Step 3: Update all internal imports**

In every `.go` file under `integrations/telegram/` and `integrations/wechat/`:
- Remove the `replace` directive import workaround — `types` package import path `github.com/crestalnetwork/intentkit/integrations/types` stays the same but now resolves within the single module.

**Step 4: Delete old module files**

```bash
rm integrations/telegram/go.mod integrations/telegram/go.sum
rm integrations/wechat/go.mod integrations/wechat/go.sum
rm integrations/types/go.mod
rm integrations/telegram/Dockerfile integrations/wechat/Dockerfile
```

**Step 5: Update Dockerfiles**

Create `integrations/Dockerfile.telegram`:
```dockerfile
FROM golang:1.26-alpine AS builder
WORKDIR /app
RUN apk add --no-cache git
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o intent-telegram ./cmd/telegram

FROM alpine:latest
ARG RELEASE=local
ENV RELEASE=${RELEASE}
WORKDIR /app
RUN apk --no-cache add ca-certificates tzdata
COPY --from=builder /app/intent-telegram .
ENV TG_NEW_AGENT_POLL_INTERVAL=10
CMD ["./intent-telegram"]
```

Create `integrations/Dockerfile.wechat` (same pattern, `./cmd/wechat`, binary `intent-wechat`, env `WX_NEW_CHANNEL_POLL_INTERVAL=10`).

Update `integrations/Dockerfile.dev`:
```dockerfile
FROM golang:1.26-alpine
ARG SERVICE
RUN apk add --no-cache git
RUN go install github.com/air-verse/air@latest
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
CMD ["air", "-c", ".air.${SERVICE}.toml"]
```

Create `integrations/.air.telegram.toml`:
```toml
root = "."
tmp_dir = "tmp/telegram"

[build]
  cmd = "go build -o ./tmp/telegram/intent-telegram ./cmd/telegram"
  bin = "./tmp/telegram/intent-telegram"
  delay = 1000
  exclude_dir = ["tmp"]
  exclude_regex = ["_test\\.go"]
  include_ext = ["go", "mod", "sum"]
  poll = true
  poll_interval = 2000

[log]
  time = false

[misc]
  clean_on_exit = true
```

Create `integrations/.air.wechat.toml` (same pattern, `wechat` paths, binary `intent-wechat`).

Delete old `.air.toml` files from `integrations/telegram/` and `integrations/wechat/`.

**Step 6: Update docker-compose.yml**

For the `telegram` service (lines 206-236):
```yaml
  telegram:
    build:
      context: ./integrations
      dockerfile: Dockerfile.dev
      args:
        SERVICE: telegram
    volumes:
      - ./integrations:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      api:
        condition: service_healthy
    environment:
      - DB_HOST=db
      - DB_PORT=5432
      - DB_USERNAME=postgres
      - DB_PASSWORD=postgres
      - DB_NAME=intentkit
      - REDIS_HOST=redis
      - INTERNAL_BASE_URL=http://api:8000
      - TG_NEW_AGENT_POLL_INTERVAL=10
    healthcheck:
      test: ["CMD", "find", "/tmp/healthy", "-mmin", "-2"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped
```

For `wechat` service (lines 238+): same pattern, `SERVICE: wechat`.

**Step 7: Run go mod tidy and verify build**

```bash
cd integrations
go mod tidy
go build ./cmd/telegram
go build ./cmd/wechat
```

**Step 8: Commit**

```bash
git add -A integrations/ docker-compose.yml
git commit -m "refactor: merge Go integrations into single module"
```

---

## Task 2: Add Python SSE Streaming Lead Endpoints

Add streaming versions of the team lead endpoints.

**Files:**
- Modify: `intentkit/core/api.py:140-221`

**Step 1: Add `/core/lead/stream` endpoint**

Add after the existing `/core/lead/execute` endpoint (after line 173 in `intentkit/core/api.py`):

```python
@core_router.post("/lead/stream")
async def stream_team_lead(
    request: TeamLeadExecuteRequest = Body(...),
) -> StreamingResponse:
    """Stream the team lead agent execution for a Telegram team channel message."""
    user = await User.get_by_telegram_id(request.telegram_id)
    if not user:
        raise IntentKitAPIError(
            403, "Forbidden", "Telegram user not bound to any IntentKit account"
        )

    await verify_team_membership(request.team_id, user.id)

    chat_msg = ChatMessageCreate(
        id=str(XID()),
        agent_id=request.team_id,
        chat_id=f"tg_team:{request.team_id}:{request.chat_id}",
        user_id=user.id,
        author_id=user.id,
        author_type=AuthorType.TELEGRAM,
        thread_type=AuthorType.TELEGRAM,
        message=request.message,
    )

    async def generate():
        async for chat_message in stream_lead(request.team_id, user.id, chat_msg):
            yield f"event: message\ndata: {chat_message.model_dump_json()}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

**Step 2: Add `/core/lead/wechat/stream` endpoint**

Add after the existing `/core/lead/wechat/execute` endpoint (after line 220):

```python
@core_router.post("/lead/wechat/stream")
async def stream_wechat_team_lead(
    request: WechatLeadExecuteRequest = Body(...),
) -> StreamingResponse:
    """Stream the team lead agent execution for a WeChat team channel message."""
    user = await User.get_by_wechat_id(request.wechat_user_id)
    if not user:
        from intentkit.models.team import Team

        owner_id = await Team.get_owner(request.team_id)
        if owner_id:
            await UserUpdate.model_validate(
                {"wechat_id": request.wechat_user_id}
            ).patch(owner_id)
            user = await User.get(owner_id)

    if user:
        user_id = user.id
        await verify_team_membership(request.team_id, user_id)
    else:
        user_id = request.wechat_user_id

    chat_msg = ChatMessageCreate(
        id=str(XID()),
        agent_id=request.team_id,
        chat_id=f"wx_team:{request.team_id}:{request.chat_id}",
        user_id=user_id,
        author_id=user_id,
        author_type=AuthorType.WECHAT,
        thread_type=AuthorType.WECHAT,
        message=request.message,
    )

    async def generate():
        async for chat_message in stream_lead(request.team_id, user_id, chat_msg):
            yield f"event: message\ndata: {chat_message.model_dump_json()}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

**Step 3: Lint and verify**

```bash
ruff format intentkit/core/api.py
ruff check --fix intentkit/core/api.py
```

**Step 4: Commit**

```bash
git add intentkit/core/api.py
git commit -m "feat: add SSE streaming lead endpoints for Telegram and WeChat"
```

---

## Task 3: Upgrade to Resty v3 and Implement SSE Client

Replace resty v2 with v3 for SSE support. Create shared SSE stream client.

**Files:**
- Modify: `integrations/go.mod` (upgrade resty)
- Create: `integrations/shared/sse.go`
- Modify: `integrations/telegram/api/client.go`
- Modify: `integrations/wechat/api/client.go`

**Step 1: Upgrade resty in go.mod**

```bash
cd integrations
go get github.com/go-resty/resty/v3@latest
go mod tidy
```

**Step 2: Create `integrations/shared/sse.go`**

```go
package shared

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"github.com/crestalnetwork/intentkit/integrations/types"
	"github.com/go-resty/resty/v3"
)

// StreamCallback is called for each ChatMessage received from the SSE stream.
type StreamCallback func(msg types.ChatMessage) error

// StreamRequest sends a POST request to the given URL with the payload,
// reads the SSE stream, and calls the callback for each ChatMessage event.
func StreamRequest(ctx context.Context, baseURL, path string, payload interface{}, cb StreamCallback) error {
	client := resty.New().SetTimeout(10 * time.Minute)

	resp, err := client.R().
		SetContext(ctx).
		SetHeader("Content-Type", "application/json").
		SetBody(payload).
		SetDoNotParseResponse(true).
		Post(baseURL + path)

	if err != nil {
		return fmt.Errorf("stream request failed: %w", err)
	}
	defer resp.RawBody().Close()

	if resp.StatusCode() != 200 {
		return fmt.Errorf("stream request returned status %d", resp.StatusCode())
	}

	// Parse SSE stream line by line
	return parseSSEStream(resp.RawBody(), cb)
}
```

Note: The exact resty v3 SSE API should be checked during implementation. Resty v3 may provide a built-in SSE event reader (e.g., `SetResultAs(resty.SSE)` or similar). If so, use that instead of manual parsing. If not, implement manual SSE parsing with `bufio.Scanner`:

```go
func parseSSEStream(reader io.Reader, cb StreamCallback) error {
	scanner := bufio.NewScanner(reader)
	var dataLine string

	for scanner.Scan() {
		line := scanner.Text()

		if strings.HasPrefix(line, "data: ") {
			dataLine = strings.TrimPrefix(line, "data: ")
		} else if line == "" && dataLine != "" {
			// Empty line = end of event
			var msg types.ChatMessage
			if err := json.Unmarshal([]byte(dataLine), &msg); err != nil {
				slog.Error("Failed to parse SSE message", "error", err, "data", dataLine)
				dataLine = ""
				continue
			}
			if err := cb(msg); err != nil {
				slog.Error("Callback error", "error", err)
			}
			dataLine = ""
		}
	}

	return scanner.Err()
}
```

**Step 3: Update `integrations/telegram/api/client.go`**

Upgrade resty import from v2 to v3. Keep existing `ExecuteAgent` and `ExecuteTeamLead` for now (they still work, will be replaced in Task 5). Add streaming methods:

```go
// StreamAgent calls /core/stream with SSE
func (c *Client) StreamAgent(ctx context.Context, payload map[string]interface{}, cb shared.StreamCallback) error {
	return shared.StreamRequest(ctx, c.baseURL, "/core/stream", payload, cb)
}

// StreamTeamLead calls /core/lead/stream with SSE
func (c *Client) StreamTeamLead(ctx context.Context, payload map[string]interface{}, cb shared.StreamCallback) error {
	return shared.StreamRequest(ctx, c.baseURL, "/core/lead/stream", payload, cb)
}
```

**Step 4: Update `integrations/wechat/api/client.go`**

Same resty v2→v3 upgrade. Add streaming method:

```go
// StreamWechatTeamLead calls /core/lead/wechat/stream with SSE
func (c *Client) StreamWechatTeamLead(ctx context.Context, payload map[string]interface{}, cb shared.StreamCallback) error {
	return shared.StreamRequest(ctx, c.baseURL, "/core/lead/wechat/stream", payload, cb)
}
```

**Step 5: Verify build**

```bash
cd integrations
go build ./cmd/telegram
go build ./cmd/wechat
```

**Step 6: Commit**

```bash
git add integrations/
git commit -m "feat: add SSE stream client with resty v3"
```

---

## Task 4: Create Shared Message Dispatcher

Implement the common message dispatch logic that routes ChatMessages to platform-specific senders.

**Files:**
- Create: `integrations/shared/dispatcher.go`
- Create: `integrations/shared/media.go`

**Step 1: Create `integrations/shared/dispatcher.go`**

```go
package shared

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/crestalnetwork/intentkit/integrations/types"
)

// MessageSender is the interface each platform implements.
type MessageSender interface {
	SendText(ctx context.Context, text string) error
	SendImage(ctx context.Context, url string, caption string) error
	SendVideo(ctx context.Context, url string, caption string) error
	SendFile(ctx context.Context, url string, name string, caption string) error
	SendCard(ctx context.Context, title, description, imageURL, linkURL, label string) error
	SendChoice(ctx context.Context, question string, options []string) error
}

// DispatchMessage routes a ChatMessage to the appropriate sender method.
func DispatchMessage(ctx context.Context, msg types.ChatMessage, sender MessageSender) {
	switch msg.AuthorType {
	case "thinking":
		// Ignore thinking messages
		return

	case "skill":
		// Send "Running xxx..." for each skill call
		if len(msg.SkillCalls) > 0 {
			text := fmt.Sprintf("🔧 Running %s...", msg.SkillCalls[0].Name)
			if err := sender.SendText(ctx, text); err != nil {
				slog.Error("Failed to send skill status", "error", err)
			}
		}

	case "system":
		if msg.Message == "" {
			return
		}
		var text string
		if msg.ErrorType != nil && *msg.ErrorType != "" {
			text = "❌ " + msg.Message
		} else {
			text = "ℹ️ " + msg.Message
		}
		if err := sender.SendText(ctx, text); err != nil {
			slog.Error("Failed to send system message", "error", err)
		}

	case "agent":
		// Send text if present
		if msg.Message != "" {
			if err := sender.SendText(ctx, msg.Message); err != nil {
				slog.Error("Failed to send agent text", "error", err)
			}
		}
		// Process attachments
		for _, att := range msg.Attachments {
			dispatchAttachment(ctx, att, sender)
		}

	default:
		slog.Warn("Unknown author_type in dispatch", "author_type", msg.AuthorType)
	}
}

func dispatchAttachment(ctx context.Context, att types.ChatMessageAttach, sender MessageSender) {
	switch att.Type {
	case "image":
		url := ""
		if att.URL != nil {
			url = *att.URL
		}
		caption := ""
		if att.LeadText != nil {
			caption = *att.LeadText
		}
		if url != "" {
			if err := sender.SendImage(ctx, url, caption); err != nil {
				slog.Error("Failed to send image", "error", err)
			}
		}

	case "video":
		url := ""
		if att.URL != nil {
			url = *att.URL
		}
		caption := ""
		if att.LeadText != nil {
			caption = *att.LeadText
		}
		if url != "" {
			if err := sender.SendVideo(ctx, url, caption); err != nil {
				slog.Error("Failed to send video", "error", err)
			}
		}

	case "file":
		url := ""
		if att.URL != nil {
			url = *att.URL
		}
		name := ""
		if n, ok := att.JSON["name"]; ok {
			if s, ok := n.(string); ok {
				name = s
			}
		}
		caption := ""
		if att.LeadText != nil {
			caption = *att.LeadText
		}
		if url != "" {
			if err := sender.SendFile(ctx, url, name, caption); err != nil {
				slog.Error("Failed to send file", "error", err)
			}
		}

	case "card":
		title, _ := att.JSON["title"].(string)
		description, _ := att.JSON["description"].(string)
		imageURL, _ := att.JSON["image_url"].(string)
		linkURL, _ := att.JSON["link"].(string)
		label, _ := att.JSON["label"].(string)
		if err := sender.SendCard(ctx, title, description, imageURL, linkURL, label); err != nil {
			slog.Error("Failed to send card", "error", err)
		}

	case "choice":
		question, _ := att.JSON["question"].(string)
		optionsRaw, _ := att.JSON["options"].([]interface{})
		options := make([]string, 0, len(optionsRaw))
		for _, o := range optionsRaw {
			if s, ok := o.(string); ok {
				options = append(options, s)
			}
		}
		if err := sender.SendChoice(ctx, question, options); err != nil {
			slog.Error("Failed to send choice", "error", err)
		}

	case "link", "xmtp":
		// Skip
	}
}
```

**Step 2: Create `integrations/shared/media.go`**

```go
package shared

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"time"
)

// DownloadFromURL downloads a file from the given URL and returns its bytes.
// Used by WeChat to re-upload media to its own CDN.
func DownloadFromURL(ctx context.Context, url string) ([]byte, error) {
	client := &http.Client{Timeout: 2 * time.Minute}
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create download request: %w", err)
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("download from url: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("download returned status %d", resp.StatusCode)
	}

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read download body: %w", err)
	}
	return data, nil
}
```

**Step 3: Verify build**

```bash
cd integrations && go build ./shared/...
```

**Step 4: Commit**

```bash
git add integrations/shared/
git commit -m "feat: add shared message dispatcher and media download helper"
```

---

## Task 5: Implement Telegram Rich Media Sender

Implement the `MessageSender` interface for Telegram and switch handlers to SSE streaming.

**Files:**
- Create: `integrations/telegram/bot/sender.go`
- Modify: `integrations/telegram/bot/handler.go`
- Modify: `integrations/telegram/bot/manager.go:169-175,275-281` (update loop to handle CallbackQuery)

**Step 1: Create `integrations/telegram/bot/sender.go`**

```go
package bot

import (
	"context"
	"fmt"

	"github.com/mymmrac/telego"
	tu "github.com/mymmrac/telego/telegoutil"
)

// TelegramSender implements shared.MessageSender for Telegram.
type TelegramSender struct {
	bot    *telego.Bot
	chatID int64
}

func NewTelegramSender(bot *telego.Bot, chatID int64) *TelegramSender {
	return &TelegramSender{bot: bot, chatID: chatID}
}

func (s *TelegramSender) SendText(ctx context.Context, text string) error {
	_, err := s.bot.SendMessage(ctx, tu.Message(tu.ID(s.chatID), text))
	return err
}

func (s *TelegramSender) SendImage(ctx context.Context, url string, caption string) error {
	photo := &telego.SendPhotoParams{
		ChatID: tu.ID(s.chatID),
		Photo:  telego.InputFile{URL: url},
	}
	if caption != "" {
		photo.Caption = caption
	}
	_, err := s.bot.SendPhoto(ctx, photo)
	return err
}

func (s *TelegramSender) SendVideo(ctx context.Context, url string, caption string) error {
	video := &telego.SendVideoParams{
		ChatID: tu.ID(s.chatID),
		Video:  telego.InputFile{URL: url},
	}
	if caption != "" {
		video.Caption = caption
	}
	_, err := s.bot.SendVideo(ctx, video)
	return err
}

func (s *TelegramSender) SendFile(ctx context.Context, url string, name string, caption string) error {
	doc := &telego.SendDocumentParams{
		ChatID:   tu.ID(s.chatID),
		Document: telego.InputFile{URL: url},
	}
	if caption != "" {
		doc.Caption = caption
	}
	_, err := s.bot.SendDocument(ctx, doc)
	return err
}

func (s *TelegramSender) SendCard(ctx context.Context, title, description, imageURL, linkURL, label string) error {
	text := ""
	if title != "" {
		text = fmt.Sprintf("*%s*", title)
	}
	if description != "" {
		if text != "" {
			text += "\n"
		}
		text += description
	}

	// Build optional inline keyboard with link button
	var keyboard *telego.InlineKeyboardMarkup
	if linkURL != "" {
		btnLabel := label
		if btnLabel == "" {
			btnLabel = "View"
		}
		keyboard = &telego.InlineKeyboardMarkup{
			InlineKeyboard: [][]telego.InlineKeyboardButton{
				{telego.InlineKeyboardButton{Text: btnLabel, URL: linkURL}},
			},
		}
	}

	if imageURL != "" {
		// Send as photo with caption
		photo := &telego.SendPhotoParams{
			ChatID:    tu.ID(s.chatID),
			Photo:     telego.InputFile{URL: imageURL},
			Caption:   text,
			ParseMode: telego.ModeMarkdown,
		}
		if keyboard != nil {
			photo.ReplyMarkup = keyboard
		}
		_, err := s.bot.SendPhoto(ctx, photo)
		return err
	}

	// Send as text message
	msg := &telego.SendMessageParams{
		ChatID:    tu.ID(s.chatID),
		Text:      text,
		ParseMode: telego.ModeMarkdown,
	}
	if keyboard != nil {
		msg.ReplyMarkup = keyboard
	}
	_, err := s.bot.SendMessage(ctx, msg)
	return err
}

func (s *TelegramSender) SendChoice(ctx context.Context, question string, options []string) error {
	buttons := make([][]telego.InlineKeyboardButton, len(options))
	for i, opt := range options {
		buttons[i] = []telego.InlineKeyboardButton{
			{Text: opt, CallbackData: opt},
		}
	}

	msg := &telego.SendMessageParams{
		ChatID: tu.ID(s.chatID),
		Text:   question,
		ReplyMarkup: &telego.InlineKeyboardMarkup{
			InlineKeyboard: buttons,
		},
	}
	_, err := s.bot.SendMessage(ctx, msg)
	return err
}
```

Note: Check the exact telego API for `SendPhoto`, `SendVideo`, `SendDocument` param structs. The above uses the expected struct-based API — verify field names match telego v1.7.0.

**Step 2: Rewrite `integrations/telegram/bot/handler.go`**

Replace the entire file. Both `handleMessage` and `handleTeamMessage` now use SSE streaming + shared dispatcher:

```go
package bot

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/types"
	"github.com/mymmrac/telego"
	tu "github.com/mymmrac/telego/telegoutil"
	"github.com/rs/xid"
)

func (m *Manager) handleMessage(bot *telego.Bot, message telego.Message, agentID string) {
	if message.Text == "" {
		return
	}

	slog.Info("Received message", "agent_id", agentID, "chat_id", message.Chat.ID)
	_ = bot.SendChatAction(context.Background(), tu.ChatAction(tu.ID(message.Chat.ID), telego.ChatActionTyping))

	userID := fmt.Sprintf("%d", message.From.ID)
	if message.From.Username != "" {
		userID = message.From.Username
	}

	payload := map[string]interface{}{
		"id":          xid.New().String(),
		"agent_id":    agentID,
		"chat_id":     fmt.Sprintf("%d", message.Chat.ID),
		"user_id":     userID,
		"author_id":   userID,
		"author_type": "telegram",
		"thread_type": "telegram",
		"message":     message.Text,
	}

	sender := NewTelegramSender(bot, message.Chat.ID)
	err := m.apiClient.StreamAgent(context.Background(), payload, func(msg types.ChatMessage) error {
		shared.DispatchMessage(context.Background(), msg, sender)
		return nil
	})
	if err != nil {
		slog.Error("Failed to stream agent", "error", err)
		_ = sender.SendText(context.Background(), "Sorry, I encountered an error processing your request.")
	}
}

func (m *Manager) handleTeamMessage(bot *telego.Bot, message telego.Message, teamID string) {
	if message.Text == "" || message.From == nil {
		return
	}

	slog.Info("Received team message", "team_id", teamID, "chat_id", message.Chat.ID)
	_ = bot.SendChatAction(context.Background(), tu.ChatAction(tu.ID(message.Chat.ID), telego.ChatActionTyping))

	telegramID := fmt.Sprintf("%d", message.From.ID)

	payload := map[string]interface{}{
		"team_id":     teamID,
		"telegram_id": telegramID,
		"chat_id":     fmt.Sprintf("%d", message.Chat.ID),
		"message":     message.Text,
	}

	sender := NewTelegramSender(bot, message.Chat.ID)
	err := m.apiClient.StreamTeamLead(context.Background(), payload, func(msg types.ChatMessage) error {
		shared.DispatchMessage(context.Background(), msg, sender)
		return nil
	})
	if err != nil {
		slog.Error("Failed to stream team lead", "error", err)
		_ = sender.SendText(context.Background(), "Sorry, I encountered an error processing your request.")
	}
}

func (m *Manager) handleCallbackQuery(bot *telego.Bot, query telego.CallbackQuery, agentID string, isTeam bool) {
	if query.Data == "" || query.Message == nil {
		return
	}

	// Answer the callback to remove the loading spinner
	_ = bot.AnswerCallbackQuery(context.Background(), &telego.AnswerCallbackQueryParams{
		CallbackQueryID: query.ID,
	})

	chatID := query.Message.GetChat().ID
	slog.Info("Received callback query", "data", query.Data, "chat_id", chatID)

	sender := NewTelegramSender(bot, chatID)

	if isTeam {
		telegramID := fmt.Sprintf("%d", query.From.ID)
		payload := map[string]interface{}{
			"team_id":     agentID,
			"telegram_id": telegramID,
			"chat_id":     fmt.Sprintf("%d", chatID),
			"message":     query.Data,
		}
		err := m.apiClient.StreamTeamLead(context.Background(), payload, func(msg types.ChatMessage) error {
			shared.DispatchMessage(context.Background(), msg, sender)
			return nil
		})
		if err != nil {
			slog.Error("Failed to stream team lead for callback", "error", err)
		}
	} else {
		userID := fmt.Sprintf("%d", query.From.ID)
		if query.From.Username != "" {
			userID = query.From.Username
		}
		payload := map[string]interface{}{
			"id":          xid.New().String(),
			"agent_id":    agentID,
			"chat_id":     fmt.Sprintf("%d", chatID),
			"user_id":     userID,
			"author_id":   userID,
			"author_type": "telegram",
			"thread_type": "telegram",
			"message":     query.Data,
		}
		err := m.apiClient.StreamAgent(context.Background(), payload, func(msg types.ChatMessage) error {
			shared.DispatchMessage(context.Background(), msg, sender)
			return nil
		})
		if err != nil {
			slog.Error("Failed to stream agent for callback", "error", err)
		}
	}
}
```

**Step 3: Update `integrations/telegram/bot/manager.go` to handle CallbackQuery**

In the `ensureBotRunning` method (around line 169-175), update the goroutine that processes updates to also handle callback queries:

```go
go func() {
    for update := range updates {
        if update.Message != nil {
            m.handleMessage(bot, *update.Message, agent.ID)
        }
        if update.CallbackQuery != nil {
            m.handleCallbackQuery(bot, *update.CallbackQuery, agent.ID, false)
        }
    }
}()
```

Similarly in `ensureTeamBotRunning` (around line 275-281):

```go
go func() {
    for update := range updates {
        if update.Message != nil {
            m.handleTeamMessage(bot, *update.Message, tc.TeamID)
        }
        if update.CallbackQuery != nil {
            m.handleCallbackQuery(bot, *update.CallbackQuery, tc.TeamID, true)
        }
    }
}()
```

**Step 4: Verify build**

```bash
cd integrations && go build ./cmd/telegram
```

**Step 5: Commit**

```bash
git add integrations/telegram/ integrations/shared/
git commit -m "feat: telegram rich media sender with SSE streaming and callback queries"
```

---

## Task 6: Implement WeChat Media Upload and Rich Media Sender

Add `getuploadurl` + CDN upload to iLink client, implement `MessageSender` for WeChat, switch to SSE.

**Files:**
- Modify: `integrations/wechat/ilink/types.go` (add media item types and upload types)
- Modify: `integrations/wechat/ilink/client.go` (add upload and media send methods)
- Create: `integrations/wechat/bot/sender.go`
- Modify: `integrations/wechat/bot/manager.go:256-334` (switch to SSE)

**Step 1: Update `integrations/wechat/ilink/types.go`**

Add new structs after the existing types:

```go
// ImageItem holds image content for a message item.
type ImageItem struct {
	URL string `json:"url"`
}

// VideoItem holds video content for a message item.
type VideoItem struct {
	URL string `json:"url"`
}

// FileItem holds file content for a message item.
type FileItem struct {
	URL  string `json:"url"`
	Name string `json:"name,omitempty"`
}
```

Update `ItemObj` to include the new item types:

```go
type ItemObj struct {
	Type      int        `json:"type"`
	TextItem  *TextItem  `json:"text_item,omitempty"`
	ImageItem *ImageItem `json:"image_item,omitempty"`
	VideoItem *VideoItem `json:"video_item,omitempty"`
	FileItem  *FileItem  `json:"file_item,omitempty"`
}
```

Add upload types:

```go
// --- GetUploadURL ---

type GetUploadURLRequest struct {
	BaseInfo BaseInfo `json:"base_info"`
}

type GetUploadURLResponse struct {
	Ret       int    `json:"ret"`
	ErrMsg    string `json:"errmsg,omitempty"`
	UploadURL string `json:"upload_url"`
	FileKey   string `json:"file_key,omitempty"`
}
```

Note: The exact `GetUploadURLResponse` fields need to be verified against the actual iLink API response during implementation. Consult the openclaw-weixin SDK source for the precise field names and upload flow.

**Step 2: Add upload and media methods to `integrations/wechat/ilink/client.go`**

```go
// GetUploadURL obtains a pre-signed URL for media upload.
func (c *Client) GetUploadURL(ctx context.Context) (*GetUploadURLResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	reqBody := GetUploadURLRequest{
		BaseInfo: BaseInfo{},
	}

	var resp GetUploadURLResponse
	if err := c.doPost(ctx, "/ilink/bot/getuploadurl", reqBody, &resp); err != nil {
		return nil, err
	}

	if resp.Ret != 0 {
		return nil, fmt.Errorf("getuploadurl returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return &resp, nil
}

// UploadMedia uploads raw bytes to the given pre-signed URL.
func (c *Client) UploadMedia(ctx context.Context, uploadURL string, data []byte, contentType string) error {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Minute)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "PUT", uploadURL, bytes.NewReader(data))
	if err != nil {
		return fmt.Errorf("create upload request: %w", err)
	}
	req.Header.Set("Content-Type", contentType)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("upload media: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("upload returned status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

// SendImage sends an image message to a WeChat user.
func (c *Client) SendImage(ctx context.Context, toUserID, contextToken, imageURL string) error {
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
					Type:      ItemTypeImage,
					ImageItem: &ImageItem{URL: imageURL},
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
		return fmt.Errorf("send image returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}
	return nil
}

// SendVideo sends a video message to a WeChat user.
func (c *Client) SendVideo(ctx context.Context, toUserID, contextToken, videoURL string) error {
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
					Type:      ItemTypeVideo,
					VideoItem: &VideoItem{URL: videoURL},
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
		return fmt.Errorf("send video returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}
	return nil
}

// SendFile sends a file message to a WeChat user.
func (c *Client) SendFile(ctx context.Context, toUserID, contextToken, fileURL, fileName string) error {
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
					Type:     ItemTypeFile,
					FileItem: &FileItem{URL: fileURL, Name: fileName},
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
		return fmt.Errorf("send file returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}
	return nil
}
```

Note: The exact upload flow (whether to pass CDN URL directly in `ImageItem.URL` or first upload and pass a file key) must be verified against the iLink API during implementation. Check the openclaw-weixin SDK.

**Step 3: Create `integrations/wechat/bot/sender.go`**

```go
package bot

import (
	"context"
	"fmt"
	"log/slog"
	"strings"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/wechat/ilink"
)

// WechatSender implements shared.MessageSender for WeChat.
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

func (s *WechatSender) SendImage(ctx context.Context, url string, caption string) error {
	if caption != "" {
		_ = s.SendText(ctx, caption)
	}

	// Download from our CDN, upload to WeChat CDN, then send
	cdnURL, err := s.uploadToWechat(ctx, url, "image/jpeg")
	if err != nil {
		slog.Error("Failed to upload image to WeChat CDN", "error", err)
		// Fallback: send URL as text
		return s.SendText(ctx, fmt.Sprintf("🖼️ %s", url))
	}

	return s.client.SendImage(ctx, s.toUserID, s.contextToken, cdnURL)
}

func (s *WechatSender) SendVideo(ctx context.Context, url string, caption string) error {
	if caption != "" {
		_ = s.SendText(ctx, caption)
	}

	cdnURL, err := s.uploadToWechat(ctx, url, "video/mp4")
	if err != nil {
		slog.Error("Failed to upload video to WeChat CDN", "error", err)
		return s.SendText(ctx, fmt.Sprintf("🎬 %s", url))
	}

	return s.client.SendVideo(ctx, s.toUserID, s.contextToken, cdnURL)
}

func (s *WechatSender) SendFile(ctx context.Context, url string, name string, caption string) error {
	if caption != "" {
		_ = s.SendText(ctx, caption)
	}

	cdnURL, err := s.uploadToWechat(ctx, url, "application/octet-stream")
	if err != nil {
		slog.Error("Failed to upload file to WeChat CDN", "error", err)
		return s.SendText(ctx, fmt.Sprintf("📎 %s: %s", name, url))
	}

	if name == "" {
		name = "file"
	}
	return s.client.SendFile(ctx, s.toUserID, s.contextToken, cdnURL, name)
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
		linkLabel := label
		if linkLabel == "" {
			linkLabel = "🔗 Link"
		}
		parts = append(parts, linkLabel+": "+linkURL)
	}

	if len(parts) == 0 {
		return nil
	}

	// If there's an image, send it first
	if imageURL != "" {
		_ = s.SendImage(ctx, imageURL, "")
	}

	return s.SendText(ctx, strings.Join(parts, "\n"))
}

func (s *WechatSender) SendChoice(ctx context.Context, question string, options []string) error {
	text := "❓ " + question + "\n"
	for i, opt := range options {
		text += fmt.Sprintf("%d. %s\n", i+1, opt)
	}
	return s.SendText(ctx, strings.TrimSpace(text))
}

// uploadToWechat downloads media from our CDN and re-uploads to WeChat CDN.
func (s *WechatSender) uploadToWechat(ctx context.Context, sourceURL, contentType string) (string, error) {
	// 1. Download from our CDN
	data, err := shared.DownloadFromURL(ctx, sourceURL)
	if err != nil {
		return "", fmt.Errorf("download media: %w", err)
	}

	// 2. Get upload URL from WeChat
	uploadResp, err := s.client.GetUploadURL(ctx)
	if err != nil {
		return "", fmt.Errorf("get upload url: %w", err)
	}

	// 3. Upload to WeChat CDN
	if err := s.client.UploadMedia(ctx, uploadResp.UploadURL, data, contentType); err != nil {
		return "", fmt.Errorf("upload to wechat cdn: %w", err)
	}

	// Return the CDN URL or file key for use in sendmessage
	// Note: the exact return value depends on iLink API behavior — may be
	// uploadResp.FileKey or the upload URL itself. Verify during implementation.
	return uploadResp.UploadURL, nil
}
```

**Step 4: Update `integrations/wechat/bot/manager.go` — rewrite `handleTeamMessage`**

Replace the `handleTeamMessage` method (lines 256-334):

```go
func (m *Manager) handleTeamMessage(entry *botEntry, msg ilink.WeixinMessage, teamID string) {
	// Extract text from item_list
	text := ""
	for _, item := range msg.ItemList {
		if item.Type == 1 && item.TextItem != nil {
			text = item.TextItem.Text
			break
		}
	}

	if text == "" || msg.FromUserID == "" {
		return
	}

	slog.Info("Received wechat message", "team_id", teamID, "from", msg.FromUserID)

	// Store latest context_token for proactive messaging
	m.updateContextToken(teamID, msg.ContextToken)

	// Lazy-fetch typing_ticket on first message
	if entry.typingTicket == "" {
		cfgResp, err := entry.client.GetConfig(context.Background(), msg.FromUserID, msg.ContextToken)
		if err != nil {
			slog.Warn("Failed to get typing_ticket", "team_id", teamID, "error", err)
		} else {
			entry.typingTicket = cfgResp.TypingTicket
			m.updateTeamChannelData(teamID, entry.typingTicket)
		}
	}

	// Start periodic typing indicator
	typingCtx, typingCancel := context.WithCancel(context.Background())
	if entry.typingTicket != "" {
		_ = entry.client.SendTyping(typingCtx, msg.FromUserID, entry.typingTicket)
		go func() {
			ticker := time.NewTicker(10 * time.Second)
			defer ticker.Stop()
			for {
				select {
				case <-typingCtx.Done():
					return
				case <-ticker.C:
					_ = entry.client.SendTyping(typingCtx, msg.FromUserID, entry.typingTicket)
				}
			}
		}()
	}

	// Call Core API via SSE stream
	payload := map[string]interface{}{
		"team_id":        teamID,
		"wechat_user_id": msg.FromUserID,
		"chat_id":        msg.FromUserID,
		"message":        text,
	}

	sender := NewWechatSender(entry.client, msg.FromUserID, msg.ContextToken)
	err := m.apiClient.StreamWechatTeamLead(context.Background(), payload, func(chatMsg types.ChatMessage) error {
		shared.DispatchMessage(context.Background(), chatMsg, sender)
		return nil
	})
	typingCancel() // stop typing indicator

	if err != nil {
		slog.Error("Failed to stream wechat team lead", "error", err)
		_ = sender.SendText(context.Background(), "Sorry, I encountered an error processing your request.")
	}
}
```

Remember to add the new imports at the top of manager.go:
```go
import (
	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/types"
)
```

**Step 5: Verify build**

```bash
cd integrations && go build ./cmd/wechat
```

**Step 6: Commit**

```bash
git add integrations/wechat/
git commit -m "feat: wechat rich media sender with CDN upload and SSE streaming"
```

---

## Task 7: Cleanup and Final Verification

Remove old non-streaming code paths, update AGENTS.md files, verify everything builds.

**Files:**
- Modify: `integrations/telegram/api/client.go` (remove old Execute methods if no longer needed)
- Modify: `integrations/wechat/api/client.go` (remove old Execute method)
- Modify: `integrations/telegram/AGENTS.md`
- Modify: `integrations/wechat/AGENTS.md`
- Delete: `integrations/telegram/.air.toml`
- Delete: `integrations/wechat/.air.toml`
- Delete: `integrations/telegram/.gitignore`
- Delete: `integrations/wechat/.gitignore`

**Step 1: Clean up old API client methods**

In `integrations/telegram/api/client.go`: Remove `ExecuteAgent` and `ExecuteTeamLead` methods (replaced by `StreamAgent` and `StreamTeamLead`). Keep `CheckHealth`.

In `integrations/wechat/api/client.go`: Remove `ExecuteWechatTeamLead` method (replaced by `StreamWechatTeamLead`). Keep `CheckHealth`.

Remove `resty/v2` import if fully replaced by v3 (or if the streaming methods use `shared.StreamRequest` which uses its own client). If `CheckHealth` still uses resty, update it to v3.

**Step 2: Verify both binaries build**

```bash
cd integrations
go build ./cmd/telegram
go build ./cmd/wechat
```

**Step 3: Verify docker-compose builds**

```bash
docker compose build telegram wechat
```

**Step 4: Update AGENTS.md files**

Update `integrations/telegram/AGENTS.md` and `integrations/wechat/AGENTS.md` to reflect:
- Module merged into single `integrations/` module
- Entry points moved to `cmd/telegram/main.go` and `cmd/wechat/main.go`
- SSE streaming instead of non-streaming execute
- Rich media support (images, videos, files, cards, choices)
- New shared packages (`shared/`, `types/`)

**Step 5: Commit**

```bash
git add integrations/
git commit -m "chore: cleanup old non-streaming code and update docs"
```

---

## Important Notes for Implementation

1. **iLink media upload flow**: The exact `getuploadurl` request/response format and the subsequent CDN upload protocol (PUT vs POST, content-type headers, encryption) need to be verified by consulting the [openclaw-weixin SDK](https://github.com/hao-ji-xing/openclaw-weixin). The WeChat CDN uses `novac2c.cdn.weixin.qq.com` with possible AES-128-ECB encryption. The implementation in Task 6 is a best-effort skeleton that will need adjustment.

2. **Resty v3 SSE API**: The exact resty v3 SSE reading API needs to be checked. If v3 provides a first-class SSE reader, use it instead of manual `bufio.Scanner` parsing in `shared/sse.go`.

3. **Telego API verification**: The `SendPhoto`, `SendVideo`, `SendDocument` param structs in telego v1.7.0 need exact field name verification. The `InputFile{URL: url}` syntax should be checked — telego may use `telego.InputFileFromURL(url)` or similar.

4. **CHOICE callback_data limit**: Telegram limits `callback_data` to 64 bytes. If option text exceeds this, truncate or use a hash mapping. Handle this edge case in `TelegramSender.SendChoice`.

5. **Error resilience**: If media upload/send fails in any platform, always fall back to sending the URL as plain text rather than silently dropping the attachment.
