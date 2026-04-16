# WeChat Image S3 Storage Design

## Problem

WeChat sends temporary CDN image URLs (`novac2c.cdn.weixin.qq.com`) with encrypted query parameters. These URLs:
1. May expire (WeChat's general media retention is ~3 days, CDN tokens likely shorter)
2. Return AES-128-ECB encrypted ciphertext, not usable images
3. Cannot be accessed by the LLM directly

## Solution

Download and decrypt WeChat images in the Go integration layer, upload to S3, and pass the stable S3 CDN URL to the Python backend for LLM consumption.

## Architecture

### Layer Separation

**Shared layer (`integrations/shared/storage.go`)** — reusable by all channels:
- S3 client initialization using `aws-sdk-go-v2`
- `StoreMedia(ctx, bytes, key, contentType) → (cdnURL, error)` — upload bytes to S3, return CDN URL
- Reads same env vars as Python S3 client: `AWS_S3_BUCKET`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`, `AWS_S3_ACCESS_KEY_ID`, `AWS_S3_SECRET_ACCESS_KEY`, `AWS_S3_CDN_URL`, `ENV`
- Supports custom S3-compatible endpoints via `BaseEndpoint` + `UsePathStyle`

**WeChat-specific layer (`integrations/wechat/ilink/media.go`)** — WeChat only:
- `DownloadAndDecryptMedia(media CDNMedia) → ([]byte, error)` — download ciphertext from CDN, AES-128-ECB decrypt with PKCS7 unpadding
- Reuses existing `aesECBDecrypt` logic from `client.go`

### Flow

```
WeChat message arrives (manager.go)
  → ilink.DownloadAndDecryptMedia(imageItem.Media)   // WeChat-specific: download + decrypt
  → shared.Storage.StoreMedia(bytes, key, contentType) // Shared: upload to S3
  → S3 CDN URL as attachment → Python backend → LLM ✓
```

Future channels (e.g., Telegram) only need:
```
shared.DownloadFromURL(imageURL)
  → shared.Storage.StoreMedia(bytes, key, contentType)
  → pass S3 URL to backend
```

### S3 Key Format

`{env}/wechat/{teamID}/{timestamp}_{randomID}.{ext}`

### File Changes

| File | Change |
|---|---|
| `integrations/go.mod` | Add aws-sdk-go-v2 dependencies |
| `integrations/shared/storage.go` | **New** — S3Storage implementation |
| `integrations/wechat/ilink/media.go` | **New** — DownloadAndDecryptMedia |
| `integrations/wechat/bot/manager.go` | Modify image extraction to download+decrypt+upload |
| `integrations/wechat/config/config.go` | Add S3 config fields |

### No Changes

- Python backend — no changes needed
- Telegram integration — unchanged (can adopt later)
- `types/messages.go` — attachment structure unchanged, only URL source changes
- Outbound image flow — unchanged (WeChat sender still uploads to WeChat CDN)

## Dependencies

- `github.com/aws/aws-sdk-go-v2`
- `github.com/aws/aws-sdk-go-v2/config`
- `github.com/aws/aws-sdk-go-v2/credentials`
- `github.com/aws/aws-sdk-go-v2/service/s3`

## Decision Log

- **Why Go layer, not Python?** — WeChat CDN returns AES-encrypted ciphertext; decryption requires `aes_key` from the message, only available in Go.
- **Why aws-sdk-go-v2, not minio-go?** — MinIO server archived Feb 2026; client library maintenance uncertain long-term. AWS SDK is safer bet.
- **Why shared storage module?** — Future channels (Telegram, etc.) will also need to persist user-sent media for LLM access.
