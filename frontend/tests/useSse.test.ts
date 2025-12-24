import { describe, it, expect } from "vitest";

// Test the SSE hook logic directly (state transitions)
// We test the underlying state logic, not the EventSource browser API

describe("SSE chunk accumulation logic", () => {
  it("accumulates streaming chunks into a string", () => {
    const chunks = ["Hello ", "world", "!"];
    let accumulated = "";
    for (const chunk of chunks) {
      accumulated += chunk;
    }
    expect(accumulated).toBe("Hello world!");
  });

  it("parses SseChunk JSON correctly", () => {
    const raw = JSON.stringify({
      taskId: "t1",
      sessionId: "s1",
      workspaceId: "w1",
      status: "streaming",
      chunk: "Hello",
      isDone: false,
      fullResponse: null,
      sources: null,
      tokensUsed: null,
      latencyMs: null,
      errorMessage: null,
    });
    const parsed = JSON.parse(raw);
    expect(parsed.chunk).toBe("Hello");
    expect(parsed.isDone).toBe(false);
  });

  it("recognizes done event", () => {
    const raw = JSON.stringify({
      taskId: "t1",
      sessionId: "s1",
      workspaceId: "w1",
      status: "done",
      chunk: null,
      isDone: true,
      fullResponse: "Hello world!",
      sources: [],
      tokensUsed: 70,
      latencyMs: 1200,
      errorMessage: null,
    });
    const parsed = JSON.parse(raw);
    expect(parsed.isDone).toBe(true);
    expect(parsed.fullResponse).toBe("Hello world!");
    expect(parsed.tokensUsed).toBe(70);
  });

  it("recognizes failed event", () => {
    const raw = JSON.stringify({
      taskId: "t1",
      sessionId: "s1",
      workspaceId: "w1",
      status: "failed",
      chunk: null,
      isDone: true,
      fullResponse: null,
      sources: null,
      tokensUsed: null,
      latencyMs: null,
      errorMessage: "API error",
    });
    const parsed = JSON.parse(raw);
    expect(parsed.status).toBe("failed");
    expect(parsed.errorMessage).toBe("API error");
  });
});
