package ilink

import (
	"encoding/base64"
	"encoding/hex"
	"strings"
	"testing"
)

func TestIsRecognizedMime(t *testing.T) {
	cases := []struct {
		ct   string
		want bool
	}{
		{"image/jpeg", true},
		{"image/png", true},
		{"image/gif", true},
		{"image/webp", true},
		{"image/bmp", true},
		{"video/mp4", true},
		{"audio/mpeg", true},
		{"application/octet-stream", false},
		{"text/plain; charset=utf-8", false},
		{"text/html; charset=utf-8", false},
		{"", false},
	}
	for _, c := range cases {
		if got := isRecognizedMime(c.ct); got != c.want {
			t.Errorf("isRecognizedMime(%q) = %v, want %v", c.ct, got, c.want)
		}
	}
}

func TestHeadHex(t *testing.T) {
	cases := []struct {
		name string
		in   []byte
		n    int
		want string
	}{
		{"nil", nil, 8, ""},
		{"empty", []byte{}, 8, ""},
		{"shorter than n", []byte{0xFF, 0xD8}, 8, "ffd8"},
		{"exact", []byte{0xFF, 0xD8, 0xFF, 0xE0}, 4, "ffd8ffe0"},
		{"longer, truncated", []byte{0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10}, 3, "ffd8ff"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := headHex(c.in, c.n); got != c.want {
				t.Errorf("headHex = %q, want %q", got, c.want)
			}
		})
	}
}

func TestDecodeAESKey(t *testing.T) {
	raw := make([]byte, 16)
	for i := range raw {
		raw[i] = byte(i + 1)
	}
	hexStr := hex.EncodeToString(raw) // 32 hex chars

	t.Run("base64(hex_string)", func(t *testing.T) {
		encoded := base64.StdEncoding.EncodeToString([]byte(hexStr))
		got, err := decodeAESKey(encoded)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if string(got) != string(raw) {
			t.Errorf("got %x, want %x", got, raw)
		}
	})

	t.Run("base64(raw_16_bytes)", func(t *testing.T) {
		encoded := base64.StdEncoding.EncodeToString(raw)
		got, err := decodeAESKey(encoded)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if string(got) != string(raw) {
			t.Errorf("got %x, want %x", got, raw)
		}
	})

	t.Run("raw_hex_string", func(t *testing.T) {
		got, err := decodeAESKey(hexStr)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if string(got) != string(raw) {
			t.Errorf("got %x, want %x", got, raw)
		}
	})

	t.Run("unknown_format", func(t *testing.T) {
		if _, err := decodeAESKey("not a key!!"); err == nil {
			t.Error("expected error for garbage input, got nil")
		}
	})
}

func TestAesECBDecrypt(t *testing.T) {
	// Round-trip known plaintext through the companion encrypt function in
	// client.go to verify decrypt + PKCS7 strip recover the original.
	key := make([]byte, 16)
	for i := range key {
		key[i] = byte(i + 1)
	}
	plaintext := []byte("hello wechat image decryption path")

	ciphertext, err := aesECBEncrypt(key, plaintext)
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}

	got, err := aesECBDecrypt(key, ciphertext)
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}
	if string(got) != string(plaintext) {
		t.Errorf("got %q, want %q", got, plaintext)
	}

	t.Run("bad_block_size", func(t *testing.T) {
		if _, err := aesECBDecrypt(key, []byte{1, 2, 3}); err == nil ||
			!strings.Contains(err.Error(), "block size") {
			t.Errorf("expected block size error, got %v", err)
		}
	})

	t.Run("bad_padding", func(t *testing.T) {
		// Encrypt a tampered payload: valid ciphertext with bogus tail byte.
		bogus := make([]byte, len(ciphertext))
		copy(bogus, ciphertext)
		bogus[len(bogus)-1] ^= 0xFF
		if _, err := aesECBDecrypt(key, bogus); err == nil {
			t.Error("expected padding error, got nil")
		}
	})
}
