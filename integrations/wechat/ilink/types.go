package ilink

// Message type constants
const (
	MessageTypeNone = 0
	MessageTypeUser = 1
	MessageTypeBot  = 2
)

// Message state constants
const (
	MessageStateNew        = 0
	MessageStateGenerating = 1
	MessageStateFinish     = 2
)

// Item type constants
const (
	ItemTypeNone  = 0
	ItemTypeText  = 1
	ItemTypeImage = 2
	ItemTypeVoice = 3
	ItemTypeFile  = 4
	ItemTypeVideo = 5
)

// Credentials holds the authentication data obtained from QR code login.
type Credentials struct {
	BotToken   string `json:"bot_token"`
	BaseURL    string `json:"baseurl"`
	ILinkBotID string `json:"ilink_bot_id"`
	UserID     string `json:"user_id"`
}

// BaseInfo is included in various requests.
type BaseInfo struct {
	ChannelVersion string `json:"channel_version,omitempty"`
}

// --- GetUpdates ---

// GetUpdatesRequest is the request body for the getupdates endpoint.
type GetUpdatesRequest struct {
	GetUpdatesBuf      string   `json:"get_updates_buf"`
	LongpollingTimeout int      `json:"longpolling_timeout,omitempty"`
	BaseInfo           BaseInfo `json:"base_info"`
}

// GetUpdatesResponse is the response from the getupdates endpoint.
type GetUpdatesResponse struct {
	Ret               int             `json:"ret"`
	ErrMsg            string          `json:"errmsg,omitempty"`
	Msgs              []WeixinMessage `json:"msgs"`
	GetUpdatesBuf     string          `json:"get_updates_buf"`
	LongpollingTimeout int            `json:"longpolling_timeout_ms"`
}

// WeixinMessage represents an incoming WeChat message.
type WeixinMessage struct {
	FromUserID   string    `json:"from_user_id"`
	ToUserID     string    `json:"to_user_id"`
	MessageType  int       `json:"message_type"`
	MessageState int       `json:"message_state"`
	ContextToken string    `json:"context_token"`
	ItemList     []ItemObj `json:"item_list"`
}

// ItemObj represents a message item (text, image, etc.).
type ItemObj struct {
	Type      int        `json:"type"`
	TextItem  *TextItem  `json:"text_item,omitempty"`
	ImageItem *ImageItem `json:"image_item,omitempty"`
	VideoItem *VideoItem `json:"video_item,omitempty"`
	FileItem  *FileItem  `json:"file_item,omitempty"`
}

// TextItem holds text content for a message item.
type TextItem struct {
	Text string `json:"text"`
}

// --- SendMessage ---

// SendMessageRequest is the request body for the sendmessage endpoint.
type SendMessageRequest struct {
	Msg      SendMsg  `json:"msg"`
	BaseInfo BaseInfo `json:"base_info"`
}

// SendMsg is the outgoing message structure.
type SendMsg struct {
	FromUserID   string    `json:"from_user_id"`
	ToUserID     string    `json:"to_user_id"`
	ClientID     string    `json:"client_id"`
	MessageType  int       `json:"message_type"`
	MessageState int       `json:"message_state"`
	ContextToken string    `json:"context_token"`
	ItemList     []ItemObj `json:"item_list"`
}

// SendMessageResponse is the response from the sendmessage endpoint.
type SendMessageResponse struct {
	Ret    int    `json:"ret"`
	ErrMsg string `json:"errmsg,omitempty"`
}

// --- SendTyping ---

// SendTypingRequest is the request body for the sendtyping endpoint.
type SendTypingRequest struct {
	ILinkUserID  string   `json:"ilink_user_id"`
	TypingTicket string   `json:"typing_ticket"`
	Status       int      `json:"status"`
	BaseInfo     BaseInfo `json:"base_info"`
}

// SendTypingResponse is the response from the sendtyping endpoint.
type SendTypingResponse struct {
	Ret    int    `json:"ret"`
	ErrMsg string `json:"errmsg,omitempty"`
}

// --- GetConfig ---

// GetConfigRequest is the request body for the getconfig endpoint.
type GetConfigRequest struct {
	ILinkUserID  string   `json:"ilink_user_id"`
	ContextToken string   `json:"context_token"`
	BaseInfo     BaseInfo `json:"base_info"`
}

// GetConfigResponse is the response from the getconfig endpoint.
type GetConfigResponse struct {
	Ret          int    `json:"ret"`
	ErrMsg       string `json:"errmsg,omitempty"`
	TypingTicket string `json:"typing_ticket"`
}

// --- Media Item Types ---

// CDNMedia references an encrypted file on WeChat's CDN.
type CDNMedia struct {
	EncryptQueryParam string `json:"encrypt_query_param"`
	AESKey            string `json:"aes_key"`
	EncryptType       int    `json:"encrypt_type"`
}

// ImageItem holds image content for a message item.
type ImageItem struct {
	Media       CDNMedia `json:"media"`
	ThumbMedia  CDNMedia `json:"thumb_media"`
	MidSize     int      `json:"mid_size"`
	ThumbSize   int      `json:"thumb_size"`
	ThumbHeight int      `json:"thumb_height"`
	ThumbWidth  int      `json:"thumb_width"`
}

// VideoItem holds video content for a message item.
type VideoItem struct {
	Media CDNMedia `json:"media"`
}

// FileItem holds file content for a message item.
type FileItem struct {
	Media    CDNMedia `json:"media"`
	FileName string   `json:"file_name"`
	FileSize int      `json:"file_size"`
}

// --- GetUploadURL ---

// UploadParam contains the parameters for uploading a file to CDN.
type UploadParam struct {
	UploadURL string `json:"upload_url"`
	FileID    string `json:"file_id"`
	AESKey    string `json:"aes_key"`
}

// GetUploadURLRequest is the request body for the getuploadurl endpoint.
type GetUploadURLRequest struct {
	MediaType int      `json:"media_type"`
	FileSize  int      `json:"file_size"`
	FileName  string   `json:"file_name"`
	BaseInfo  BaseInfo `json:"base_info"`
}

// GetUploadURLResponse is the response from the getuploadurl endpoint.
type GetUploadURLResponse struct {
	Ret              int          `json:"ret"`
	ErrMsg           string       `json:"errmsg,omitempty"`
	UploadParam      UploadParam  `json:"upload_param"`
	ThumbUploadParam *UploadParam `json:"thumb_upload_param,omitempty"`
}
