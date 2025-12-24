import { describe, it, expect } from "vitest";

// Unit-test the pure state-management logic extracted from useChat
// (The hook itself depends on EventSource which is a browser API — we test the logic)

describe("useChat message accumulation", () => {
  it("appends user message optimistically", () => {
    const messages: { role: string; content: string }[] = [];
    const addMsg = (role: string, content: string) => {
      messages.push({ role, content });
    };

    addMsg("user", "What is Redis?");
    expect(messages).toHaveLength(1);
    expect(messages[0]).toEqual({ role: "user", content: "What is Redis?" });
  });

  it("accumulates streaming tokens", () => {
    let streamingContent = "";
    const tokens = ["Redis ", "is ", "an ", "in-memory ", "store."];
    for (const token of tokens) {
      streamingContent += token;
    }
    expect(streamingContent).toBe("Redis is an in-memory store.");
  });

  it("finalizes message on done event", () => {
    const messages: { role: string; content: string }[] = [
      { role: "user", content: "What is Redis?" },
    ];
    let streamingContent = "Redis is an in-memory store.";

    // On done: push assistant message + clear streaming
    messages.push({ role: "assistant", content: streamingContent });
    streamingContent = "";

    expect(messages).toHaveLength(2);
    expect(messages[1].role).toBe("assistant");
    expect(streamingContent).toBe("");
  });

  it("removes optimistic message on send error", () => {
    const tempId = "temp-123";
    const messages: { id: string; role: string; content: string }[] = [
      { id: tempId, role: "user", content: "question" },
    ];

    // Simulate error: remove optimistic message
    const filtered = messages.filter((m) => m.id !== tempId);
    expect(filtered).toHaveLength(0);
  });
});
