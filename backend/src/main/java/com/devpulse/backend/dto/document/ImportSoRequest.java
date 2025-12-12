package com.devpulse.backend.dto.document;

import java.util.Map;

public record ImportSoRequest(
    String title,
    String content,
    Map<String, Object> metadata
) {}
