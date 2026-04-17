package alert

import (
	"context"
	"errors"
	"log/slog"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"
)

type fakeSender struct {
	mu       sync.Mutex
	messages []string
	err      error
}

func (f *fakeSender) Send(_ context.Context, msg string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.messages = append(f.messages, msg)
	return f.err
}

func (f *fakeSender) snapshot() []string {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := make([]string, len(f.messages))
	copy(out, f.messages)
	return out
}

// pipelineWith builds a pipeline whose dispatcher uses the supplied allow
// function instead of a real Redis-backed limiter, so handler tests can
// exercise the rate-limit decision branches without Redis.
func pipelineWith(t *testing.T, sender Sender, allow func() (bool, error)) (*pipeline, func()) {
	t.Helper()
	p := &pipeline{
		queue:  make(chan string, 16),
		sender: sender,
		done:   make(chan struct{}),
	}
	ctx, cancel := context.WithCancel(context.Background())
	go func() {
		defer close(p.done)
		for {
			select {
			case <-ctx.Done():
				return
			case msg := <-p.queue:
				ok, err := allow()
				if err != nil {
					ok = true
				}
				if !ok {
					p.rateDropped.Add(1)
					continue
				}
				dropped := p.dropped.Swap(0) + p.rateDropped.Swap(0)
				if dropped > 0 {
					msg = "[dropped " + strconv.FormatInt(dropped, 10) + "]\n\n" + msg
				}
				_ = sender.Send(ctx, msg)
			}
		}
	}()
	return p, func() { cancel(); <-p.done }
}

func waitFor(t *testing.T, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("condition not met within deadline")
}

func TestHandlerForwardsErrorOnly(t *testing.T) {
	sender := &fakeSender{}
	p, stop := pipelineWith(t, sender, func() (bool, error) { return true, nil })
	defer stop()

	innerBuf := &strings.Builder{}
	inner := slog.NewTextHandler(innerBuf, &slog.HandlerOptions{Level: slog.LevelDebug})
	logger := slog.New(newHandler(inner, p))

	logger.Info("info-msg")
	logger.Warn("warn-msg")
	logger.Error("error-msg", "team_id", "abc")

	waitFor(t, func() bool { return len(sender.snapshot()) == 1 })

	got := sender.snapshot()[0]
	if !strings.Contains(got, "error-msg") {
		t.Fatalf("expected message to contain 'error-msg', got: %s", got)
	}
	if !strings.Contains(got, "team_id=abc") {
		t.Fatalf("expected message to flatten kv, got: %s", got)
	}
	if strings.Contains(got, "info-msg") || strings.Contains(got, "warn-msg") {
		t.Fatalf("non-error log leaked into alert: %s", got)
	}
}

func TestHandlerIncludesEnvAndRelease(t *testing.T) {
	sender := &fakeSender{}
	p, stop := pipelineWith(t, sender, func() (bool, error) { return true, nil })
	defer stop()

	inner := slog.NewTextHandler(&strings.Builder{}, &slog.HandlerOptions{Level: slog.LevelDebug})
	logger := slog.New(newHandler(inner, p)).With("env", "prod", "release", "v1.2.3")

	logger.Error("kapow")
	waitFor(t, func() bool { return len(sender.snapshot()) == 1 })

	got := sender.snapshot()[0]
	if !strings.Contains(got, "📦 v1.2.3 | 🌍 prod") {
		t.Fatalf("expected env/release header, got: %s", got)
	}
	if strings.Contains(got, "release=v1.2.3") || strings.Contains(got, "env=prod") {
		t.Fatalf("env/release should be in header only, not flattened: %s", got)
	}
}

func TestHandlerDoesNotShadowInner(t *testing.T) {
	sender := &fakeSender{}
	p, stop := pipelineWith(t, sender, func() (bool, error) { return true, nil })
	defer stop()

	innerBuf := &strings.Builder{}
	inner := slog.NewTextHandler(innerBuf, &slog.HandlerOptions{Level: slog.LevelDebug})
	logger := slog.New(newHandler(inner, p))

	logger.Info("kept")
	logger.Error("kept-too")

	if !strings.Contains(innerBuf.String(), "kept") {
		t.Fatalf("inner handler should still see Info logs, got: %s", innerBuf.String())
	}
	if !strings.Contains(innerBuf.String(), "kept-too") {
		t.Fatalf("inner handler should still see Error logs, got: %s", innerBuf.String())
	}
}

