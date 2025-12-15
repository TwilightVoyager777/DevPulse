package com.devpulse.backend.service;

import com.devpulse.backend.dto.auth.*;
import com.devpulse.backend.model.User;
import com.devpulse.backend.repository.UserRepository;
import com.devpulse.backend.security.JwtTokenProvider;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.time.Instant;
import java.util.Date;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock UserRepository userRepository;
    @Mock PasswordEncoder passwordEncoder;
    @Mock JwtTokenProvider jwtTokenProvider;
    @Mock RedisService redisService;
    @InjectMocks AuthService authService;

    @Test
    void register_success_returnsTokens() {
        RegisterRequest req = new RegisterRequest("new@test.com", "secret", "Alice");
        when(userRepository.existsByEmail("new@test.com")).thenReturn(false);
        when(passwordEncoder.encode("secret")).thenReturn("hashed");
        when(userRepository.save(any())).thenAnswer(inv -> {
            User u = inv.getArgument(0);
            u.setId(UUID.randomUUID());
            return u;
        });
        when(jwtTokenProvider.generateAccessToken(any(), eq("new@test.com"))).thenReturn("at");
        when(jwtTokenProvider.generateRefreshToken(any())).thenReturn("rt");

        AuthResponse resp = authService.register(req);

        assertThat(resp.accessToken()).isEqualTo("at");
        assertThat(resp.refreshToken()).isEqualTo("rt");
        assertThat(resp.email()).isEqualTo("new@test.com");
        verify(userRepository).save(argThat(u -> u.getEmail().equals("new@test.com")
            && u.getPasswordHash().equals("hashed")));
    }

    @Test
    void register_duplicateEmail_throwsIllegalArgument() {
        when(userRepository.existsByEmail("dupe@test.com")).thenReturn(true);
        assertThatThrownBy(() -> authService.register(new RegisterRequest("dupe@test.com", "p", "N")))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("already registered");
    }

    @Test
    void login_success_returnsTokens() {
        UUID userId = UUID.randomUUID();
        User user = User.builder()
            .id(userId).email("user@test.com").passwordHash("hashed").displayName("Bob").role("USER")
            .build();
        when(userRepository.findByEmail("user@test.com")).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("pw", "hashed")).thenReturn(true);
        when(jwtTokenProvider.generateAccessToken(userId, "user@test.com")).thenReturn("at");
        when(jwtTokenProvider.generateRefreshToken(userId)).thenReturn("rt");

        AuthResponse resp = authService.login(new LoginRequest("user@test.com", "pw"));

        assertThat(resp.accessToken()).isEqualTo("at");
        assertThat(resp.userId()).isEqualTo(userId);
    }

    @Test
    void login_wrongPassword_throwsBadCredentials() {
        User user = User.builder()
            .id(UUID.randomUUID()).email("u@t.com").passwordHash("hashed").build();
        when(userRepository.findByEmail("u@t.com")).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("wrong", "hashed")).thenReturn(false);

        assertThatThrownBy(() -> authService.login(new LoginRequest("u@t.com", "wrong")))
            .isInstanceOf(BadCredentialsException.class);
    }

    @Test
    void login_unknownUser_throwsBadCredentials() {
        when(userRepository.findByEmail("ghost@t.com")).thenReturn(Optional.empty());
        assertThatThrownBy(() -> authService.login(new LoginRequest("ghost@t.com", "pw")))
            .isInstanceOf(BadCredentialsException.class);
    }

    @Test
    void logout_blacklistsJti() {
        Claims claims = mock(Claims.class);
        when(claims.getId()).thenReturn("jti-abc");
        when(claims.getExpiration()).thenReturn(Date.from(Instant.now().plusSeconds(900)));
        when(jwtTokenProvider.parseClaims("token")).thenReturn(claims);

        authService.logout("token");

        ArgumentCaptor<Long> ttlCaptor = ArgumentCaptor.forClass(Long.class);
        verify(redisService).blacklistToken(eq("jti-abc"), ttlCaptor.capture());
        assertThat(ttlCaptor.getValue()).isBetween(800L, 900L);
    }

    @Test
    void refreshToken_valid_returnsNewTokens() {
        UUID userId = UUID.randomUUID();
        User user = User.builder()
            .id(userId).email("r@t.com").displayName("R").role("USER").build();
        Claims claims = mock(Claims.class);
        when(claims.getSubject()).thenReturn(userId.toString());
        when(jwtTokenProvider.parseClaims("rt")).thenReturn(claims);
        when(userRepository.findById(userId)).thenReturn(Optional.of(user));
        when(jwtTokenProvider.generateAccessToken(userId, "r@t.com")).thenReturn("new-at");
        when(jwtTokenProvider.generateRefreshToken(userId)).thenReturn("new-rt");

        AuthResponse resp = authService.refreshToken(new RefreshRequest("rt"));

        assertThat(resp.accessToken()).isEqualTo("new-at");
        assertThat(resp.refreshToken()).isEqualTo("new-rt");
    }

    @Test
    void refreshToken_invalid_throwsIllegalArgument() {
        when(jwtTokenProvider.parseClaims("bad-rt")).thenThrow(new JwtException("invalid"));
        assertThatThrownBy(() -> authService.refreshToken(new RefreshRequest("bad-rt")))
            .isInstanceOf(IllegalArgumentException.class);
    }
}
