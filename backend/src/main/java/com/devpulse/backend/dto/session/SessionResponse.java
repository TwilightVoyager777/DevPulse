package com.devpulse.backend.dto.session;

import java.time.Instant;
import java.util.UUID;

public record SessionResponse(UUID id, UUID workspaceId, String title, Instant createdAt, Instant updatedAt) {}
