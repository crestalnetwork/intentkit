# WeChat Image S3 Storage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Download and decrypt WeChat inbound images in the Go layer, upload to S3, and pass stable CDN URLs to the Python backend so the LLM can access them.

**Architecture:** Shared S3 storage module in `integrations/shared/` using `aws-sdk-go-v2`. WeChat-specific AES decryption in `integrations/wechat/ilink/`. Manager wires them together on image receipt.

**Tech Stack:** Go, aws-sdk-go-v2, AES-128-ECB (existing), resty (existing)

---

### Task 1: Add aws-sdk-go-v2 dependencies

**Files:**
- Modify: `integrations/go.mod`

**Step 1: Add the dependencies**

```bash
cd integrations && go get github.com/aws/aws-sdk-go-v2 github.com/aws/aws-sdk-go-v2/config github.com/aws/aws-sdk-go-v2/credentials github.com/aws/aws-sdk-go-v2/service/s3
```

**Step 2: Tidy**

```bash
cd integrations && go mod tidy
```

**Step 3: Verify**

Run: `cd integrations && go build ./...`
Expected: compiles without error

---

### Task 2: Create shared S3 storage module

**Files:**
- Create: `integrations/shared/storage.go`

**Step 1: Write the storage module**

```go
package shared

import (
	"bytes"
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"

	"github.com/aws/aws-sdk-go-v2/aws"
	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

// S3Storage provides media upload to S3-compatible object storage.
// Safe for concurrent use.
type S3Storage struct {
	client *s3.Client
	bucket string
	cdnURL string // e.g. "https://example.com/static"
	env    string // e.g. "production", used as key prefix
}

// NewS3StorageFromEnv creates an S3Storage from standard environment variables.
// Returns nil if AWS_S3_BUCKET is not set (graceful degradation).
// Reads: AWS_S3_BUCKET, AWS_S3_ENDPOINT_URL, AWS_S3_REGION_NAME,
// AWS_S3_ACCESS_KEY_ID, AWS_S3_SECRET_ACCESS_KEY, AWS_S3_CDN_URL, ENV.
func NewS3StorageFromEnv() *S3Storage {
	bucket := os.Getenv("AWS_S3_BUCKET")
	if bucket == "" {
		slog.Warn("AWS_S3_BUCKET not set, S3 storage disabled")
		return nil
	}

	region := os.Getenv("AWS_S3_REGION_NAME")
	if region == "" {
		region = "us-east-1"
	}

	accessKey := os.Getenv("AWS_S3_ACCESS_KEY_ID")
	secretKey := os.Getenv("AWS_S3_SECRET_ACCESS_KEY")
	endpointURL := os.Getenv("AWS_S3_ENDPOINT_URL")
	cdnURL := os.Getenv("AWS_S3_CDN_URL")
	env := os.Getenv("ENV")
	if env == "" {
		env = "local"
	}

	cfg, err := awsconfig.LoadDefaultConfig(context.Background(),
		awsconfig.WithRegion(region),
		awsconfig.WithCredentialsProvider(
			credentials.NewStaticCredentialsProvider(accessKey, secretKey, ""),
		),
	)
	if err != nil {
		slog.Error("Failed to load AWS config", "error", err)
		return nil
	}

	var client *s3.Client
	if endpointURL != "" {
		client = s3.NewFromConfig(cfg, func(o *s3.Options) {
			o.BaseEndpoint = aws.String(endpointURL)
			o.UsePathStyle = true
		})
	} else {
		client = s3.NewFromConfig(cfg)
	}

	slog.Info("S3 storage initialized", "bucket", bucket, "env", env)
	return &S3Storage{
		client: client,
		bucket: bucket,
		cdnURL: cdnURL,
		env:    env,
	}
}

// StoreMedia uploads media bytes to S3 and returns the CDN URL.
// key should be a relative path like "wechat/{teamID}/{id}.jpg".
// The final S3 key will be "{env}/{key}".
// If contentType is empty, it will be detected from the data.
func (s *S3Storage) StoreMedia(ctx context.Context, data []byte, key string, contentType string) (string, error) {
	if contentType == "" {
		contentType = http.DetectContentType(data)
	}

	fullKey := s.env + "/" + key

	_, err := s.client.PutObject(ctx, &s3.PutObjectInput{
		Bucket:      aws.String(s.bucket),
		Key:         aws.String(fullKey),
		Body:        bytes.NewReader(data),
		ContentType: aws.String(contentType),
	})
	if err != nil {
		return "", fmt.Errorf("s3 put object: %w", err)
	}

	cdnURL := s.cdnURL + "/" + fullKey
	return cdnURL, nil
}
```

