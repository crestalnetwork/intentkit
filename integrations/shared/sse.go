package shared

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"

	"github.com/crestalnetwork/intentkit/integrations/types"
	"resty.dev/v3"
)

// StreamCallback is called for each ChatMessage received from the SSE stream.
type StreamCallback func(msg types.ChatMessage) error

// StreamRequest sends a POST to the given URL with JSON body, reads the SSE stream,
// and calls cb for each ChatMessage event.
func StreamRequest(ctx context.Context, baseURL, path string, payload interface{}, cb StreamCallback) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	url := baseURL + path

	// Channel to collect errors from callbacks
	errCh := make(chan error, 1)
	// Channel to signal stream completion
	doneCh := make(chan error, 1)

	es := resty.NewEventSource().
		SetURL(url).
		SetMethod(resty.MethodPost).
		SetBody(bytes.NewReader(body)).
		SetHeader("Content-Type", "application/json").
		SetRetryCount(0) // one-shot stream, no retries

	es.OnMessage(func(e any) {
		event, ok := e.(*resty.Event)
		if !ok {
			return
		}

		// Skip empty data
		if event.Data == "" {
			return
		}

		// Handle stream termination signal
		if event.Data == "[DONE]" {
			es.Close()
			return
		}

		var msg types.ChatMessage
		if err := json.Unmarshal([]byte(event.Data), &msg); err != nil {
			slog.Error("Failed to unmarshal SSE event data", "error", err, "data", event.Data)
			return
		}

		if err := cb(msg); err != nil {
			slog.Error("Stream callback error", "error", err)
			select {
			case errCh <- err:
			default:
			}
			es.Close()
		}
	}, nil)

	es.OnError(func(err error) {
		slog.Error("SSE stream error", "error", err, "url", url)
	})

	es.OnRequestFailure(func(err error, res *http.Response) {
		if res != nil {
			res.Body.Close()
			select {
			case doneCh <- fmt.Errorf("SSE request failed with status %d: %w", res.StatusCode, err):
			default:
			}
		} else {
			select {
			case doneCh <- fmt.Errorf("SSE request failed: %w", err):
			default:
			}
		}
	})

	// Run the EventSource connection in a goroutine so we can respect context cancellation
	go func() {
		doneCh <- es.Get()
	}()

	select {
	case <-ctx.Done():
		es.Close()
		return ctx.Err()
	case err := <-errCh:
		return err
	case err := <-doneCh:
		// Check if there was a callback error too
		select {
		case cbErr := <-errCh:
			return cbErr
		default:
		}
		// Treat clean EOF as normal stream completion. The preferred termination
		// signal is [DONE] (which triggers es.Close() and returns nil above);
		// EOF is a fallback for endpoints that haven't adopted [DONE] yet.
		if errors.Is(err, io.EOF) {
			return nil
		}
		return err
	}
}
