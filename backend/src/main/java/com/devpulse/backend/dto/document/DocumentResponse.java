package com.devpulse.backend.dto.document;

import java.time.Instant;
import java.util.UUID;

public record DocumentResponse(
    UUID id,
    UUID workspaceId,
    String title,
    String sourceType,
    String status,
    Integer chunkCount,
    String errorMessage,
    Instant createdAt,
    Instant indexedAt
) {}
