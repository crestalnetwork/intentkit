// Package alert wires a slog.Handler that forwards Error+ records to an
// external alert channel (Telegram or Slack) with Redis-based rate
// limiting. Non-error records pass through to the underlying handler with
// no overhead.
//
// The package mirrors intentkit/utils/alert_handler.py on the Python side:
// same Redis key, same default 3-per-minute budget, same drop-counter
// notice. Operators can drive both stacks from a single secrets bundle.
package alert

import (
	"io"
	"os"
	"time"

	"log/slog"

	"github.com/redis/go-redis/v9"
)

const (
	queueSize         = 1000
	alertHTTPTimeout  = 10 * time.Second
	alertRetryWait    = 1 * time.Second
	alertRetryMaxWait = 5 * time.Second
	// dispatchTimeout bounds a single Allow + Send round-trip; bigger than
	// the resty client's per-call timeout so retries can finish.
	dispatchTimeout = 30 * time.Second
	// shutdownDrainGrace caps how long Wrap()'s shutdown closure will wait
	// for the worker to flush queued messages on SIGTERM.
	shutdownDrainGrace = 15 * time.Second
)

// stderrSink is overridable for tests so we can capture diagnostic output
// without writing to the real os.Stderr.
var stderrSink io.Writer = os.Stderr

// Wrap returns a slog.Handler that forwards Error+ records to the alert
// channel described by cfg. When alert credentials are missing, Wrap
// returns the inner handler unchanged so callers don't need a nil check.
//
// The returned shutdown closure should be invoked during graceful
// termination; it stops the worker goroutine and waits up to a short grace
// period for the queue to drain. When alerts are disabled, shutdown is a
// no-op.
func Wrap(inner slog.Handler, cfg *Config, redisClient *redis.Client) (slog.Handler, func()) {
	if cfg == nil {
		return inner, func() {}
	}
	backend := cfg.Backend()
	if backend == BackendNone {
		return inner, func() {}
	}
	if redisClient == nil {
		// Rate limiting requires Redis; without it we can't honor the
		// shared budget. Fall back to log-only rather than risk flooding.
		return inner, func() {}
	}

	var sender Sender
	switch backend {
	case BackendTelegram:
		sender = newTelegramSender(cfg.TgBotToken, cfg.TgChatID)
	case BackendSlack:
		sender = newSlackSender(cfg.SlackToken, cfg.SlackChannel)
	default:
		return inner, func() {}
	}

	limiter := newRateLimiter(redisClient, cfg.MaxMessages, time.Duration(cfg.TimeWindow)*time.Second)
	p := &pipeline{
		queue:   make(chan string, queueSize),
		limiter: limiter,
		sender:  sender,
		stop:    make(chan struct{}),
		done:    make(chan struct{}),
	}
	go p.run()

	shutdown := func() {
		close(p.stop)
		select {
		case <-p.done:
		case <-time.After(shutdownDrainGrace):
		}
	}
	return newHandler(inner, p), shutdown
}
