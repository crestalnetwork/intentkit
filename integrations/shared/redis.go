package shared

import (
	"fmt"

	"github.com/redis/go-redis/v9"
)

// NewRedisClient builds a redis.Client from the standard env-derived fields
// every binary loads (REDIS_HOST/PORT/PASSWORD/DB). Returns nil when host
// is empty so callers can treat Redis as optional.
func NewRedisClient(host, port, password string, db int) *redis.Client {
	if host == "" {
		return nil
	}
	return redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", host, port),
		Password: password,
		DB:       db,
	})
}
