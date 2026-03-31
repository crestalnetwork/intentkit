package config

import (
	"fmt"

	"github.com/hack-fan/config"
)

type Config struct {
	Env     string `default:"local"`
	Debug   bool   `default:"false"`
	Release string `env:"RELEASE"`

	// DB
	DBHost     string `env:"DB_HOST"`
	DBPort     string `env:"DB_PORT" default:"5432"`
	DBName     string `env:"DB_NAME"`
	DBUsername string `env:"DB_USERNAME"`
	DBPassword string `env:"DB_PASSWORD"`

	// Internal API
	InternalBaseURL string `env:"INTERNAL_BASE_URL" default:"http://intent-api"`

	// Redis
	RedisHost     string `env:"REDIS_HOST"`
	RedisPort     string `env:"REDIS_PORT" default:"6379"`
	RedisPassword string `env:"REDIS_PASSWORD"`
	RedisDB       int    `env:"REDIS_DB" default:"0"`

	// Telegram
	TgNewAgentPollInterval int `env:"TG_NEW_AGENT_POLL_INTERVAL" default:"10"`
}

func Load() (*Config, error) {
	var cfg Config
	// Load from ENV
	if err := config.Load(&cfg); err != nil {
		return nil, err
	}
	return &cfg, nil
}

func (c *Config) DatabaseDSN() string {
	// sslmode=disable is intentional: the Go integration connects to the database
	// within a private network where TLS is not required.
	dsn := fmt.Sprintf("host=%s dbname=%s port=%s sslmode=disable TimeZone=UTC",
		c.DBHost, c.DBName, c.DBPort)
	if c.DBUsername != "" {
		dsn += fmt.Sprintf(" user=%s", c.DBUsername)
	}
	if c.DBPassword != "" {
		dsn += fmt.Sprintf(" password=%s", c.DBPassword)
	}
	return dsn
}
