package larkclient

import (
	"encoding/json"
	"strings"
	"testing"
)

// parsedCard is a loose view of a built card used to assert structure without
// coupling the tests to the exact builder types.
type parsedCard struct {
	Config map[string]any `json:"config"`
	Header *struct {
		Template string `json:"template"`
		Title    struct {
			Tag     string `json:"tag"`
			Content string `json:"content"`
		} `json:"title"`
	} `json:"header"`
	Elements []map[string]any `json:"elements"`
}

func mustParse(t *testing.T, cardJSON string) parsedCard {
	t.Helper()
	var c parsedCard
	if err := json.Unmarshal([]byte(cardJSON), &c); err != nil {
		t.Fatalf("card is not valid JSON: %v\n%s", err, cardJSON)
	}
	return c
}

func TestTextCardRendersMarkdown(t *testing.T) {
	out, err := TextCard("**hello** world")
	if err != nil {
		t.Fatalf("TextCard error: %v", err)
	}
	c := mustParse(t, out)
	if len(c.Elements) != 1 {
		t.Fatalf("expected 1 element, got %d", len(c.Elements))
	}
	if c.Elements[0]["tag"] != "markdown" {
		t.Errorf("expected markdown element, got %v", c.Elements[0]["tag"])
	}
	if c.Elements[0]["content"] != "**hello** world" {
		t.Errorf("markdown content mismatch: %v", c.Elements[0]["content"])
	}
}

func TestRichCardFull(t *testing.T) {
	out, err := RichCard("Title", "Body", "img_123", "https://example.com", "Open")
	if err != nil {
		t.Fatalf("RichCard error: %v", err)
	}
	c := mustParse(t, out)
	if c.Header == nil || c.Header.Title.Content != "Title" {
		t.Fatalf("expected header title 'Title', got %+v", c.Header)
	}
	var hasImg, hasMarkdown, hasButtonURL bool
	for _, el := range c.Elements {
		switch el["tag"] {
		case "img":
			if el["img_key"] == "img_123" {
				hasImg = true
			}
		case "markdown":
			if el["content"] == "Body" {
				hasMarkdown = true
			}
		case "action":
			actions, _ := el["actions"].([]any)
			for _, a := range actions {
				btn, _ := a.(map[string]any)
				if btn["url"] == "https://example.com" {
					hasButtonURL = true
				}
			}
		}
	}
	if !hasImg || !hasMarkdown || !hasButtonURL {
		t.Errorf("missing element(s): img=%v markdown=%v buttonURL=%v", hasImg, hasMarkdown, hasButtonURL)
	}
}

func TestRichCardEmptyStillValid(t *testing.T) {
	// A fully empty attachment must still produce a sendable (non-empty) card.
	out, err := RichCard("", "", "", "", "")
	if err != nil {
		t.Fatalf("RichCard error: %v", err)
	}
	c := mustParse(t, out)
	if c.Header != nil {
		t.Errorf("expected no header for empty card")
	}
	if len(c.Elements) == 0 {
		t.Errorf("empty card must still carry at least one element")
	}
}

func TestChoiceCardButtonsCarryOption(t *testing.T) {
	options := []string{"Yes", "No", "Maybe: not sure"}
	out, err := ChoiceCard("Pick one", options)
	if err != nil {
		t.Fatalf("ChoiceCard error: %v", err)
	}
	c := mustParse(t, out)

	var buttonValues []string
	for _, el := range c.Elements {
		if el["tag"] != "action" {
			continue
		}
		actions, _ := el["actions"].([]any)
		for _, a := range actions {
			btn, _ := a.(map[string]any)
			value, _ := btn["value"].(map[string]any)
			opt, _ := value[ChoiceValueKey].(string)
			buttonValues = append(buttonValues, opt)
		}
	}

	if len(buttonValues) != len(options) {
		t.Fatalf("expected %d buttons, got %d", len(options), len(buttonValues))
	}
	for i, opt := range options {
		if buttonValues[i] != opt {
			t.Errorf("button %d carries %q, want %q (callback round-trip would break)", i, buttonValues[i], opt)
		}
	}
}

func TestResolveBaseURL(t *testing.T) {
	cases := map[string]string{
		"feishu": "open.feishu.cn",
		"lark":   "larksuite.com",
		"":       "open.feishu.cn", // default
		"bogus":  "open.feishu.cn", // unknown falls back to feishu
	}
	for domain, want := range cases {
		got := ResolveBaseURL(domain)
		if !strings.Contains(got, want) {
			t.Errorf("ResolveBaseURL(%q) = %q, want host containing %q", domain, got, want)
		}
	}
}