**Step 2: Verify compilation**

Run: `cd integrations && go build ./...`
Expected: compiles without error

---

### Task 3: Create WeChat media download+decrypt function

**Files:**
- Create: `integrations/wechat/ilink/media.go`
- Modify: `integrations/wechat/ilink/client.go` — export `aesECBDecrypt` by extracting it

**Step 1: Extract AES decrypt as an exported function**

In `integrations/wechat/ilink/client.go`, the `aesECBEncrypt` function (line 238) contains the encrypt logic. There is no standalone decrypt function — we need to create one. Looking at the upload flow, decryption is the reverse: AES-128-ECB decrypt each block, then strip PKCS7 padding.

Create `integrations/wechat/ilink/media.go`:

```go
package ilink

import (
	"context"
	"crypto/aes"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"log/slog"

	"github.com/crestalnetwork/intentkit/integrations/shared"
)

// DownloadAndDecryptMedia downloads encrypted media from WeChat CDN and decrypts it.
// Returns the decrypted plaintext bytes.
func DownloadAndDecryptMedia(ctx context.Context, media CDNMedia) ([]byte, error) {
	downloadURL := MediaDownloadURL(media)
	if downloadURL == "" {
		return nil, fmt.Errorf("empty media download URL")
	}

	// Download encrypted content from CDN
	ciphertext, err := shared.DownloadFromURL(ctx, downloadURL)
	if err != nil {
		return nil, fmt.Errorf("download media: %w", err)
	}

	// If no encryption, return as-is
	if media.EncryptType == 0 || media.AESKey == "" {
		return ciphertext, nil
	}

	// Decode AES key: base64(hex_string) → hex_string → 16 bytes
	aesKeyHex, err := base64.StdEncoding.DecodeString(media.AESKey)
	if err != nil {
		// Fallback: try treating it directly as hex
		aesKeyHex = []byte(media.AESKey)
	}

	aesKey, err := hex.DecodeString(string(aesKeyHex))
	if err != nil {
		return nil, fmt.Errorf("decode aes key hex: %w", err)
	}

	// Decrypt AES-128-ECB + strip PKCS7 padding
	plaintext, err := aesECBDecrypt(aesKey, ciphertext)
	if err != nil {
		return nil, fmt.Errorf("decrypt media: %w", err)
	}

	slog.Debug("Media downloaded and decrypted", "size", len(plaintext))
	return plaintext, nil
}

// aesECBDecrypt decrypts AES-128-ECB ciphertext and strips PKCS7 padding.
func aesECBDecrypt(key, ciphertext []byte) ([]byte, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("create cipher: %w", err)
	}

	blockSize := block.BlockSize()
	if len(ciphertext) == 0 || len(ciphertext)%blockSize != 0 {
		return nil, fmt.Errorf("ciphertext length %d is not a multiple of block size %d", len(ciphertext), blockSize)
	}

	// ECB mode: decrypt each block independently
	plaintext := make([]byte, len(ciphertext))
	for i := 0; i < len(ciphertext); i += blockSize {
		block.Decrypt(plaintext[i:i+blockSize], ciphertext[i:i+blockSize])
	}

	// Strip PKCS7 padding
	if len(plaintext) == 0 {
		return plaintext, nil
	}
	padding := int(plaintext[len(plaintext)-1])
	if padding < 1 || padding > blockSize {
		return nil, fmt.Errorf("invalid PKCS7 padding value: %d", padding)
	}
	for i := len(plaintext) - padding; i < len(plaintext); i++ {
		if plaintext[i] != byte(padding) {
			return nil, fmt.Errorf("invalid PKCS7 padding at byte %d", i)
		}
	}
	return plaintext[:len(plaintext)-padding], nil
}
```

**Step 2: Verify compilation**

