package bot

import (
	"log/slog"
	"net/http"

	authenv1 "github.com/larksuite/oapi-sdk-go/v3/service/authen/v1"
)

// exchangeRequest is the body the Python API posts to /lark/exchange after it
// has authenticated the team admin and verified the OAuth state. CreatedBy is
// the installing admin's user id, forwarded so the stored install is attributed
// to them.
type exchangeRequest struct {
	Code      string `json:"code"`
	TeamID    string `json:"team_id"`
	CreatedBy string `json:"created_by"`
}

// handleExchange runs the ISV code->tenant_key exchange for an authorized
// enterprise and stores the install on the team's lark channel row. State /
// admin verification already happened in the Python API; this internal endpoint
// only needs the shared secret (the SDK token chain that the exchange requires
// lives in this process, which is why the Python side delegates here).
func (m *Manager) handleExchange(w http.ResponseWriter, r *http.Request) {
	if !m.authorizeInternal(w, r) {
		return
	}
	var req exchangeRequest
	if err := readInternalJSON(r, &req); err != nil || req.Code == "" || req.TeamID == "" || req.CreatedBy == "" {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	ctx := r.Context()
	resp, err := m.sharedLark.Authen.AccessToken.Create(ctx, authenv1.NewCreateAccessTokenReqBuilder().
		Body(authenv1.NewCreateAccessTokenReqBodyBuilder().
			GrantType("authorization_code").
			Code(req.Code).
			Build()).
		Build())
	if err != nil || !resp.Success() || resp.Data == nil || resp.Data.TenantKey == nil {
		slog.Error("lark: oauth code exchange failed", "team_id", req.TeamID, "error", err)
		http.Error(w, "exchange failed", http.StatusBadGateway)
		return
	}
	tenantKey := *resp.Data.TenantKey

	if err := m.apiClient.SetChannelConfig(ctx, req.TeamID, channelType,
		map[string]any{"tenant_key": tenantKey}, req.CreatedBy); err != nil {
		slog.Error("lark: failed to store tenant install", "team_id", req.TeamID, "error", err)
		http.Error(w, "persist failed", http.StatusInternalServerError)
		return
	}
	slog.Info("lark: tenant authorized", "team_id", req.TeamID, "tenant_key", tenantKey)
	writeJSONOK(w)
}
