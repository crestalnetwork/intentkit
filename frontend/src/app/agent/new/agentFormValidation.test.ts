import { describe, expect, it } from "vitest";
import { validateAgentForm } from "./AgentForm";
import { cleanAgentPayload } from "./formUtils";

/**
 * The form's constraints are a hand-written mirror of `AgentUpdate` in
 * intentkit/models/agent/user_input.py. Nothing enforces that at build time, so
 * these cases pin the ones that are easy to get subtly wrong.
 *
 * The heading cases are the same table as
 * tests/models/test_agent_system_prompt.py::TestHeadingRuleCases, which asserts
 * them against the server validator. Keep the two in step.
 */

describe("system_prompt heading rule", () => {
    it.each([
        ["plain text", true],
        ["## Section\n\nbody", true],
        ["### Deep\n\nbody\n\n#### Deeper", true],
        ["#hashtag no space", true],
        // A bare "#" is not a heading -- the server's rule is /^# /m, so the
        // trailing space matters.
        ["#", true],
        ["intro\n#\nbody", true],
        ["# Top Heading", false],
        ["intro\n# Mid Heading\nbody", false],
    ])("%j -> allowed=%s", (text, allowed) => {
        const errors = validateAgentForm({ name: "T", system_prompt: text });
        expect(errors.system_prompt === undefined).toBe(allowed);
    });
});

describe("sub_agent_prompt heading rule", () => {
    it.each([
        ["plain text", true],
        ["### Deep", true],
        ["#", true],
        ["# Top", false],
        ["## Second", false],
    ])("%j -> allowed=%s", (text, allowed) => {
        const errors = validateAgentForm({ name: "T", sub_agent_prompt: text });
        expect(errors.sub_agent_prompt === undefined).toBe(allowed);
    });
});

describe("slug rule", () => {
    it.each([
        ["ab", true], // server allows 2 characters
        ["my-agent", true],
        ["a".repeat(60), true],
        ["a", false],
        ["a".repeat(61), false],
        ["1abc", false], // must start with a letter
        ["My-Agent", false], // lowercase only
        ["trailing-", false],
    ])("%j -> allowed=%s", (slug, allowed) => {
        const errors = validateAgentForm({ name: "T", slug });
        expect(errors.slug === undefined).toBe(allowed);
    });
});

describe("name rule", () => {
    it("is required", () => {
        expect(validateAgentForm({}).name).toBeDefined();
        expect(validateAgentForm({ name: "   " }).name).toBeDefined();
    });

    it("is capped at 50 characters", () => {
        expect(validateAgentForm({ name: "a".repeat(50) }).name).toBeUndefined();
        expect(validateAgentForm({ name: "a".repeat(51) }).name).toBeDefined();
    });
});

describe("description", () => {
    it("has no length limit, matching the server", () => {
        const errors = validateAgentForm({ name: "T", description: "a".repeat(50000) });
        expect(errors.description).toBeUndefined();
    });
});

describe("cleanAgentPayload", () => {
    it("always sends a model on create so the server can pick its default", () => {
        // `model` is required by the API; omitting the key is a 422, whereas ""
        // routes to pick_default_model().
        expect(cleanAgentPayload({ name: "T" }, "create").model).toBe("");
    });

    it("keeps an explicitly chosen model on create", () => {
        expect(cleanAgentPayload({ name: "T", model: "x" }, "create").model).toBe("x");
    });

    it("does not invent a model on edit", () => {
        expect("model" in cleanAgentPayload({ name: "T" }, "edit")).toBe(false);
    });

    it("drops empties on create so server defaults apply", () => {
        const out = cleanAgentPayload(
            { name: "T", system_prompt: "", tools: [], sub_agents: [] },
            "create",
        );
        expect("system_prompt" in out).toBe(false);
        expect("tools" in out).toBe(false);
        expect("sub_agents" in out).toBe(false);
    });

    it("sends empties on edit so clearing a field lands", () => {
        const out = cleanAgentPayload(
            { name: "T", system_prompt: "", tools: [] },
            "edit",
        );
        expect(out.system_prompt).toBe("");
        expect(out.tools).toEqual([]);
    });

    it("sends null on edit but not on create", () => {
        // "Model default" for reasoning_effort: "" would be a literal_error
        // server-side, so the cleared value must travel as null.
        expect(cleanAgentPayload({ reasoning_effort: null }, "edit").reasoning_effort)
            .toBeNull();
        expect("reasoning_effort" in cleanAgentPayload({ reasoning_effort: null }, "create"))
            .toBe(false);
    });

    it("de-duplicates tool names", () => {
        const out = cleanAgentPayload({ tools: ["a", "b", "a"] }, "edit");
        expect(out.tools).toEqual(["a", "b"]);
    });
});
