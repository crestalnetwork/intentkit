package bot

import "testing"

func TestCleanText(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want string
	}{
		{"plain", "plain text", "plain text"},
		{"user mention", "<@U123ABC> hello", "hello"},
		{"user mention with label", "<@U123ABC|john> hello", "hello"},
		{"channel mention", "<#C123ABC|general>", "#general"},
		{"special here", "<!here>", "@here"},
		{"subteam with label", "<!subteam^S1|@devs>", "@devs"},
		{"labelled link", "<https://x.com|click>", "click"},
		{"bare link", "<https://x.com>", "https://x.com"},
		{"html entities", "a &amp; b &lt; c", "a & b < c"},
		{"trims surrounding space", "  spaced  ", "spaced"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := cleanText(c.in); got != c.want {
				t.Errorf("cleanText(%q) = %q, want %q", c.in, got, c.want)
			}
		})
	}
}
