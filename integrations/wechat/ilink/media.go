package ilink

import (
	"context"
	"crypto/aes"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"log/slog"
	"net/http"
	"strings"

	"github.com/crestalnetwork/intentkit/integrations/shared"
)

// DownloadAndDecryptMedia fetches WeChat CDN media and returns the plaintext
// bytes plus the detected MIME type. It tries the raw response first (the CDN
// sometimes returns plaintext already) and falls back to AES-128-ECB+PKCS7 if
// EncryptType != 0 and AESKey is set. Errors if neither path yields a
// recognizable image/video/audio payload.
func DownloadAndDecryptMedia(ctx context.Context, media CDNMedia) ([]byte, string, error) {
	downloadURL := MediaDownloadURL(media)
	if downloadURL == "" {
		return nil, "", fmt.Errorf("empty media download URL")
	}

	raw, err := shared.DownloadFromURL(ctx, downloadURL)
	if err != nil {
		return nil, "", fmt.Errorf("download media %q: %w", downloadURL, err)
	}

	if mime := http.DetectContentType(raw); isRecognizedMime(mime) {
		slog.Info("wechat media: ready",
			"path", "raw",
			"size", len(raw),
			"mime", mime,
			"encrypt_type", media.EncryptType,
		)
		return raw, mime, nil
	}

	if media.EncryptType == 0 || media.AESKey == "" {
		return nil, "", fmt.Errorf(
			"download is not recognized media and no aes key provided "+
				"(size=%d head=%s)",
			len(raw), headHex(raw, 16),
		)
	}

	aesKey, err := decodeAESKey(media.AESKey)
	if err != nil {
		return nil, "", fmt.Errorf("decode aes key (len=%d): %w", len(media.AESKey), err)
	}

	plain, err := aesECBDecrypt(aesKey, raw)
	if err != nil {
		return nil, "", fmt.Errorf(
			"decrypt media (size=%d raw_head=%s aes_key_len=%d): %w",
			len(raw), headHex(raw, 16), len(media.AESKey), err,
		)
	}

	mime := http.DetectContentType(plain)
	if !isRecognizedMime(mime) {
		return nil, "", fmt.Errorf(
			"decrypted bytes are not recognized media "+
				"(plain_size=%d plain_head=%s raw_head=%s encrypt_type=%d aes_key_len=%d)",
			len(plain), headHex(plain, 16),
			headHex(raw, 16), media.EncryptType, len(media.AESKey),
		)
	}

	slog.Info("wechat media: ready",
		"path", "decrypted",
		"size", len(plain),
		"mime", mime,
	)
	return plain, mime, nil
}

// isRecognizedMime reports whether ct is an image/video/audio MIME type.
func isRecognizedMime(ct string) bool {
	return strings.HasPrefix(ct, "image/") ||
		strings.HasPrefix(ct, "video/") ||
		strings.HasPrefix(ct, "audio/")
}

// headHex hex-encodes up to the first n bytes of b for diagnostic logs.
func headHex(b []byte, n int) string {
	if n > len(b) {
		n = len(b)
	}
	return hex.EncodeToString(b[:n])
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

// decodeAESKey tries multiple encoding formats for the AES key:
// 1. base64(hex_string) → hex decode → 16 bytes (this project's outbound convention)
// 2. base64(raw_16_bytes) → 16 bytes directly
// 3. raw hex string → 16 bytes
func decodeAESKey(encoded string) ([]byte, error) {
	// Try base64 decode first
	decoded, err := base64.StdEncoding.DecodeString(encoded)
	if err == nil {
		// base64 succeeded — check if result is a hex string or raw bytes
		if len(decoded) == 32 {
			// Likely hex string (32 hex chars → 16 bytes)
			if key, err := hex.DecodeString(string(decoded)); err == nil {
				return key, nil
			}
		}
		if len(decoded) == 16 {
			// Raw 16-byte key
			return decoded, nil
		}
	}

	// Try raw hex string (32 hex chars → 16 bytes)
	if key, err := hex.DecodeString(encoded); err == nil && len(key) == 16 {
		return key, nil
	}

	return nil, fmt.Errorf("unrecognized AES key format (length %d)", len(encoded))
}
