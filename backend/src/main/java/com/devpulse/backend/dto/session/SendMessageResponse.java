package com.devpulse.backend.dto.session;

import java.util.UUID;

public record SendMessageResponse(UUID taskId, UUID messageId) {}
