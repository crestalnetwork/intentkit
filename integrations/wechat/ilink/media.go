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

// DownloadAndDecryptImage fetches an inbound WeChat image from the CDN and
// returns plaintext bytes plus detected MIME. Per the iLink protocol, inbound
// images carry the AES key as hex in the top-level ImageItem.aeskey field; if
// present it takes precedence over media.aes_key (which uses a different
// base64-of-hex encoding from outbound media).
func DownloadAndDecryptImage(ctx context.Context, img ImageItem) ([]byte, string, error) {
	media := img.Media
	keySource := "media.aes_key"
	if img.AESKeyHex != "" {
		keySource = "image_item.aeskey"
		rawKey, err := hex.DecodeString(img.AESKeyHex)
		if err != nil || len(rawKey) != 16 {
			return nil, "", fmt.Errorf(
				"invalid image_item.aeskey hex (len=%d): %w",
				len(img.AESKeyHex), err,
			)
		}
		media.AESKey = img.AESKeyHex
	}
	return downloadAndDecryptMedia(ctx, media, keySource)
}

// downloadAndDecryptMedia is the low-level worker: download → try raw → try
// AES decrypt → validate MIME. Diagnostic fields are logged at each step so a
// single failed attempt in production gives enough signal for post-mortem.
func downloadAndDecryptMedia(ctx context.Context, media CDNMedia, keySource string) ([]byte, string, error) {
	downloadURL := MediaDownloadURL(media)
	if downloadURL == "" {
		return nil, "", fmt.Errorf("empty media download URL")
	}

	slog.Info("wechat media: downloading",
		"url", downloadURL,
		"encrypt_type", media.EncryptType,
		"key_source", keySource,
		"aes_key_len", len(media.AESKey),
	)

	raw, err := shared.DownloadFromURL(ctx, downloadURL)
	if err != nil {
		return nil, "", fmt.Errorf("download media %q: %w", downloadURL, err)
	}

	slog.Info("wechat media: downloaded",
		"size", len(raw),
		"raw_head", headHex(raw, 32),
		"raw_tail", tailHex(raw, 16),
	)

	if mime := http.DetectContentType(raw); isRecognizedMime(mime) {
		slog.Info("wechat media: ready",
			"path", "raw",
			"size", len(raw),
			"mime", mime,
		)
		return raw, mime, nil
	}

	if media.AESKey == "" {
		return nil, "", fmt.Errorf(
			"raw download not recognized media and no aes key available "+
				"(encrypt_type=%d size=%d raw_head=%s)",
			media.EncryptType, len(raw), headHex(raw, 32),
		)
	}

	aesKey, err := decodeAESKey(media.AESKey)
	if err != nil {
		return nil, "", fmt.Errorf(
			"decode aes key (source=%s len=%d): %w",
			keySource, len(media.AESKey), err,
		)
	}

	slog.Info("wechat media: decoded aes key",
		"key_source", keySource,
		"key_head", headHex(aesKey, 4),
	)

	plain, err := aesECBDecrypt(aesKey, raw)
	if err != nil {
		return nil, "", fmt.Errorf(
			"decrypt media (encrypt_type=%d size=%d raw_head=%s key_source=%s): %w",
			media.EncryptType, len(raw), headHex(raw, 32), keySource, err,
		)
	}

	mime := http.DetectContentType(plain)
	if !isRecognizedMime(mime) {
		return nil, "", fmt.Errorf(
			"decrypted bytes not recognized media "+
				"(encrypt_type=%d key_source=%s plain_size=%d plain_head=%s raw_head=%s)",
			media.EncryptType, keySource,
			len(plain), headHex(plain, 32), headHex(raw, 32),
		)
	}

	slog.Info("wechat media: ready",
		"path", "decrypted",
		"size", len(plain),
		"mime", mime,
		"key_source", keySource,
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

// tailHex hex-encodes up to the last n bytes of b for diagnostic logs
// (useful for spotting PKCS7 padding shape in ciphertext).
func tailHex(b []byte, n int) string {
	if n > len(b) {
		n = len(b)
	}
	return hex.EncodeToString(b[len(b)-n:])
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
