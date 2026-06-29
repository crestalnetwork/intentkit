package bot

import (
	"io"
	"net/http"

	larkevent "github.com/larksuite/oapi-sdk-go/v3/event"
)

// maxBodyBytes caps a webhook request body (Lark event payloads are small).
const maxBodyBytes = 2 << 20 // 2 MiB

// handleEventsRequest is the Lark event-subscription webhook. The SDK dispatcher
// decrypts (AES) + verifies (verification token) the body, answers the
// url_verification handshake, captures the app_ticket, and routes message /
// card-action events to the handlers wired in NewManager.
func (m *Manager) handleEventsRequest(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, maxBodyBytes))
	if err != nil {
		http.Error(w, "read error", http.StatusBadRequest)
		return
	}
	resp := m.dispatcher.Handle(r.Context(), &larkevent.EventReq{
		Header:     r.Header,
		Body:       body,
		RequestURI: r.RequestURI,
	})
	for k, vals := range resp.Header {
		for _, v := range vals {
			w.Header().Add(k, v)
		}
	}
	status := resp.StatusCode
	if status == 0 {
		status = http.StatusOK
	}
	w.WriteHeader(status)
	_, _ = w.Write(resp.Body)
}
