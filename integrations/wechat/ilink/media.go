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

// mediaPolicy controls how downloadAndDecryptMedia treats raw CDN output.
//
// accept gates BOTH the raw-plaintext fast path AND the decrypted-output
// validation. allowRawFastPath permits skipping AES decrypt when the raw
// download's sniffed MIME already satisfies accept — only safe for media
// whose MIME Go can reliably identify (e.g. images). For SILK/AMR/arbitrary
// binaries, the sniff is unreliable, so the fast path must stay disabled
// and integrity is guaranteed by AES + PKCS7 alone.
type mediaPolicy struct {
	accept           func(string) bool
	allowRawFastPath bool
}

var (
	imagePolicy = mediaPolicy{accept: isRecognizedImageMime, allowRawFastPath: true}
	permissive  = mediaPolicy{accept: acceptAnyMime, allowRawFastPath: false}
)

// DownloadAndDecryptImage fetches an inbound WeChat image from the CDN and
// returns plaintext bytes plus detected MIME. Per the iLink protocol, inbound
// images carry the AES key as hex in the top-level ImageItem.aeskey field; if
// present it takes precedence over media.aes_key (which uses a different
// base64-of-hex encoding from outbound media).
func DownloadAndDecryptImage(ctx context.Context, img ImageItem) ([]byte, string, error) {
	// Images don't have a top-level URL fallback (historically the aeskey and
	// encrypted_query_param sit on media directly).
	return decryptInboundMedia(ctx, img.Media, img.AESKeyHex, "", "image_item", imagePolicy)
}

// DownloadAndDecryptVoice fetches an inbound WeChat voice message (typically
// SILK-v3) from the CDN. Go's http.DetectContentType cannot identify SILK or
// AMR, so MIME validation is intentionally permissive — we rely on successful
// AES-128-ECB + PKCS7 decryption as the integrity signal.
func DownloadAndDecryptVoice(ctx context.Context, vi VoiceItem) ([]byte, string, error) {
	return decryptInboundMedia(ctx, vi.Media, vi.AESKeyHex, vi.URL, "voice_item", permissive)
}

// DownloadAndDecryptVideo fetches an inbound WeChat video from the CDN.
func DownloadAndDecryptVideo(ctx context.Context, vi VideoItem) ([]byte, string, error) {
	return decryptInboundMedia(ctx, vi.Media, vi.AESKeyHex, vi.URL, "video_item", permissive)
}

// DownloadAndDecryptFile fetches an inbound WeChat file from the CDN. Files
// may be arbitrary binaries (PDFs, docs, zip, etc.) whose MIME is not known
// in advance, so acceptance is permissive.
func DownloadAndDecryptFile(ctx context.Context, fi FileItem) ([]byte, string, error) {
	return decryptInboundMedia(ctx, fi.Media, fi.AESKeyHex, fi.URL, "file_item", permissive)
}

// decryptInboundMedia is the shared "resolve key → apply URL fallback →
// download+decrypt" flow for inbound iLink media items. Per the iLink
// protocol, the top-level item aeskey hex (when present) overrides
// media.aes_key, and some item types carry the CDN URL at the item level
// rather than on the nested media.
func decryptInboundMedia(
	ctx context.Context,
	media CDNMedia,
	itemAESKeyHex, itemURL, itemKind string,
	policy mediaPolicy,
) ([]byte, string, error) {
	media, keySource, err := resolveMediaKey(media, itemAESKeyHex, itemKind)
	if err != nil {
		return nil, "", err
	}
	if media.URL == "" {
		media.URL = itemURL
	}
	return downloadAndDecryptMedia(ctx, media, keySource, policy)
}

// resolveMediaKey applies the "top-level aeskey takes precedence" rule used
// across inbound iLink media items. When itemAESKeyHex is set it must be a
// 32-char hex string (16 raw bytes) and is promoted into media.AESKey.
func resolveMediaKey(media CDNMedia, itemAESKeyHex, itemKind string) (CDNMedia, string, error) {
	if itemAESKeyHex == "" {
		return media, "media.aes_key", nil
	}
	rawKey, err := hex.DecodeString(itemAESKeyHex)
	if err != nil || len(rawKey) != 16 {
		return CDNMedia{}, "", fmt.Errorf(
			"invalid %s.aeskey hex (len=%d): %w",
			itemKind, len(itemAESKeyHex), err,
		)
	}
	media.AESKey = itemAESKeyHex
	return media, itemKind + ".aeskey", nil
}

// downloadAndDecryptMedia is the low-level worker: download → try raw → try
// AES decrypt → validate MIME. Diagnostic fields are logged at each step so a
// single failed attempt in production gives enough signal for post-mortem.
func downloadAndDecryptMedia(ctx context.Context, media CDNMedia, keySource string, policy mediaPolicy) ([]byte, string, error) {
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

	rawMime := http.DetectContentType(raw)
	if policy.allowRawFastPath && policy.accept(rawMime) {
		slog.Info("wechat media: ready",
			"path", "raw",
			"size", len(raw),
			"mime", rawMime,
		)
		return raw, rawMime, nil
	}

	if media.AESKey == "" {
		// Without an AES key and no decrypt step, only the strict raw-
		// fast-path policy should ever return bytes: under a permissive
		// policy (acceptAnyMime) every download would pass MIME validation,
		// so ciphertext from a protocol bug could be forwarded as plaintext.
		if policy.allowRawFastPath && policy.accept(rawMime) {
			slog.Info("wechat media: ready",
				"path", "raw",
				"size", len(raw),
				"mime", rawMime,
			)
			return raw, rawMime, nil
		}
		return nil, "", fmt.Errorf(
			"no aes key available and raw download not in fast-path "+
				"(encrypt_type=%d size=%d mime=%s raw_head=%s)",
			media.EncryptType, len(raw), rawMime, headHex(raw, 32),
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
	if !policy.accept(mime) {
		// Intentionally omit plain_head: if decryption succeeded on a user
		// document with sensitive content (passwords, PII), the first bytes
		// would leak into logs.
		return nil, "", fmt.Errorf(
			"decrypted bytes not accepted "+
				"(encrypt_type=%d key_source=%s plain_size=%d plain_mime=%s raw_head=%s)",
			media.EncryptType, keySource,
			len(plain), mime, headHex(raw, 32),
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

// isRecognizedImageMime accepts image/* only. Downstream (Gemini vision)
// only handles images, and CDN-served raw bytes must be verifiable as an
// image before we skip the decrypt step.
func isRecognizedImageMime(ct string) bool {
	return strings.HasPrefix(ct, "image/")
}

// acceptAnyMime permits any content type. Used by permissive policy for
// voice/video/file where http.DetectContentType can't reliably identify
// valid plaintext (SILK/AMR/arbitrary binaries) and integrity is guaranteed
// by AES + PKCS7 alone.
func acceptAnyMime(string) bool { return true }

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
