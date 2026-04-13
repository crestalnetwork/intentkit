package bot

import (
	"bytes"
	"context"
	"fmt"
	"log/slog"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/mymmrac/telego"
	tu "github.com/mymmrac/telego/telegoutil"
)

// TelegramSender implements shared.MessageSender for Telegram.
type TelegramSender struct {
	bot    *telego.Bot
	chatID int64
}

// NewTelegramSender creates a new TelegramSender.
func NewTelegramSender(bot *telego.Bot, chatID int64) *TelegramSender {
	return &TelegramSender{bot: bot, chatID: chatID}
}

// downloadAsInputFile downloads the URL via the shared media client and returns
// a telego InputFile suitable for upload. Uses the shared HTTP client with
// timeout and size limits. If fileName is empty, derives it from the URL.
func downloadAsInputFile(ctx context.Context, mediaURL, fileName string) (telego.InputFile, bool) {
	data, err := shared.DownloadFromURL(ctx, mediaURL)
	if err != nil {
		slog.Warn("Media download failed for upload fallback", "error", err, "url", mediaURL)
		return telego.InputFile{}, false
	}
	if fileName == "" {
		fileName = shared.FilenameFromURL(mediaURL)
	}
	return tu.FileFromReader(bytes.NewReader(data), fileName), true
}

func (s *TelegramSender) SendText(ctx context.Context, text string) error {
	_, err := s.bot.SendMessage(ctx, tu.Message(tu.ID(s.chatID), text))
	return err
}

func (s *TelegramSender) SendImage(ctx context.Context, url string, caption string) error {
	params := tu.Photo(tu.ID(s.chatID), tu.FileFromURL(url))
	if caption != "" {
		params.Caption = caption
	}
	_, err := s.bot.SendPhoto(ctx, params)
	if err == nil {
		return nil
	}

	file, ok := downloadAsInputFile(ctx, url, "")
	if !ok {
		return err
	}
	params = tu.Photo(tu.ID(s.chatID), file)
	if caption != "" {
		params.Caption = caption
	}
	if _, uploadErr := s.bot.SendPhoto(ctx, params); uploadErr != nil {
		slog.Warn("Upload fallback also failed for image", "error", uploadErr, "url", url)
		return err
	}
	return nil
}

func (s *TelegramSender) SendVideo(ctx context.Context, url string, caption string) error {
	params := tu.Video(tu.ID(s.chatID), tu.FileFromURL(url))
	if caption != "" {
		params.Caption = caption
	}
	_, err := s.bot.SendVideo(ctx, params)
	if err == nil {
		return nil
	}

	file, ok := downloadAsInputFile(ctx, url, "")
	if !ok {
		return err
	}
	params = tu.Video(tu.ID(s.chatID), file)
	if caption != "" {
		params.Caption = caption
	}
	if _, uploadErr := s.bot.SendVideo(ctx, params); uploadErr != nil {
		slog.Warn("Upload fallback also failed for video", "error", uploadErr, "url", url)
		return err
	}
	return nil
}

func (s *TelegramSender) SendFile(ctx context.Context, url string, name string, caption string) error {
	params := tu.Document(tu.ID(s.chatID), tu.FileFromURL(url))
	if caption != "" {
		params.Caption = caption
	}
	_, err := s.bot.SendDocument(ctx, params)
	if err == nil {
		return nil
	}

	file, ok := downloadAsInputFile(ctx, url, name)
	if !ok {
		return err
	}
	params = tu.Document(tu.ID(s.chatID), file)
	if caption != "" {
		params.Caption = caption
	}
	if _, uploadErr := s.bot.SendDocument(ctx, params); uploadErr != nil {
		slog.Warn("Upload fallback also failed for file", "error", uploadErr, "url", url)
		return err
	}
	return nil
}

func (s *TelegramSender) SendCard(ctx context.Context, title, description, imageURL, linkURL, label string) error {
	// Build optional inline keyboard with a URL button
	var keyboard *telego.InlineKeyboardMarkup
	if linkURL != "" {
		btnLabel := label
		if btnLabel == "" {
			btnLabel = "View"
		}
		btn := tu.InlineKeyboardButton(btnLabel)
		btn.URL = linkURL
		keyboard = tu.InlineKeyboard(tu.InlineKeyboardRow(btn))
	}

	if imageURL != "" {
		caption := fmt.Sprintf("*%s*\n%s", title, description)

		// Try sending as photo with URL
		params := tu.Photo(tu.ID(s.chatID), tu.FileFromURL(imageURL))
		params.Caption = caption
		params.ParseMode = telego.ModeMarkdown
		if keyboard != nil {
			params.ReplyMarkup = keyboard
		}
		_, err := s.bot.SendPhoto(ctx, params)
		if err == nil {
			return nil
		}

		// Fallback: download and upload
		if file, ok := downloadAsInputFile(ctx, imageURL, ""); ok {
			params = tu.Photo(tu.ID(s.chatID), file)
			params.Caption = caption
			params.ParseMode = telego.ModeMarkdown
			if keyboard != nil {
				params.ReplyMarkup = keyboard
			}
			if _, uploadErr := s.bot.SendPhoto(ctx, params); uploadErr == nil {
				return nil
			}
		}
		// Image failed — fall through to text-only message
	}

	// No image or image failed: send as text message
	text := fmt.Sprintf("*%s*\n%s", title, description)
	params := tu.Message(tu.ID(s.chatID), text)
	params.ParseMode = telego.ModeMarkdown
	if keyboard != nil {
		params.ReplyMarkup = keyboard
	}
	_, err := s.bot.SendMessage(ctx, params)
	return err
}

// maxCallbackData is the maximum size of callback_data in bytes for Telegram inline buttons.
const maxCallbackData = 64

func (s *TelegramSender) SendChoice(ctx context.Context, question string, options []string) error {
	rows := make([][]telego.InlineKeyboardButton, 0, len(options))
	for _, opt := range options {
		btn := tu.InlineKeyboardButton(opt)
		data := opt
		if len(data) > maxCallbackData {
			data = data[:maxCallbackData]
		}
		btn.CallbackData = data
		rows = append(rows, tu.InlineKeyboardRow(btn))
	}

	params := tu.Message(tu.ID(s.chatID), question)
	params.ReplyMarkup = tu.InlineKeyboard(rows...)
	_, err := s.bot.SendMessage(ctx, params)
	return err
}
