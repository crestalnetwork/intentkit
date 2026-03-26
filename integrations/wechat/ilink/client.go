package ilink

import (
	"bytes"
	"context"
	"crypto/aes"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math/rand/v2"
	"net/http"
	"strconv"
	"time"

	"github.com/rs/xid"
)

const channelVersion = "1.0.2"

// Client communicates with the WeChat iLink Bot API.
type Client struct {
	baseURL    string
	botToken   string
	botID      string
	httpClient *http.Client // for API calls (40s timeout)
	cdnClient  *http.Client // for CDN uploads (2min timeout)
	updatesBuf string       // cursor for long-polling
}

// NewClient creates an authenticated iLink API client.
func NewClient(baseURL, botToken, botID string) *Client {
	return &Client{
		baseURL:  baseURL,
		botToken: botToken,
		botID:    botID,
		httpClient: &http.Client{
			Timeout: 40 * time.Second,
		},
		cdnClient: &http.Client{
			Timeout: 2 * time.Minute,
		},
	}
}

// BotID returns the bot's iLink user ID.
func (c *Client) BotID() string {
	return c.botID
}

// generateWechatUIN generates a random X-WECHAT-UIN header value.
func generateWechatUIN() string {
	n := rand.Uint32()
	return base64.StdEncoding.EncodeToString([]byte(strconv.FormatUint(uint64(n), 10)))
}

// setHeaders applies the required auth headers to an HTTP request.
func (c *Client) setHeaders(req *http.Request) {
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("AuthorizationType", "ilink_bot_token")
	req.Header.Set("X-WECHAT-UIN", generateWechatUIN())
	req.Header.Set("Authorization", "Bearer "+c.botToken)
}

// doPost performs a POST request with JSON body and decodes the JSON response.
func (c *Client) doPost(ctx context.Context, path string, body interface{}, result interface{}) error {
	bodyBytes, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+path, bytes.NewReader(bodyBytes))
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	c.setHeaders(req)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("http request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("read response body: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		slog.Error("iLink API error", "path", path, "status", resp.StatusCode, "body", string(respBody))
		return fmt.Errorf("ilink api returned status %d", resp.StatusCode)
	}

	// Log response for non-getupdates calls (getupdates is too noisy)
	if path != "/ilink/bot/getupdates" {
		slog.Info("iLink API response", "path", path, "body", string(respBody))
	}

	if result != nil {
		if err := json.Unmarshal(respBody, result); err != nil {
			return fmt.Errorf("decode response: %w", err)
		}
	}
	return nil
}

