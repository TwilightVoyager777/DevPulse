package com.devpulse.backend.dto.workspace;

import java.time.Instant;
import java.util.UUID;

public record WorkspaceResponse(UUID id, String name, UUID ownerId, Instant createdAt) {}
