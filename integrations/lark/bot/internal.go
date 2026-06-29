package bot

import (
	"crypto/subtle"
	"encoding/json"
	"io"
	"net/http"
)

// maxInternalBodyBytes caps the (small) JSON bodies of the internal reverse
// endpoints called by the Python API.
const maxInternalBodyBytes = 1 << 20 // 1 MiB

// authorizeInternal gates the internal-only endpoints (/lark/exchange,
// /lark/push). The Lark service port is public (Lark posts events to it), so
// these reverse calls from the Python API must present the shared secret in the
// X-Internal-Secret header. Fails closed when the secret isn't configured.
func (m *Manager) authorizeInternal(w http.ResponseWriter, r *http.Request) bool {
	if m.cfg.LarkInternalSecret == "" {
		http.Error(w, "internal endpoint disabled", http.StatusServiceUnavailable)
		return false
	}
	got := r.Header.Get("X-Internal-Secret")
	if subtle.ConstantTimeCompare([]byte(got), []byte(m.cfg.LarkInternalSecret)) != 1 {
		http.Error(w, "forbidden", http.StatusForbidden)
		return false
	}
	return true
}

// readInternalJSON decodes a capped JSON request body.
func readInternalJSON(r *http.Request, v any) error {
	body, err := io.ReadAll(io.LimitReader(r.Body, maxInternalBodyBytes))
	if err != nil {
		return err
	}
	return json.Unmarshal(body, v)
}

// writeJSONOK writes a {"ok":true} 200 response.
func writeJSONOK(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write([]byte(`{"ok":true}`))
}
