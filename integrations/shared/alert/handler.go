package alert

import (
	"context"
	"fmt"
	"log/slog"
	"runtime"
	"strings"
	"sync/atomic"
)

// Handler wraps an inner slog.Handler and forwards records at Error+ to an
// async alert pipeline. Non-error records pass through untouched.
//
// To preserve slog's group semantics (a group opened via WithGroup applies
// only to attrs added *after* it), persisted attrs are stored with their
// effective key already prefixed at the time WithAttrs is called.
type Handler struct {
	inner    slog.Handler
	pipeline *pipeline

	// boundAttrs are attrs applied via With(); their keys already include
	// any group prefix that was active when they were bound.
	boundAttrs []prefixedAttr

	// groupPrefix is the dot-joined group path that applies to attrs added
	// from this point forward (both via WithAttrs and via the record).
	groupPrefix string
}

type prefixedAttr struct {
	key string
	val slog.Value
}

func newHandler(inner slog.Handler, p *pipeline) *Handler {
	return &Handler{inner: inner, pipeline: p}
}

func (h *Handler) Enabled(ctx context.Context, level slog.Level) bool {
	return h.inner.Enabled(ctx, level)
}

func (h *Handler) Handle(ctx context.Context, record slog.Record) error {
	if record.Level >= slog.LevelError {
		h.pipeline.enqueue(h.format(record))
	}
	return h.inner.Handle(ctx, record)
}

func (h *Handler) WithAttrs(attrs []slog.Attr) slog.Handler {
	bound := make([]prefixedAttr, len(h.boundAttrs), len(h.boundAttrs)+len(attrs))
	copy(bound, h.boundAttrs)
	for _, a := range attrs {
		bound = append(bound, prefixedAttr{key: h.prefixed(a.Key), val: a.Value})
	}
	return &Handler{
		inner:       h.inner.WithAttrs(attrs),
		pipeline:    h.pipeline,
		boundAttrs:  bound,
		groupPrefix: h.groupPrefix,
	}
}

func (h *Handler) WithGroup(name string) slog.Handler {
	if name == "" {
		return h
	}
	return &Handler{
		inner:       h.inner.WithGroup(name),
		pipeline:    h.pipeline,
		boundAttrs:  h.boundAttrs,
		groupPrefix: h.prefixed(name),
	}
}

func (h *Handler) prefixed(key string) string {
	if h.groupPrefix == "" {
		return key
	}
	return h.groupPrefix + "." + key
}

// format renders a record into the alert text. Layout:
//
//	🚨 LEVEL | source=file:line
//	📦 release | 🌍 env
//
//	message
//	key1=val1 key2=val2
//
// release/env are pulled from the persisted attrs added via With(); other
// attrs are flattened after the message body. Only the most recently bound
// release/env values win, matching slog's "last write" semantics.
func (h *Handler) format(record slog.Record) string {
	source := sourceOf(record)

	var release, env string
	contextAttrs := make([]prefixedAttr, 0, len(h.boundAttrs))
	for _, a := range h.boundAttrs {
		switch a.key {
		case "release":
			release = a.val.String()
		case "env":
			env = a.val.String()
		default:
			contextAttrs = append(contextAttrs, a)
		}
	}
	if release == "" {
		release = "unknown"
	}
	if env == "" {
		env = "unknown"
	}

	var b strings.Builder
	fmt.Fprintf(&b, "🚨 %s", record.Level.String())
	if source != "" {
		fmt.Fprintf(&b, " | source=%s", source)
	}
	fmt.Fprintf(&b, "\n📦 %s | 🌍 %s\n\n%s", release, env, record.Message)

	for _, a := range contextAttrs {
		fmt.Fprintf(&b, " %s=%v", a.key, a.val.Resolve().Any())
	}
	record.Attrs(func(a slog.Attr) bool {
		fmt.Fprintf(&b, " %s=%v", h.prefixed(a.Key), a.Value.Resolve().Any())
		return true
	})

	return b.String()
}

func sourceOf(record slog.Record) string {
	if record.PC == 0 {
		return ""
	}
	frames := runtime.CallersFrames([]uintptr{record.PC})
	frame, _ := frames.Next()
	if frame.File == "" {
		return ""
	}
	return fmt.Sprintf("%s:%d", frame.File, frame.Line)
}

// pipeline serializes alert delivery. enqueue is non-blocking; overflow
// and rate-limit rejections both bump dropped counters that the next
// successful send prepends as a notice.
type pipeline struct {
	queue   chan string
	limiter *rateLimiter
	sender  Sender

	dropped     atomic.Int64
	rateDropped atomic.Int64

	stop chan struct{}
	done chan struct{}
}

func (p *pipeline) enqueue(message string) {
	select {
	case p.queue <- message:
	default:
		p.dropped.Add(1)
	}
}

// run pulls messages from the queue and dispatches them. On stop, it
// drains anything already queued before exiting so a graceful shutdown
// doesn't lose alerts that were emitted moments before SIGTERM.
func (p *pipeline) run() {
	defer close(p.done)
	for {
		select {
		case msg := <-p.queue:
			p.dispatch(msg)
		case <-p.stop:
			for {
				select {
				case msg := <-p.queue:
					p.dispatch(msg)
				default:
					return
				}
			}
		}
	}
}

func (p *pipeline) dispatch(msg string) {
	// Each dispatch gets its own bounded context so an in-flight HTTP send
	// is not killed when the worker is told to stop.
	ctx, cancel := context.WithTimeout(context.Background(), dispatchTimeout)
	defer cancel()

	allowed, err := p.limiter.Allow(ctx)
	if err != nil {
		// Fail open: if Redis is unavailable, send anyway rather than
		// silently swallow alerts. Worst case we exceed the budget; better
		// than missing a real production error.
		allowed = true
	}
	if !allowed {
		p.rateDropped.Add(1)
		return
	}

	dropped := p.dropped.Swap(0) + p.rateDropped.Swap(0)
	if dropped > 0 {
		msg = fmt.Sprintf("[⚠️ %d messages dropped due to rate limit]\n\n%s", dropped, msg)
	}

	if err := p.sender.Send(ctx, msg); err != nil {
		// Cannot use slog here: it would feed into ourselves and loop.
		fmt.Fprintf(stderrSink, "[alert] send failed: %v\n", err)
	}
}
