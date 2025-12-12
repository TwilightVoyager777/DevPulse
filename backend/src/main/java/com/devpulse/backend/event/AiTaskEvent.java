package com.devpulse.backend.event;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record AiTaskEvent(
    UUID taskId,
    UUID sessionId,
    UUID workspaceId,
    String userMessage,
    List<ConversationMessage> conversationHistory,  // last 10 messages
    Instant createdAt
) {
    public record ConversationMessage(String role, String content) {}
}
