package com.devpulse.backend.dto.session;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record MessageResponse(
    UUID id,
    String role,
    String content,
    List<SourceInfo> sources,
    Integer tokensUsed,
    Long latencyMs,
    Instant createdAt
) {
    public record SourceInfo(String title, double score, String snippet, UUID documentId) {}
}
