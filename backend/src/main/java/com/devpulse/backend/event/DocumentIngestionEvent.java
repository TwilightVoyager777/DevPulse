package com.devpulse.backend.event;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record DocumentIngestionEvent(
    UUID documentId,
    UUID workspaceId,
    String sourceType,       // "UPLOAD", "SO_IMPORT"
    String contentOrPath,    // file content or path
    Map<String, Object> metadata,
    Instant createdAt
) {}