Run: `cd integrations && go build ./...`
Expected: compiles without error

---

### Task 4: Add S3 config to WeChat config and wire into Manager

**Files:**
- Modify: `integrations/wechat/config/config.go` — no change needed (env vars read by shared directly)
- Modify: `integrations/wechat/bot/manager.go` — add S3Storage field, use in handleTeamMessage
- Modify: `integrations/cmd/wechat/main.go` — init S3Storage at startup

**Step 1: Update Manager to accept S3Storage**

In `integrations/wechat/bot/manager.go`:

1. Add `storage *shared.S3Storage` field to `Manager` struct (line 28).
2. Update `NewManager` to accept `storage *shared.S3Storage` parameter (line 38).
3. Replace the image URL extraction in `handleTeamMessage` (lines 274-285) with download+decrypt+upload logic.

The updated `handleTeamMessage` image block (replacing lines 274-285):

```go
if item.Type == ilink.ItemTypeImage && item.ImageItem != nil {
    if m.storage != nil {
        // Download encrypted image from WeChat CDN, decrypt, upload to S3
        imageBytes, err := ilink.DownloadAndDecryptMedia(context.Background(), item.ImageItem.Media)
        if err != nil {
            slog.Warn("Failed to download/decrypt wechat image", "team_id", teamID, "error", err)
            continue
        }
        ext := extensionFromBytes(imageBytes)
        key := fmt.Sprintf("wechat/%s/%d_%s.%s", teamID, time.Now().UnixMilli(), xid.New().String(), ext)
        contentType := http.DetectContentType(imageBytes)
        cdnURL, err := m.storage.StoreMedia(context.Background(), imageBytes, key, contentType)
        if err != nil {
            slog.Warn("Failed to upload wechat image to S3", "team_id", teamID, "error", err)
            continue
        }
        leadText := "User sent an image."
        attachments = append(attachments, types.ChatMessageAttach{
            Type:     types.AttachImage,
            LeadText: &leadText,
            URL:      &cdnURL,
        })
    } else {
        // Fallback: pass WeChat CDN URL directly (may not work for LLM)
        imageURL := ilink.MediaDownloadURL(item.ImageItem.Media)
        if imageURL == "" {
            continue
        }
        leadText := "User sent an image."
        attachments = append(attachments, types.ChatMessageAttach{
            Type:     types.AttachImage,
            LeadText: &leadText,
            URL:      &imageURL,
        })
    }
}
```

Add helper at the bottom of `manager.go`:

```go
func extensionFromBytes(data []byte) string {
    ct := http.DetectContentType(data)
    switch {
    case strings.HasPrefix(ct, "image/jpeg"):
        return "jpg"
    case strings.HasPrefix(ct, "image/png"):
        return "png"
    case strings.HasPrefix(ct, "image/gif"):
        return "gif"
    case strings.HasPrefix(ct, "image/webp"):
        return "webp"
    default:
        return "jpg"
    }
}
```

Add required imports: `"net/http"`, `"strings"`, `"time"`, `"github.com/rs/xid"`.

**Step 2: Update main.go to init S3Storage**

In `integrations/cmd/wechat/main.go`, after config loading (line 37), before creating Manager:

```go
storage := shared.NewS3StorageFromEnv()

manager := bot.NewManager(db, cfg, apiClient, storage)
```

Add import: `"github.com/crestalnetwork/intentkit/integrations/shared"`

**Step 3: Verify compilation**

Run: `cd integrations && go build ./...`
Expected: compiles without error

---

### Task 5: Test end-to-end

**Step 1: Run linter**

```bash
cd integrations && go vet ./...
```

Expected: no errors

**Step 2: Run existing tests**

```bash
cd integrations && go test ./...
```

Expected: all tests pass (or "no test files" for packages without tests)

**Step 3: Manual verification**

Verify the code compiles and the flow makes sense:
- `NewS3StorageFromEnv()` returns nil if `AWS_S3_BUCKET` not set → fallback path used
- `DownloadAndDecryptMedia` handles both encrypted (EncryptType=1) and unencrypted media
- `StoreMedia` uploads with correct key prefix and returns CDN URL
- Manager gracefully skips images if download/decrypt/upload fails (logs warning, continues)
