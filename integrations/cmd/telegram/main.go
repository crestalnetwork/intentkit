package main

import (
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/joho/godotenv"
	"github.com/redis/go-redis/v9"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"

	"github.com/crestalnetwork/intentkit/integrations/telegram/api"
	"github.com/crestalnetwork/intentkit/integrations/telegram/bot"
	"github.com/crestalnetwork/intentkit/integrations/telegram/config"
)

func main() {
	// Initialize Logger
	logLevel := slog.LevelInfo
	if os.Getenv("DEBUG") == "true" {
		logLevel = slog.LevelDebug
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: logLevel}))
	slog.SetDefault(logger)

	// Load .env file
	// We ignore the error because in production (k8s/docker) the env vars might be injected directly
	// and no .env file might be present. But for local dev it is useful.
	_ = godotenv.Load()

	// Load Configuration
	cfg, err := config.Load()
	if err != nil {
		slog.Error("Failed to load config", "error", err)
		os.Exit(1)
	}
	logger = logger.With("env", cfg.Env)

	if cfg.Release != "" {
		logger = logger.With("release", cfg.Release)
	}
	slog.SetDefault(logger)

	// Initialize Database
	db, err := gorm.Open(postgres.Open(cfg.DatabaseDSN()), &gorm.Config{})
	if err != nil {
		slog.Error("Failed to connect to database", "error", err)
		os.Exit(1)
	}

	// Auto Migrate (optional, but good for ensuring schema matches models)
	// In production, we assume schema is managed by migration scripts in the main repo.
	// But minimal migration for new tables or ensuring columns exist is fine.
	// We only strictly need Agent and AgentData read access, and AgentData write access.
	// For safety, we won't auto-migrate Agent table as it is core. AgentData is also core.
	// So we skip auto-migration to avoid altering core tables unexpectedly.

	// Initialize Redis
	redisClient := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})

	// Initialize API Client
	apiClient := api.NewClient(cfg.InternalBaseURL)

	// Initialize Bot Manager
	manager := bot.NewManager(db, cfg, apiClient, redisClient)

	// Start Manager
	go manager.Start()
	slog.Info("Telegram Integration Started")

	// Graceful Shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	slog.Info("Shutting down...")
	manager.Stop()
	slog.Info("Shutdown complete")
}
