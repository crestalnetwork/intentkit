package shared

import "testing"

func todoParams(items ...map[string]interface{}) map[string]interface{} {
	list := make([]interface{}, 0, len(items))
	for _, item := range items {
		list = append(list, item)
	}
	return map[string]interface{}{"todos": list}
}

func TestRenderTodoStatusFreshPlan(t *testing.T) {
	got := renderTodoStatus(todoParams(
		map[string]interface{}{"content": "research", "status": "in_progress"},
		map[string]interface{}{"content": "implement", "status": "pending"},
		map[string]interface{}{"content": "test", "status": "pending"},
	))
	want := "📋 0/3\n🔄 research\n⬜ implement\n⬜ test"
	if got != want {
		t.Errorf("fresh plan render mismatch:\ngot:  %q\nwant: %q", got, want)
	}
}

func TestRenderTodoStatusProgressLine(t *testing.T) {
	got := renderTodoStatus(todoParams(
		map[string]interface{}{"content": "research", "status": "completed"},
		map[string]interface{}{"content": "implement", "status": "in_progress"},
		map[string]interface{}{"content": "test", "status": "pending"},
	))
	want := "📋 1/3 · 🔄 implement"
	if got != want {
		t.Errorf("progress render mismatch:\ngot:  %q\nwant: %q", got, want)
	}
}

func TestRenderTodoStatusAllCompleted(t *testing.T) {
	got := renderTodoStatus(todoParams(
		map[string]interface{}{"content": "research", "status": "completed"},
		map[string]interface{}{"content": "implement", "status": "completed"},
	))
	want := "📋 2/2"
	if got != want {
		t.Errorf("completed render mismatch:\ngot:  %q\nwant: %q", got, want)
	}
}

func TestRenderTodoStatusFallsBackOnBadShape(t *testing.T) {
	cases := []map[string]interface{}{
		{},                         // no todos key
		{"todos": "not a list"},    // wrong type
		{"todos": []interface{}{}}, // empty list
		todoParams(map[string]interface{}{"content": "x"}),      // missing status
		todoParams(map[string]interface{}{"status": "pending"}), // missing content
		{"todos": []interface{}{"not a map"}},                   // wrong item type
	}
	for i, params := range cases {
		if got := renderTodoStatus(params); got != "" {
			t.Errorf("case %d: expected empty fallback, got %q", i, got)
		}
	}
}
