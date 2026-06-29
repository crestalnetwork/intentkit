package slackclient

import (
	"strconv"

	"github.com/slack-go/slack"
)

// This file builds Slack Block Kit messages. Blocks are the main UX lever the
// Slack integration leans on: agent replies render through a `markdown` block
// (so standard LLM markdown — bold, lists, code, links — displays natively
// instead of as Slack's divergent mrkdwn or raw syntax), and choices render as
// real buttons that post back through the block-actions interaction instead of
// a numbered text list.
//
// The builders are pure (values in, []slack.Block out) so they can be unit
// tested without a live workspace. Orchestration that needs the Web API
// (uploading media, downloading attachments) lives in client.go.

// ChoiceActionPrefix prefixes the action_id of every choice button. Each button
// in a message needs a unique action_id, so the index is appended; the handler
// matches on this prefix and forwards the button's value (the option text) to
// the lead agent as the user's reply.
const ChoiceActionPrefix = "ik_choice_"

// linkActionID is the action_id of a card's URL button. Clicking a URL button
// still emits a block-actions interaction (which the handler ignores, since the
// id lacks ChoiceActionPrefix) in addition to opening the link.
const linkActionID = "ik_link"

// Block Kit field limits (characters). Over-long values are rejected by Slack,
// so labels/values are truncated to keep a rich send from failing.
const (
	maxButtonLabel = 75
	maxButtonValue = 2000
	maxHeaderText  = 150
	// maxMarkdownText caps each markdown block below Slack's 12000-char limit.
	// Long agent replies are split across blocks (Slack allows up to 50 per
	// message) so native markdown rendering survives instead of the whole reply
	// falling back to plain text.
	maxMarkdownText = 11000
)

// TextBlocks renders text as one or more native-markdown blocks. Used for agent
// text and tool/system status lines so LLM markdown renders natively; long text
// is split across blocks so even a long reply keeps native rendering.
func TextBlocks(text string) []slack.Block {
	chunks := splitForBlocks(text, maxMarkdownText)
	blocks := make([]slack.Block, 0, len(chunks))
	for _, c := range chunks {
		blocks = append(blocks, slack.NewMarkdownBlock("", c))
	}
	return blocks
}

// splitForBlocks splits s into chunks of at most limit runes, preferring to
// break at the last newline within each window so markdown lines aren't cut
// mid-line. Returns a single chunk when s already fits.
func splitForBlocks(s string, limit int) []string {
	r := []rune(s)
	if len(r) <= limit {
		return []string{s}
	}
	var chunks []string
	for len(r) > limit {
		cut := limit
		for i := limit - 1; i > limit/2; i-- {
			if r[i] == '\n' {
				cut = i + 1
				break
			}
		}
		chunks = append(chunks, string(r[:cut]))
		r = r[cut:]
	}
	if len(r) > 0 {
		chunks = append(chunks, string(r))
	}
	return chunks
}

// ChoiceBlocks renders a question (native markdown) followed by one button per
// option. Each button carries its option text as the action value; clicking it
// fires a block-actions interaction the handler forwards to the lead agent.
// Users who type the option text instead get the same result, so the buttons
// degrade gracefully.
func ChoiceBlocks(question string, options []string) []slack.Block {
	blocks := make([]slack.Block, 0, 2)
	if question != "" {
		blocks = append(blocks, slack.NewMarkdownBlock("", question))
	}
	elements := make([]slack.BlockElement, 0, len(options))
	for i, opt := range options {
		label := truncateRunes(opt, maxButtonLabel)
		if label == "" {
			label = strconv.Itoa(i + 1)
		}
		elements = append(elements, slack.NewButtonBlockElement(
			ChoiceActionPrefix+strconv.Itoa(i),
			truncateRunes(opt, maxButtonValue),
			slack.NewTextBlockObject(slack.PlainTextType, label, true, false),
		))
	}
	if len(elements) > 0 {
		blocks = append(blocks, slack.NewActionBlock("", elements...))
	}
	return blocks
}

// CardBlocks renders a card attachment: an optional header (title), a native-
// markdown body, an optional cover image (public URL), and an optional link
// button. Any empty field is omitted; an all-empty card still yields one block
// so the send never fails on an empty message.
func CardBlocks(title, description, imageURL, linkURL, label string) []slack.Block {
	blocks := make([]slack.Block, 0, 4)
	if title != "" {
		blocks = append(blocks, slack.NewHeaderBlock(
			slack.NewTextBlockObject(slack.PlainTextType, truncateRunes(title, maxHeaderText), false, false)))
	}
	if description != "" {
		blocks = append(blocks, slack.NewMarkdownBlock("", description))
	}
	if imageURL != "" {
		alt := title
		if alt == "" {
			alt = "image"
		}
		blocks = append(blocks, slack.NewImageBlock(imageURL, alt, "", nil))
	}
	if linkURL != "" {
		btnLabel := label
		if btnLabel == "" {
			btnLabel = "View"
		}
		btn := slack.NewButtonBlockElement(linkActionID, "",
			slack.NewTextBlockObject(slack.PlainTextType, truncateRunes(btnLabel, maxButtonLabel), false, false)).
			WithURL(linkURL).
			WithStyle(slack.StylePrimary)
		blocks = append(blocks, slack.NewActionBlock("", btn))
	}
	if len(blocks) == 0 {
		blocks = append(blocks, slack.NewMarkdownBlock("", " "))
	}
	return blocks
}

// truncateRunes shortens s to at most max runes, appending an ellipsis when cut.
func truncateRunes(s string, max int) string {
	r := []rune(s)
	if len(r) <= max {
		return s
	}
	if max <= 1 {
		return string(r[:max])
	}
	return string(r[:max-1]) + "…"
}
