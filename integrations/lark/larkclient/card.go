package larkclient

import "encoding/json"

// This file builds Feishu/Lark interactive message cards (msg_type=interactive)
// as JSON strings. Cards are the main UX lever the Lark integration leans on:
// agent replies render as markdown (bold/lists/code/links display natively,
// unlike plain-text messages), and choices render as real buttons that post
// back through the card-action callback instead of a numbered text list.
//
// The builders are pure (string in, JSON string out) so they can be unit
// tested without the SDK or a live tenant. Orchestration that needs the API
// (uploading a card's cover image to obtain an img_key) lives in client.go.

// ChoiceValueKey is the key under which a choice button carries the selected
// option in its `value` map. The card-action callback echoes this back, and
// the handler forwards it to the lead agent as the user's reply.
const ChoiceValueKey = "option"

// Header colour templates.
const (
	templateBlue      = "blue"
	templateTurquoise = "turquoise"
)

type cardConfig struct {
	WideScreenMode bool `json:"wide_screen_mode"`
	UpdateMulti    bool `json:"update_multi"`
}

type plainText struct {
	Tag     string `json:"tag"`
	Content string `json:"content"`
}

func newPlainText(content string) plainText {
	return plainText{Tag: "plain_text", Content: content}
}

type cardHeader struct {
	Template string    `json:"template,omitempty"`
	Title    plainText `json:"title"`
}

type markdownElement struct {
	Tag     string `json:"tag"`
	Content string `json:"content"`
}

type imgElement struct {
	Tag    string    `json:"tag"`
	ImgKey string    `json:"img_key"`
	Alt    plainText `json:"alt"`
}

type buttonElement struct {
	Tag   string         `json:"tag"`
	Text  plainText      `json:"text"`
	Type  string         `json:"type"`
	Value map[string]any `json:"value,omitempty"`
	URL   string         `json:"url,omitempty"`
}

type actionElement struct {
	Tag     string          `json:"tag"`
	Actions []buttonElement `json:"actions"`
}

type card struct {
	Config   cardConfig  `json:"config"`
	Header   *cardHeader `json:"header,omitempty"`
	Elements []any       `json:"elements"`
}

func newCard() *card {
	return &card{
		// update_multi lets every member of a group see button-driven updates;
		// harmless for p2p chats.
		Config:   cardConfig{WideScreenMode: true, UpdateMulti: true},
		Elements: []any{},
	}
}

func (c *card) marshal() (string, error) {
	buf, err := json.Marshal(c)
	if err != nil {
		return "", err
	}
	return string(buf), nil
}

func markdown(content string) markdownElement {
	return markdownElement{Tag: "markdown", Content: content}
}

// TextCard renders a single block of markdown as a card. Used for agent text
// and tool/system status lines so LLM markdown renders natively.
func TextCard(content string) (string, error) {
	c := newCard()
	c.Elements = append(c.Elements, markdown(content))
	return c.marshal()
}

// RichCard renders a card attachment: an optional coloured header (title), a
// markdown body, an optional cover image (already uploaded to an img_key), and
// an optional link button. Any empty field is omitted.
func RichCard(title, description, imgKey, linkURL, linkLabel string) (string, error) {
	c := newCard()
	if title != "" {
		c.Header = &cardHeader{Template: templateBlue, Title: newPlainText(title)}
	}
	if imgKey != "" {
		c.Elements = append(c.Elements, imgElement{
			Tag:    "img",
			ImgKey: imgKey,
			Alt:    newPlainText(title),
		})
	}
	if description != "" {
		c.Elements = append(c.Elements, markdown(description))
	}
	if linkURL != "" {
		label := linkLabel
		if label == "" {
			label = "View"
		}
		c.Elements = append(c.Elements, actionElement{
			Tag: "action",
			Actions: []buttonElement{{
				Tag:  "button",
				Text: newPlainText(label),
				Type: "primary",
				URL:  linkURL,
			}},
		})
	}
	// A card with no header and no elements would be rejected; guarantee at
	// least one element so the send never fails on an empty attachment.
	if c.Header == nil && len(c.Elements) == 0 {
		c.Elements = append(c.Elements, markdown(" "))
	}
	return c.marshal()
}

// ChoiceCard renders a question followed by one button per option. Each button
// carries its option text in `value` under ChoiceValueKey; clicking it fires a
// card-action callback the handler forwards to the lead agent. Users who type
// the option text instead get the same result, so the buttons degrade
// gracefully on clients that don't support callbacks.
func ChoiceCard(question string, options []string) (string, error) {
	c := newCard()
	c.Header = &cardHeader{Template: templateTurquoise, Title: newPlainText("Please choose")}
	if question != "" {
		c.Elements = append(c.Elements, markdown(question))
	}
	actions := make([]buttonElement, 0, len(options))
	for _, opt := range options {
		actions = append(actions, buttonElement{
			Tag:   "button",
			Text:  newPlainText(opt),
			Type:  "primary",
			Value: map[string]any{ChoiceValueKey: opt},
		})
	}
	if len(actions) > 0 {
		c.Elements = append(c.Elements, actionElement{Tag: "action", Actions: actions})
	}
	return c.marshal()
}
