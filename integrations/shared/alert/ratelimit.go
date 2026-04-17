package alert

import (
	"context"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

// rateLimitKey is shared with the Python integration so all stacks draw
// from the same per-minute alert budget. Do not change without coordinating
// with intentkit/utils/alert_handler.py.
const rateLimitKey = "intentkit:alert:rate_limit:alert"

// rateLimiter implements a Redis sliding-window counter.
//
// Each Allow call atomically prunes expired entries, counts current ones,
// and conditionally reserves a slot. If the slot would push the counter
// over Max, the reservation is rolled back and Allow returns false.
type rateLimiter struct {
	redis  *redis.Client
	max    int
	window time.Duration
}

func newRateLimiter(client *redis.Client, max int, window time.Duration) *rateLimiter {
	return &rateLimiter{redis: client, max: max, window: window}
}

func (r *rateLimiter) Allow(ctx context.Context) (bool, error) {
	// Score and member match the Python side exactly: seconds-since-epoch
	// as a float, with the member being its string form. Using nanoseconds
	// would put Go entries 9 orders of magnitude above any windowStart
	// Python could ever compute, so each side would silently evict the
	// other and the "shared budget" guarantee would be broken.
	nowSec := float64(time.Now().UnixNano()) / 1e9
	windowStart := nowSec - r.window.Seconds()
	member := strconv.FormatFloat(nowSec, 'f', -1, 64)

	pipe := r.redis.Pipeline()
	pipe.ZRemRangeByScore(ctx, rateLimitKey, "0", strconv.FormatFloat(windowStart, 'f', -1, 64))
	countCmd := pipe.ZCard(ctx, rateLimitKey)
	pipe.ZAdd(ctx, rateLimitKey, redis.Z{Score: nowSec, Member: member})
	pipe.Expire(ctx, rateLimitKey, r.window+10*time.Second)
	if _, err := pipe.Exec(ctx); err != nil {
		return false, err
	}

	// countCmd counts *before* the ZAdd; the limit is hit when the existing
	// count already meets max. Roll back our reservation in that case.
	if countCmd.Val() >= int64(r.max) {
		_ = r.redis.ZRem(ctx, rateLimitKey, member).Err()
		return false, nil
	}
	return true, nil
}
