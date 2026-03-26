package main

import (
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/joho/godotenv"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"

	"github.com/crestalnetwork/intentkit/integrations/wechat/api"
	"github.com/crestalnetwork/intentkit/integrations/wechat/bot"
	"github.com/crestalnetwork/intentkit/integrations/wechat/config"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	_ = godotenv.Load()

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

	db, err := gorm.Open(postgres.Open(cfg.DatabaseDSN()), &gorm.Config{})
	if err != nil {
		slog.Error("Failed to connect to database", "error", err)
		os.Exit(1)
	}

	apiClient := api.NewClient(cfg.InternalBaseURL)

	manager := bot.NewManager(db, cfg, apiClient)

	go manager.Start()
	slog.Info("WeChat Integration Started")

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	slog.Info("Shutting down...")
	manager.Stop()
	slog.Info("Shutdown complete")
}