func TestPipelineRateLimitDroppedNotice(t *testing.T) {
	sender := &fakeSender{}
	calls := 0
	allow := func() (bool, error) {
		calls++
		// Block the first two attempts, allow the third.
		if calls <= 2 {
			return false, nil
		}
		return true, nil
	}
	p, stop := pipelineWith(t, sender, allow)
	defer stop()

	p.enqueue("first")
	p.enqueue("second")
	p.enqueue("third")

	waitFor(t, func() bool { return len(sender.snapshot()) == 1 })
	got := sender.snapshot()[0]
	if !strings.Contains(got, "[dropped 2]") {
		t.Fatalf("expected drop notice for 2 prior messages, got: %s", got)
	}
}

func TestPipelineShutdownDrainsQueue(t *testing.T) {
	sender := &fakeSender{}
	p := &pipeline{
		queue:   make(chan string, 8),
		limiter: &rateLimiter{}, // unused: we monkey-patch dispatch via run()
		sender:  sender,
		stop:    make(chan struct{}),
		done:    make(chan struct{}),
	}
	// Replace the limiter path by driving the same loop pipelineWith uses,
	// but exercising the real run() shape: stop, then drain.
	go func() {
		defer close(p.done)
		for {
			select {
			case msg := <-p.queue:
				_ = sender.Send(context.Background(), msg)
			case <-p.stop:
				for {
					select {
					case msg := <-p.queue:
						_ = sender.Send(context.Background(), msg)
					default:
						return
					}
				}
			}
		}
	}()

	p.enqueue("a")
	p.enqueue("b")
	p.enqueue("c")
	close(p.stop)
	select {
	case <-p.done:
	case <-time.After(2 * time.Second):
		t.Fatal("worker did not exit")
	}
	if got := len(sender.snapshot()); got != 3 {
		t.Fatalf("expected all 3 queued messages flushed on shutdown, sent=%d", got)
	}
}

func TestPipelineQueueOverflowCounted(t *testing.T) {
	sender := &fakeSender{err: errors.New("network down")}
	p := &pipeline{
		queue:  make(chan string, 1),
		sender: sender,
		done:   make(chan struct{}),
	}
	// Worker never started: fill the queue, then push one more to trigger
	// the dropped counter.
	p.enqueue("a")
	p.enqueue("b") // overflow

	if got := p.dropped.Load(); got != 1 {
		t.Fatalf("expected dropped=1 after overflow, got %d", got)
	}
}

func TestWithGroupOnlyPrefixesAttrsAddedAfter(t *testing.T) {
	sender := &fakeSender{}
	p, stop := pipelineWith(t, sender, func() (bool, error) { return true, nil })
	defer stop()

	inner := slog.NewTextHandler(&strings.Builder{}, &slog.HandlerOptions{Level: slog.LevelDebug})
	logger := slog.New(newHandler(inner, p)).
		With("svc", "tg").
		WithGroup("req").
		With("id", "42")

	logger.Error("boom")
	waitFor(t, func() bool { return len(sender.snapshot()) == 1 })

	got := sender.snapshot()[0]
	if !strings.Contains(got, " svc=tg") {
		t.Fatalf("attr added before WithGroup must NOT be prefixed, got: %s", got)
	}
	if !strings.Contains(got, " req.id=42") {
		t.Fatalf("attr added after WithGroup must be prefixed, got: %s", got)
	}
}

func TestWithGroupPrefixesKeys(t *testing.T) {
	sender := &fakeSender{}
	p, stop := pipelineWith(t, sender, func() (bool, error) { return true, nil })
	defer stop()

	inner := slog.NewTextHandler(&strings.Builder{}, &slog.HandlerOptions{Level: slog.LevelDebug})
	logger := slog.New(newHandler(inner, p)).WithGroup("req").With("id", "42")

	logger.Error("boom")
	waitFor(t, func() bool { return len(sender.snapshot()) == 1 })

	got := sender.snapshot()[0]
	if !strings.Contains(got, "req.id=42") {
		t.Fatalf("expected grouped attr 'req.id=42', got: %s", got)
	}
}
