package com.devpulse.backend.service;

import com.devpulse.backend.dto.auth.*;
import com.devpulse.backend.model.User;
import com.devpulse.backend.repository.UserRepository;
import com.devpulse.backend.security.JwtTokenProvider;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final RedisService redisService;

    public AuthResponse register(RegisterRequest req) {
        if (userRepository.existsByEmail(req.email())) {
            throw new IllegalArgumentException("Email already registered");
        }
        User user = User.builder()
            .email(req.email())
            .passwordHash(passwordEncoder.encode(req.password()))
            .displayName(req.displayName())
            .role("USER")
            .build();
        User saved = userRepository.save(user);
        return buildAuthResponse(saved);
    }

    public AuthResponse login(LoginRequest req) {
        User user = userRepository.findByEmail(req.email())
            .orElseThrow(() -> new BadCredentialsException("Invalid credentials"));
        if (!passwordEncoder.matches(req.password(), user.getPasswordHash())) {
            throw new BadCredentialsException("Invalid credentials");
        }
        return buildAuthResponse(user);
    }

    public void logout(String token) {
        var claims = jwtTokenProvider.parseClaims(token);
        String jti = claims.getId();
        long remainingSeconds = (claims.getExpiration().getTime() - System.currentTimeMillis()) / 1000;
        if (remainingSeconds > 0) {
            redisService.blacklistToken(jti, remainingSeconds);
        }
    }

    public AuthResponse refreshToken(RefreshRequest req) {
        String token = req.refreshToken();
        io.jsonwebtoken.Claims claims;
        try {
            claims = jwtTokenProvider.parseClaims(token);
        } catch (io.jsonwebtoken.JwtException | IllegalArgumentException e) {
            throw new IllegalArgumentException("Invalid or expired refresh token");
        }
        UUID userId = UUID.fromString(claims.getSubject());
        User user = userRepository.findById(userId)
            .orElseThrow(() -> new IllegalArgumentException("User not found"));
        return buildAuthResponse(user);
    }

    private AuthResponse buildAuthResponse(User user) {
        String accessToken  = jwtTokenProvider.generateAccessToken(user.getId(), user.getEmail());
        String refreshToken = jwtTokenProvider.generateRefreshToken(user.getId());
        return new AuthResponse(accessToken, refreshToken, user.getId(),
                                user.getEmail(), user.getDisplayName());
    }
}
