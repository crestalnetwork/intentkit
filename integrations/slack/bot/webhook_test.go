package bot

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"strconv"
	"testing"
	"time"
)

func signBody(secret, ts string, body []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte("v0:" + ts + ":"))
	mac.Write(body)
	return "v0=" + hex.EncodeToString(mac.Sum(nil))
}

func TestVerifySlackSignature(t *testing.T) {
	secret := "shhh"
	body := []byte(`{"type":"event_callback"}`)
	now := strconv.FormatInt(time.Now().Unix(), 10)

	good := http.Header{}
	good.Set("X-Slack-Request-Timestamp", now)
	good.Set("X-Slack-Signature", signBody(secret, now, body))
	if !verifySlackSignature(secret, good, body) {
		t.Error("valid signature should pass")
	}

	if verifySlackSignature("other-secret", good, body) {
		t.Error("signature under the wrong secret must fail")
	}
	if verifySlackSignature(secret, good, []byte(`{"type":"x"}`)) {
		t.Error("tampered body must fail")
	}

	old := strconv.FormatInt(time.Now().Unix()-3600, 10)
	stale := http.Header{}
	stale.Set("X-Slack-Request-Timestamp", old)
	stale.Set("X-Slack-Signature", signBody(secret, old, body))
	if verifySlackSignature(secret, stale, body) {
		t.Error("stale timestamp must fail (replay protection)")
	}

	if verifySlackSignature(secret, http.Header{}, body) {
		t.Error("missing headers must fail")
	}
	if verifySlackSignature("", good, body) {
		t.Error("empty signing secret must fail")
	}
}
