package ilink

import (
	"bytes"
	"context"
	"crypto/aes"
	"crypto/md5"
	crand "crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math/rand/v2"
	"net/http"
	"net/url"
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
		slog.Error("iLink API HTTP error", "path", path, "status", resp.StatusCode, "body", string(respBody))
		return fmt.Errorf("ilink api returned status %d: %s", resp.StatusCode, string(respBody))
	}

	// Log response for non-getupdates calls (getupdates is too noisy).
	// For getupdates, only log when there's a non-zero ret (potential auth failure).
	if path != "/ilink/bot/getupdates" {
		slog.Info("iLink API response", "path", path, "body", string(respBody))
	} else {
		// Peek at ret field to detect auth/session errors
		var peek struct {
			Ret    int    `json:"ret"`
			ErrMsg string `json:"errmsg"`
		}
		if json.Unmarshal(respBody, &peek) == nil && peek.Ret != 0 {
			slog.Warn("getupdates non-zero ret", "ret", peek.Ret, "errmsg", peek.ErrMsg, "body", string(respBody))
		}
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
		GetUpdatesBuf:      c.updatesBuf,
		LongpollingTimeout: 30,
		BaseInfo:           BaseInfo{ChannelVersion: channelVersion},
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

const cdnBaseURL = "https://novac2c.cdn.weixin.qq.com/c2c/upload"

// UploadMedia handles the full media upload flow for WeChat CDN:
// 1. Generates client-side AES key and filekey
// 2. Requests upload permission via getuploadurl
// 3. Encrypts data with AES-128-ECB
// 4. Uploads encrypted data to CDN
// Returns a CDNMedia reference for use in sendmessage, plus ciphertext size.
func (c *Client) UploadMedia(ctx context.Context, data []byte, mediaType int, toUserID string) (CDNMedia, int, error) {
	// Generate random 16-byte AES key and filekey
	aesKey := make([]byte, 16)
	if _, err := crand.Read(aesKey); err != nil {
		return CDNMedia{}, 0, fmt.Errorf("generate aes key: %w", err)
	}
	filekey := make([]byte, 16)
	if _, err := crand.Read(filekey); err != nil {
		return CDNMedia{}, 0, fmt.Errorf("generate filekey: %w", err)
	}

	aesKeyHex := hex.EncodeToString(aesKey)
	filekeyHex := hex.EncodeToString(filekey)

	rawSize := len(data)
	md5Sum := md5.Sum(data)
	rawMD5Hex := hex.EncodeToString(md5Sum[:])
	ciphertextSize := (rawSize/16 + 1) * 16 // PKCS7 always adds at least 1 byte

	// Step 1: Get upload param from API
	uploadReqBody := GetUploadURLRequest{
		FileKey:     filekeyHex,
		MediaType:   mediaType,
		ToUserID:    toUserID,
		RawSize:     rawSize,
		RawFileMD5:  rawMD5Hex,
		FileSize:    ciphertextSize,
		NoNeedThumb: true,
		AESKey:      aesKeyHex,
		BaseInfo:    BaseInfo{ChannelVersion: channelVersion},
	}

	var uploadResp GetUploadURLResponse
	if err := c.doPost(ctx, "/ilink/bot/getuploadurl", uploadReqBody, &uploadResp); err != nil {
		return CDNMedia{}, 0, fmt.Errorf("getuploadurl: %w", err)
	}
	if uploadResp.Ret != 0 {
		return CDNMedia{}, 0, fmt.Errorf("getuploadurl returned ret=%d errmsg=%s", uploadResp.Ret, uploadResp.ErrMsg)
	}
	if uploadResp.UploadParam == "" {
		return CDNMedia{}, 0, fmt.Errorf("getuploadurl returned empty upload_param")
	}

	// Step 2: Encrypt data with AES-128-ECB + PKCS7
	encrypted, err := aesECBEncrypt(aesKey, data)
	if err != nil {
		return CDNMedia{}, 0, fmt.Errorf("encrypt data: %w", err)
	}

	// Step 3: Upload encrypted data to CDN
	query := url.Values{}
	query.Set("encrypted_query_param", uploadResp.UploadParam)
	query.Set("filekey", filekeyHex)
	cdnURL := cdnBaseURL + "?" + query.Encode()

	req, err := http.NewRequestWithContext(ctx, "POST", cdnURL, bytes.NewReader(encrypted))
	if err != nil {
		return CDNMedia{}, 0, fmt.Errorf("create cdn upload request: %w", err)
	}
	req.Header.Set("Content-Type", "application/octet-stream")
	// CDN upload does NOT use bot auth headers

	cdnResp, err := c.cdnClient.Do(req)
	if err != nil {
		return CDNMedia{}, 0, fmt.Errorf("cdn upload: %w", err)
	}
	defer cdnResp.Body.Close()

	cdnBody, _ := io.ReadAll(cdnResp.Body)
	if cdnResp.StatusCode != http.StatusOK {
		slog.Error("CDN upload failed", "status", cdnResp.StatusCode, "body", string(cdnBody))
		return CDNMedia{}, 0, fmt.Errorf("cdn upload returned status %d", cdnResp.StatusCode)
	}

	// Read download param from response header
	downloadParam := cdnResp.Header.Get("X-Encrypted-Param")
	if downloadParam == "" {
		// Fallback: try response body
		var bodyResp struct {
			EncryptedParam string `json:"encrypt_query_param"`
		}
		if json.Unmarshal(cdnBody, &bodyResp) == nil && bodyResp.EncryptedParam != "" {
			downloadParam = bodyResp.EncryptedParam
		}
	}
	if downloadParam == "" {
		slog.Error("CDN upload: no download param", "headers", cdnResp.Header, "body", string(cdnBody))
		return CDNMedia{}, 0, fmt.Errorf("cdn upload returned no download param")
	}

	slog.Info("Media uploaded to WeChat CDN", "mediaType", mediaType, "rawSize", rawSize)

	// Build CDNMedia: aes_key for sendmessage = base64(hex_string)
	aesKeyForMsg := base64.StdEncoding.EncodeToString([]byte(aesKeyHex))

	media := CDNMedia{
		EncryptQueryParam: downloadParam,
		AESKey:            aesKeyForMsg,
		EncryptType:       1,
	}

	return media, ciphertextSize, nil
}

// SendImage sends an image message to a WeChat user.
func (c *Client) SendImage(ctx context.Context, toUserID, contextToken string, media CDNMedia, ciphertextSize int) error {
	reqBody := SendMessageRequest{
		Msg: SendMsg{
			FromUserID:   "",
			ToUserID:     toUserID,
			ClientID:     xid.New().String(),
			MessageType:  MessageTypeBot,
			MessageState: MessageStateFinish,
			ContextToken: contextToken,
			ItemList: []ItemObj{
				{
					Type: ItemTypeImage,
					ImageItem: &ImageItem{
						Media:   media,
						MidSize: ciphertextSize,
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
			FromUserID:   "",
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
			FromUserID:   "",
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