// GetUpdates performs long-polling for new messages.
func (c *Client) GetUpdates(ctx context.Context) ([]WeixinMessage, error) {
	reqBody := GetUpdatesRequest{
		GetUpdatesBuf: c.updatesBuf,
		BaseInfo:      BaseInfo{ChannelVersion: channelVersion},
	}

	var resp GetUpdatesResponse
	if err := c.doPost(ctx, "/ilink/bot/getupdates", reqBody, &resp); err != nil {
		return nil, err
	}

	if resp.Ret != 0 {
		return nil, fmt.Errorf("getupdates returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	c.updatesBuf = resp.GetUpdatesBuf
	return resp.Msgs, nil
}

// SendMessage sends a text reply to a WeChat user.
func (c *Client) SendMessage(ctx context.Context, toUserID, contextToken, text string) error {
	reqBody := SendMessageRequest{
		Msg: SendMsg{
			FromUserID:   c.botID,
			ToUserID:     toUserID,
			ClientID:     xid.New().String(),
			MessageType:  MessageTypeBot,
			MessageState: MessageStateFinish,
			ContextToken: contextToken,
			ItemList: []ItemObj{
				{
					Type:     ItemTypeText,
					TextItem: &TextItem{Text: text},
				},
			},
		},
		BaseInfo: BaseInfo{},
	}

	var resp SendMessageResponse
	if err := c.doPost(ctx, "/ilink/bot/sendmessage", reqBody, &resp); err != nil {
		return err
	}

	if resp.Ret != 0 {
		return fmt.Errorf("sendmessage returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return nil
}

// SendTyping sends a typing indicator to a WeChat user.
func (c *Client) SendTyping(ctx context.Context, userID, typingTicket string) error {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	reqBody := SendTypingRequest{
		ILinkUserID:  userID,
		TypingTicket: typingTicket,
		Status:       1,
		BaseInfo:     BaseInfo{},
	}

	var resp SendTypingResponse
	if err := c.doPost(ctx, "/ilink/bot/sendtyping", reqBody, &resp); err != nil {
		return err
	}

	if resp.Ret != 0 {
		return fmt.Errorf("sendtyping returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return nil
}

// GetConfig retrieves bot configuration including the typing_ticket.
func (c *Client) GetConfig(ctx context.Context, userID, contextToken string) (*GetConfigResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	reqBody := GetConfigRequest{
		ILinkUserID:  userID,
		ContextToken: contextToken,
		BaseInfo:     BaseInfo{},
	}

	var resp GetConfigResponse
	if err := c.doPost(ctx, "/ilink/bot/getconfig", reqBody, &resp); err != nil {
		return nil, err
	}

	if resp.Ret != 0 {
		return nil, fmt.Errorf("getconfig returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return &resp, nil
}

// aesECBEncrypt encrypts plaintext using AES-128-ECB with PKCS7 padding.
func aesECBEncrypt(key, plaintext []byte) ([]byte, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("create cipher: %w", err)
	}

	blockSize := block.BlockSize()
	// PKCS7 padding
	padding := blockSize - len(plaintext)%blockSize
	padText := make([]byte, len(plaintext)+padding)
	copy(padText, plaintext)
	for i := len(plaintext); i < len(padText); i++ {
		padText[i] = byte(padding)
	}

	// ECB mode: encrypt each block independently
	ciphertext := make([]byte, len(padText))
	for i := 0; i < len(padText); i += blockSize {
		block.Encrypt(ciphertext[i:i+blockSize], padText[i:i+blockSize])
	}

	return ciphertext, nil
}

// GetUploadURL requests an upload URL for a media file.
func (c *Client) GetUploadURL(ctx context.Context, mediaType int, fileSize int, fileName string) (*GetUploadURLResponse, error) {
	reqBody := GetUploadURLRequest{
		MediaType: mediaType,
		FileSize:  fileSize,
		FileName:  fileName,
		BaseInfo:  BaseInfo{ChannelVersion: channelVersion},
	}

	var resp GetUploadURLResponse
	if err := c.doPost(ctx, "/ilink/bot/getuploadurl", reqBody, &resp); err != nil {
		return nil, err
	}

	if resp.Ret != 0 {
		return nil, fmt.Errorf("getuploadurl returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return &resp, nil
}

// UploadToCDN encrypts the data with AES-128-ECB and uploads it to WeChat's CDN.
// Returns the encrypt_query_param for constructing CDNMedia references.
func (c *Client) UploadToCDN(ctx context.Context, uploadURL string, fileID string, aesKeyBase64 string, data []byte) (string, error) {
	// Decode AES key from base64
	keyBytes, err := base64.StdEncoding.DecodeString(aesKeyBase64)
	if err != nil {
		return "", fmt.Errorf("decode aes key base64: %w", err)
	}

	// If decoded bytes are 32 chars (hex-encoded 16-byte key), decode hex
	if len(keyBytes) == 32 {
		hexDecoded, err := hex.DecodeString(string(keyBytes))
		if err != nil {
			return "", fmt.Errorf("decode aes key hex: %w", err)
		}
		keyBytes = hexDecoded
	}

	if len(keyBytes) != 16 {
		return "", fmt.Errorf("unexpected aes key length: %d (expected 16)", len(keyBytes))
	}

	// Encrypt the data
	encrypted, err := aesECBEncrypt(keyBytes, data)
	if err != nil {
		return "", fmt.Errorf("encrypt data: %w", err)
	}

	// Upload encrypted data to CDN
	reqURL := uploadURL + "?file_id=" + fileID
	req, err := http.NewRequestWithContext(ctx, "POST", reqURL, bytes.NewReader(encrypted))
	if err != nil {
		return "", fmt.Errorf("create upload request: %w", err)
	}
	req.Header.Set("Content-Type", "application/octet-stream")
	c.setHeaders(req)

	resp, err := c.cdnClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("upload to cdn: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("read upload response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		slog.Error("CDN upload failed", "status", resp.StatusCode, "body", string(respBody))
		return "", fmt.Errorf("cdn upload returned status %d", resp.StatusCode)
	}

	slog.Info("CDN upload response", "status", resp.StatusCode, "body", string(respBody))

	// Try to parse encrypt_query_param from response body
	var cdnResp struct {
		EncryptQueryParam string `json:"encrypt_query_param"`
		FileID            string `json:"file_id"`
	}
	if err := json.Unmarshal(respBody, &cdnResp); err == nil && cdnResp.EncryptQueryParam != "" {
		return cdnResp.EncryptQueryParam, nil
	}

	// Fallback: use file_id as encrypt_query_param
	return fileID, nil
}

// SendImage sends an image message to a WeChat user.
func (c *Client) SendImage(ctx context.Context, toUserID, contextToken string, media CDNMedia, aesKey string, fileSize int) error {
	reqBody := SendMessageRequest{
		Msg: SendMsg{
			FromUserID:   c.botID,
			ToUserID:     toUserID,
			ClientID:     xid.New().String(),
			MessageType:  MessageTypeBot,
			MessageState: MessageStateFinish,
			ContextToken: contextToken,
			ItemList: []ItemObj{
				{
					Type: ItemTypeImage,
					ImageItem: &ImageItem{
						Media: media,
						ThumbMedia: CDNMedia{
							EncryptQueryParam: media.EncryptQueryParam,
							AESKey:            aesKey,
							EncryptType:       media.EncryptType,
						},
						MidSize:     fileSize,
						ThumbSize:   fileSize,
						ThumbHeight: 0,
						ThumbWidth:  0,
					},
				},
			},
		},
		BaseInfo: BaseInfo{},
	}

	var resp SendMessageResponse
	if err := c.doPost(ctx, "/ilink/bot/sendmessage", reqBody, &resp); err != nil {
		return err
	}

	if resp.Ret != 0 {
		return fmt.Errorf("sendmessage image returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return nil
}

// SendVideo sends a video message to a WeChat user.
func (c *Client) SendVideo(ctx context.Context, toUserID, contextToken string, media CDNMedia) error {
	reqBody := SendMessageRequest{
		Msg: SendMsg{
			FromUserID:   c.botID,
			ToUserID:     toUserID,
			ClientID:     xid.New().String(),
			MessageType:  MessageTypeBot,
			MessageState: MessageStateFinish,
			ContextToken: contextToken,
			ItemList: []ItemObj{
				{
					Type: ItemTypeVideo,
					VideoItem: &VideoItem{
						Media: media,
					},
				},
			},
		},
		BaseInfo: BaseInfo{},
	}

	var resp SendMessageResponse
	if err := c.doPost(ctx, "/ilink/bot/sendmessage", reqBody, &resp); err != nil {
		return err
	}

	if resp.Ret != 0 {
		return fmt.Errorf("sendmessage video returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return nil
}

// SendFile sends a file message to a WeChat user.
func (c *Client) SendFile(ctx context.Context, toUserID, contextToken, fileName string, media CDNMedia, fileSize int) error {
	reqBody := SendMessageRequest{
		Msg: SendMsg{
			FromUserID:   c.botID,
			ToUserID:     toUserID,
			ClientID:     xid.New().String(),
			MessageType:  MessageTypeBot,
			MessageState: MessageStateFinish,
			ContextToken: contextToken,
			ItemList: []ItemObj{
				{
					Type: ItemTypeFile,
					FileItem: &FileItem{
						Media:    media,
						FileName: fileName,
						FileSize: fileSize,
					},
				},
			},
		},
		BaseInfo: BaseInfo{},
	}

	var resp SendMessageResponse
	if err := c.doPost(ctx, "/ilink/bot/sendmessage", reqBody, &resp); err != nil {
		return err
	}

	if resp.Ret != 0 {
		return fmt.Errorf("sendmessage file returned ret=%d errmsg=%s", resp.Ret, resp.ErrMsg)
	}

	return nil
}
