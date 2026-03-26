# Rich Media Messaging for IM Integrations

## Goal

Enable Telegram and WeChat integrations to send rich media messages (images, videos, files, cards, choices) and real-time skill execution status, instead of text-only responses.

## Current State

- Agent already produces rich `ChatMessage` with `attachments` (IMAGE, VIDEO, FILE, CARD, CHOICE) and `skill_calls`
- Frontend web UI renders all attachment types correctly
- Both Go integrations (Telegram, WeChat) only send plain text, ignoring attachments
- Both use non-streaming `/core/execute` endpoint, waiting for full completion before responding
- Go integrations are 3 separate modules (telegram, wechat, types) with `replace` directives

## Design

### 1. Merge Go Modules

Consolidate `integrations/telegram/`, `integrations/wechat/`, and `integrations/types/` into a single Go module at `integrations/`.

**New directory structure:**

```
integrations/
  go.mod                      # single module: github.com/crestalnetwork/intentkit/integrations
  go.sum
  cmd/
    telegram/main.go          # telegram entrypoint
    wechat/main.go            # wechat entrypoint
  types/                      # shared types (no longer a separate module)
    messages.go
  shared/                     # NEW: shared logic
    sse.go                    # SSE stream client
    dispatcher.go             # message dispatch by author_type
    media.go                  # media download helper (fetch from S3 URL)
  telegram/                   # telegram business code
    bot/
    api/
    config/
    store/
  wechat/                     # wechat business code
    bot/
    api/
    config/
    ilink/
    store/
  Dockerfile.telegram
  Dockerfile.wechat
```

**Key changes:**
- Single `go.mod` with merged dependencies
- Remove `replace` directives and `types/go.mod`
- `main.go` files move to `cmd/telegram/` and `cmd/wechat/`
- Dockerfiles updated: build context is `integrations/`, build commands become `go build ./cmd/telegram` and `go build ./cmd/wechat`
- All internal imports change from `github.com/.../integrations/types` to `github.com/.../integrations/types` (same path, but no longer a separate module)

### 2. Switch to SSE Streaming

Upgrade go-resty to v3 (which supports SSE) and switch from `/core/execute` to `/core/stream`.

**`shared/sse.go`** — SSE stream client:
- Uses resty v3's SSE support
- Calls `POST /core/stream` (or `/core/lead/stream` for team lead)
- Parses `event: message\ndata: {JSON}\n\n` format
- Deserializes each event data into `types.ChatMessage`
- Invokes a callback function for each message

**New API endpoints needed (Python side):**
- `POST /core/lead/stream` — streaming equivalent of `/core/lead/execute` (for Telegram team lead)
- `POST /core/lead/wechat/stream` — streaming equivalent of `/core/lead/wechat/execute` (for WeChat)

### 3. Message Dispatch Logic

**`shared/dispatcher.go`** — common dispatch logic:

For each `ChatMessage` received from the stream:

| `author_type` | Action |
|----------------|--------|
| `skill` | Send text: `"🔧 Running {skill_calls[0].name}..."` |
| `agent` | Send text (if non-empty) + process each attachment |
| `system` | If `error_type != nil`: send `"❌ {message}"`; else: send `"ℹ️ {message}"` |
| `thinking` | Ignore (do not send to user) |

The dispatcher calls platform-specific sender methods through an interface:

```go
type MessageSender interface {
    SendText(ctx context.Context, text string) error
    SendImage(ctx context.Context, url string, caption string) error
    SendVideo(ctx context.Context, url string, caption string) error
    SendFile(ctx context.Context, url string, caption string) error
    SendCard(ctx context.Context, title, description, imageURL, linkURL, label string) error
    SendChoice(ctx context.Context, question string, options []string) error
}
```

### 4. Attachment Handling Per Platform

#### Telegram

| Type | Implementation |
|------|----------------|
| IMAGE | `sendPhoto(url)` — Telegram accepts URL directly |
| VIDEO | `sendVideo(url)` — Telegram accepts URL directly |
| FILE | `sendDocument(url)` — Telegram accepts URL directly |
| CARD | If has image: `sendPhoto` + caption (title + description) + optional inline keyboard (link button). If no image: text + optional inline keyboard |
| CHOICE | Text + inline keyboard with one button per option. `callback_data` = option text |
| LINK | Skip |
| XMTP | Skip |

**Callback query handler:** New handler for inline keyboard button presses. Extracts `callback_data` and sends it as a new user message to the agent.

#### WeChat

| Type | Implementation |
|------|----------------|
| IMAGE | `getuploadurl` -> download from S3 -> upload to WeChat CDN -> `sendmessage` with `ItemTypeImage` |
| VIDEO | Same flow, `ItemTypeVideo` |
| FILE | Same flow, `ItemTypeFile` |
| CARD | Text fallback: `"📋 {title}\n{description}"` + optional `"\n🔗 {link}"` |
| CHOICE | Text fallback: `"❓ {question}\n1. {opt1}\n2. {opt2}\n3. {opt3}"` (user replies with number) |
| LINK | Skip |
| XMTP | Skip |

### 5. WeChat Media Upload

New additions to `wechat/ilink/`:

**New types (`types.go`):**
```go
ImageItem struct { URL string `json:"url"` }
VideoItem struct { URL string `json:"url"` }
FileItem  struct { URL string `json:"url"` Name string `json:"name"` }

GetUploadURLRequest / GetUploadURLResponse
```

Note: Exact field names for `ImageItem`, `VideoItem`, `FileItem` need to be verified against iLink API behavior. The community SDK sources should be consulted during implementation.

**New client methods (`client.go`):**
- `GetUploadURL(ctx)` — calls `/ilink/bot/getuploadurl`
- `UploadMedia(ctx, uploadURL string, data []byte)` — uploads to WeChat CDN
- `SendImage(ctx, toUserID, contextToken, cdnURL string)` — sends image message
- `SendVideo(ctx, toUserID, contextToken, cdnURL string)` — sends video message
- `SendFile(ctx, toUserID, contextToken, cdnURL, fileName string)` — sends file message

**`shared/media.go`** — download helper:
- `DownloadFromURL(ctx, url string) ([]byte, error)` — downloads media from our S3/CDN URL for re-upload to WeChat

### 6. Telegram Callback Query for CHOICE

When user clicks an inline keyboard button:
1. Telegram sends a `CallbackQuery` with `data` = option text
2. Handler answers the callback query (removes loading state)
3. Sends the option text as a new message to the agent via `/core/lead/stream`

### 7. Python-Side Changes

Add streaming lead endpoints:
- `POST /core/lead/stream` — SSE streaming version of `/core/lead/execute`
- `POST /core/lead/wechat/stream` — SSE streaming version of `/core/lead/wechat/execute`

These mirror the existing non-streaming endpoints but use `StreamingResponse` with `stream_agent()` instead of `execute_agent()`.

## Attachment Data Formats

For reference, the JSON structures in `ChatMessageAttachment.json`:

**CARD:**
```json
{
  "title": "Card Title",
  "description": "Card description text",
  "image_url": "https://...",  // optional
  "link": "https://...",       // optional
  "label": "View Details"      // optional button label
}
```

**CHOICE:**
```json
{
  "question": "Which option?",
  "options": ["Option A", "Option B", "Option C"]
}
```

## Out of Scope

- LINK attachments — skipped for now
- XMTP attachments — not relevant to IM
- Bot avatar/nickname changes — iLink API does not support this
- Voice message handling — can be added later
- Message editing/deletion — not needed for initial implementation
