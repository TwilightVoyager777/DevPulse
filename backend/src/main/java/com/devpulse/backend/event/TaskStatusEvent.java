package com.devpulse.backend.event;

import java.util.List;
import java.util.UUID;

public record TaskStatusEvent(
    UUID taskId,
    UUID sessionId,
    UUID workspaceId,
    String status,           // "streaming", "done", "failed"
    String chunk,            // streaming chunk (null when done)
    boolean isDone,
    String fullResponse,     // final response (null during streaming)
    List<SourceInfo> sources,
    Integer tokensUsed,
    Long latencyMs,
    String errorMessage,
    int userMessageHash      // hash of the user's question for cache keying
) {
    public record SourceInfo(String title, double score, String snippet, UUID documentId) {}
}
