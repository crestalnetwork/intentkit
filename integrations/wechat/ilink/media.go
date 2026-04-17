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
	slog.Debug("DownloadAndDecryptMedia input",
		"url", media.URL,
		"encrypt_query_param", media.EncryptQueryParam,
		"encrypt_type", media.EncryptType,
		"aes_key_len", len(media.AESKey),
	)
	downloadURL := MediaDownloadURL(media)
	if downloadURL == "" {
		return nil, fmt.Errorf("empty media download URL")
	}

	ciphertext, err := shared.DownloadFromURL(ctx, downloadURL)
	if err != nil {
		return nil, fmt.Errorf("download media %q: %w", downloadURL, err)
	}

	// If no encryption, return as-is
	if media.EncryptType == 0 || media.AESKey == "" {
		return ciphertext, nil
	}

	// Decode AES key. WeChat uses multiple formats:
	// 1. base64(hex_string) — used by this project's outbound sender
	// 2. base64(raw_16_bytes) — possible inbound format
	// 3. raw hex string — another possible format
	aesKey, err := decodeAESKey(media.AESKey)
	if err != nil {
		return nil, fmt.Errorf("decode aes key: %w", err)
	}

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
