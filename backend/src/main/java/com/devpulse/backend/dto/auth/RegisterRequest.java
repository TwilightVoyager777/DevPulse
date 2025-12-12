package com.devpulse.backend.dto.auth;

public record RegisterRequest(String email, String password, String displayName) {}
