package slackclient

import (
	"strings"
	"testing"

	"github.com/slack-go/slack"
)

func TestTextBlocks(t *testing.T) {
	blocks := TextBlocks("**hello** world")
	if len(blocks) != 1 {
		t.Fatalf("expected 1 block, got %d", len(blocks))
	}
	md, ok := blocks[0].(*slack.MarkdownBlock)
	if !ok {
		t.Fatalf("expected *slack.MarkdownBlock, got %T", blocks[0])
	}
	if md.Text != "**hello** world" {
		t.Errorf("markdown text = %q", md.Text)
	}
}

func TestTextBlocksChunksLongText(t *testing.T) {
	// Text longer than the per-block cap, with newlines to break on.
	long := strings.Repeat(strings.Repeat("a", 200)+"\n", 100) // ~20100 chars
	blocks := TextBlocks(long)
	if len(blocks) < 2 {
		t.Fatalf("expected long text to split into multiple blocks, got %d", len(blocks))
	}
	var total int
	for i, b := range blocks {
		md, ok := b.(*slack.MarkdownBlock)
		if !ok {
			t.Fatalf("block %d not markdown: %T", i, b)
		}
		if n := len([]rune(md.Text)); n > maxMarkdownText {
			t.Errorf("block %d exceeds cap: %d runes", i, n)
		}
		total += len([]rune(md.Text))
	}
	// No content is lost across the split.
	if total != len([]rune(long)) {
		t.Errorf("chunk rune total %d != original %d", total, len([]rune(long)))
	}
}

func TestChoiceBlocks(t *testing.T) {
	blocks := ChoiceBlocks("Pick one", []string{"Yes", "No"})
	if len(blocks) != 2 {
		t.Fatalf("expected question + actions block, got %d", len(blocks))
	}
	if md, ok := blocks[0].(*slack.MarkdownBlock); !ok || md.Text != "Pick one" {
		t.Errorf("first block should be the question markdown, got %#v", blocks[0])
	}
	action, ok := blocks[1].(*slack.ActionBlock)
	if !ok {
		t.Fatalf("expected *slack.ActionBlock, got %T", blocks[1])
	}
	if action.Elements == nil || len(action.Elements.ElementSet) != 2 {
		t.Fatalf("expected 2 buttons, got %#v", action.Elements)
	}
	for i, want := range []string{"Yes", "No"} {
		btn, ok := action.Elements.ElementSet[i].(*slack.ButtonBlockElement)
		if !ok {
			t.Fatalf("element %d not a button: %T", i, action.Elements.ElementSet[i])
		}
		if btn.Value != want {
			t.Errorf("button %d value = %q, want %q", i, btn.Value, want)
		}
		if btn.Text == nil || btn.Text.Text != want {
			t.Errorf("button %d label = %#v, want %q", i, btn.Text, want)
		}
		if !strings.HasPrefix(btn.ActionID, ChoiceActionPrefix) {
			t.Errorf("button %d action_id = %q, missing prefix %q", i, btn.ActionID, ChoiceActionPrefix)
		}
	}
	// Action IDs must be unique within a message.
	a := action.Elements.ElementSet[0].(*slack.ButtonBlockElement).ActionID
	b := action.Elements.ElementSet[1].(*slack.ButtonBlockElement).ActionID
	if a == b {
		t.Errorf("button action_ids must be unique, both = %q", a)
	}
}

func TestChoiceBlocksTruncatesLongValues(t *testing.T) {
	long := strings.Repeat("x", maxButtonValue+500)
	blocks := ChoiceBlocks("", []string{long})
	action := blocks[len(blocks)-1].(*slack.ActionBlock)
	btn := action.Elements.ElementSet[0].(*slack.ButtonBlockElement)
	if n := len([]rune(btn.Value)); n > maxButtonValue {
		t.Errorf("button value not truncated: %d runes", n)
	}
	if n := len([]rune(btn.Text.Text)); n > maxButtonLabel {
		t.Errorf("button label not truncated: %d runes", n)
	}
}

func TestCardBlocksFull(t *testing.T) {
	blocks := CardBlocks("Title", "A *description*", "https://cdn.example.com/x.png", "https://example.com", "Open")
	if len(blocks) != 4 {
		t.Fatalf("expected header+body+image+action, got %d", len(blocks))
	}
	if h, ok := blocks[0].(*slack.HeaderBlock); !ok || h.Text == nil || h.Text.Text != "Title" {
		t.Errorf("header block wrong: %#v", blocks[0])
	}
	if _, ok := blocks[1].(*slack.MarkdownBlock); !ok {
		t.Errorf("expected markdown body, got %T", blocks[1])
	}
	img, ok := blocks[2].(*slack.ImageBlock)
	if !ok || img.ImageURL != "https://cdn.example.com/x.png" {
		t.Errorf("image block wrong: %#v", blocks[2])
	}
	action, ok := blocks[3].(*slack.ActionBlock)
	if !ok {
		t.Fatalf("expected action block, got %T", blocks[3])
	}
	btn := action.Elements.ElementSet[0].(*slack.ButtonBlockElement)
	if btn.URL != "https://example.com" || btn.Text.Text != "Open" {
		t.Errorf("link button wrong: url=%q label=%q", btn.URL, btn.Text.Text)
	}
}

func TestCardBlocksLinkDefaultLabel(t *testing.T) {
	blocks := CardBlocks("", "", "", "https://example.com", "")
	action, ok := blocks[len(blocks)-1].(*slack.ActionBlock)
	if !ok {
		t.Fatalf("expected action block, got %T", blocks[len(blocks)-1])
	}
	btn := action.Elements.ElementSet[0].(*slack.ButtonBlockElement)
	if btn.Text.Text != "View" {
		t.Errorf("default link label = %q, want View", btn.Text.Text)
	}
}

func TestCardBlocksNeverEmpty(t *testing.T) {
	blocks := CardBlocks("", "", "", "", "")
	if len(blocks) != 1 {
		t.Fatalf("empty card should yield 1 placeholder block, got %d", len(blocks))
	}
	if _, ok := blocks[0].(*slack.MarkdownBlock); !ok {
		t.Errorf("placeholder should be a markdown block, got %T", blocks[0])
	}
}
