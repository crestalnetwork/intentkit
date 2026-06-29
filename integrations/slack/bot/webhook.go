package bot

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"github.com/slack-go/slack"
)

// maxBodyBytes caps a webhook request body (Slack event payloads are small).
const maxBodyBytes = 2 << 20 // 2 MiB

// signatureMaxSkew rejects requests whose timestamp is older/newer than this
// (replay protection).
const signatureMaxSkew = 5 * 60 // seconds

// handleEventsRequest is the Slack Events API webhook: it verifies the request
// signature, answers the url_verification handshake, and dispatches message /
// app_mention events to the owning team. The HTTP 200 is sent immediately so
// Slack doesn't retry; the lead-agent work runs on its own goroutine.
func (m *Manager) handleEventsRequest(w http.ResponseWriter, r *http.Request) {
	body, ok := m.readVerified(w, r)
	if !ok {
		return
	}

	var probe struct {
		Type      string `json:"type"`
		Challenge string `json:"challenge"`
		TeamID    string `json:"team_id"`
		Event     struct {
			Type string `json:"type"`
		} `json:"event"`
	}
	if err := json.Unmarshal(body, &probe); err != nil {
		http.Error(w, "bad payload", http.StatusBadRequest)
		return
	}

	// URL verification handshake (sent once when the Request URL is configured).
	if probe.Type == "url_verification" {
		w.Header().Set("Content-Type", "text/plain")
		_, _ = w.Write([]byte(probe.Challenge))
		return
	}

	w.WriteHeader(http.StatusOK)

	if probe.Type != "event_callback" {
		return
	}
	switch probe.Event.Type {
	case "message", "app_mention":
		teamID, client, ok := m.resolveWorkspace(probe.TeamID)
		if !ok {
			slog.Warn("slack: event for unmapped workspace", "workspace", probe.TeamID)
			return
		}
		go m.handleMessageEvent(client, teamID, body)
	}
}

// handleInteractionRequest handles block-action (choice button) callbacks, sent
// as application/x-www-form-urlencoded with a `payload` JSON field.
func (m *Manager) handleInteractionRequest(w http.ResponseWriter, r *http.Request) {
	body, ok := m.readVerified(w, r)
	if !ok {
		return
	}
	w.WriteHeader(http.StatusOK)

	form, err := url.ParseQuery(string(body))
	if err != nil {
		return
	}
	raw := form.Get("payload")
	if raw == "" {
		return
	}
	var callback slack.InteractionCallback
	if err := json.Unmarshal([]byte(raw), &callback); err != nil {
		slog.Error("slack: failed to parse interaction payload", "error", err)
		return
	}
	teamID, client, ok := m.resolveWorkspace(callback.Team.ID)
	if !ok {
		return
	}
	go m.handleInteraction(client, teamID, &callback)
}

// readVerified reads the (size-capped) request body and verifies the Slack
// signature. On failure it writes the appropriate status and returns ok=false.
//
// SECURITY: this is the trust boundary for inbound webhooks — every request is
// authenticated here via the app signing secret before any processing.
func (m *Manager) readVerified(w http.ResponseWriter, r *http.Request) ([]byte, bool) {
	body, err := io.ReadAll(io.LimitReader(r.Body, maxBodyBytes))
	if err != nil {
		http.Error(w, "read error", http.StatusBadRequest)
		return nil, false
	}
	if !verifySlackSignature(m.cfg.SlackSigningSecret, r.Header, body) {
		slog.Warn("slack: webhook signature verification failed")
		http.Error(w, "invalid signature", http.StatusUnauthorized)
		return nil, false
	}
	return body, true
}

// verifySlackSignature checks the X-Slack-Signature HMAC-SHA256 over
// "v0:{timestamp}:{body}" and rejects stale timestamps. Uses a constant-time
// compare. See https://api.slack.com/authentication/verifying-requests-from-slack
func verifySlackSignature(signingSecret string, header http.Header, body []byte) bool {
	if signingSecret == "" {
		return false
	}
	ts := header.Get("X-Slack-Request-Timestamp")
	sig := header.Get("X-Slack-Signature")
	if ts == "" || sig == "" {
		return false
	}
	tsInt, err := strconv.ParseInt(ts, 10, 64)
	if err != nil {
		return false
	}
	if d := time.Now().Unix() - tsInt; d > signatureMaxSkew || d < -signatureMaxSkew {
		return false
	}
	mac := hmac.New(sha256.New, []byte(signingSecret))
	mac.Write([]byte("v0:" + ts + ":"))
	mac.Write(body)
	expected := "v0=" + hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(expected), []byte(sig))
}
