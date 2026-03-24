// Package types provides shared data structures for IntentKit Go integrations.
// These types mirror the Python Pydantic models in intentkit/models/chat.py.
package types

// ChatMessage mirrors intentkit.models.chat.ChatMessage.
// Only fields relevant to integration message handling are included.
type ChatMessage struct {
	ID         string `json:"id"`
	AgentID    string `json:"agent_id"`
	ChatID     string `json:"chat_id"`
	UserID     string `json:"user_id,omitempty"`
	AuthorID   string `json:"author_id"`
	AuthorType string `json:"author_type"`
	Message    string `json:"message"`

	// Optional fields
	Model      *string              `json:"model,omitempty"`
	ThreadType *string              `json:"thread_type,omitempty"`
	ReplyTo    *string              `json:"reply_to,omitempty"`
	Thinking   *string              `json:"thinking,omitempty"`
	ErrorType  *string              `json:"error_type,omitempty"`
	CreatedAt  string               `json:"created_at,omitempty"`
	SkillCalls []ChatMessageSkill   `json:"skill_calls,omitempty"`
	Attachments []ChatMessageAttach `json:"attachments,omitempty"`
}

// ChatMessageSkill mirrors intentkit.models.chat.ChatMessageSkillCall.
type ChatMessageSkill struct {
	ID           string                 `json:"id,omitempty"`
	Name         string                 `json:"name"`
	Parameters   map[string]interface{} `json:"parameters"`
	Success      bool                   `json:"success"`
	Response     string                 `json:"response,omitempty"`
	ErrorMessage string                 `json:"error_message,omitempty"`
}

// ChatMessageAttach mirrors intentkit.models.chat.ChatMessageAttachment.
type ChatMessageAttach struct {
	Type     string                 `json:"type"`
	LeadText *string                `json:"lead_text,omitempty"`
	URL      *string                `json:"url,omitempty"`
	JSON     map[string]interface{} `json:"json,omitempty"`
}

// IsAgentResponse returns true if this message is a response that should be
// sent back to the user (agent reply or system message with content).
func (m *ChatMessage) IsAgentResponse() bool {
	return m.Message != "" && (m.AuthorType == "agent" || m.AuthorType == "system")
}
