package bot

import (
	"log/slog"
	"net/http"

	"github.com/crestalnetwork/intentkit/integrations/lark/larkclient"
)

// pushRequest is the body the Python API posts to /lark/push to send a
// proactive message to a Lark chat. The Python side already knows the tenant_key
// (it's stored on the team's channel row); we just need the tenant-bound client
// to do the send, since the SDK token chain lives in this process.
type pushRequest struct {
	TenantKey string `json:"tenant_key"`
	ChatID    string `json:"chat_id"`
	Text      string `json:"text"`
}

// handlePush sends a proactive text message to a Lark chat for a tenant.
func (m *Manager) handlePush(w http.ResponseWriter, r *http.Request) {
	if !m.authorizeInternal(w, r) {
		return
	}
	var req pushRequest
	if err := readInternalJSON(r, &req); err != nil ||
		req.TenantKey == "" || req.ChatID == "" || req.Text == "" {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	client := larkclient.ForTenant(m.sharedLark, req.TenantKey)
	if err := client.SendText(r.Context(), req.ChatID, req.Text); err != nil {
		slog.Error("lark: proactive push failed", "chat_id", req.ChatID, "error", err)
		http.Error(w, "send failed", http.StatusBadGateway)
		return
	}
	writeJSONOK(w)
}
