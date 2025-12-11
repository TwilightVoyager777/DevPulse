package com.devpulse.backend.security;

import com.devpulse.backend.config.JwtProperties;
import io.jsonwebtoken.Claims;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.util.Base64;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;

class JwtTokenProviderTest {

    static JwtTokenProvider provider;

    @BeforeAll
    static void setup() throws Exception {
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048);
        KeyPair pair = gen.generateKeyPair();

        String privatePem = "-----BEGIN PRIVATE KEY-----\n" +
            Base64.getMimeEncoder(64, new byte[]{'\n'}).encodeToString(pair.getPrivate().getEncoded()) +
            "\n-----END PRIVATE KEY-----";
        String publicPem = "-----BEGIN PUBLIC KEY-----\n" +
            Base64.getMimeEncoder(64, new byte[]{'\n'}).encodeToString(pair.getPublic().getEncoded()) +
            "\n-----END PUBLIC KEY-----";

        JwtProperties props = new JwtProperties();
        props.setPrivateKey(privatePem);
        props.setPublicKey(publicPem);
        props.setAccessTokenExpiryMinutes(15);
        props.setRefreshTokenExpiryDays(7);

        provider = new JwtTokenProvider(props);
    }

    @Test
    void generateAccessToken_containsSubjectAndEmail() {
        UUID userId = UUID.randomUUID();
        String token = provider.generateAccessToken(userId, "user@test.com");

        assertThat(token).isNotBlank();
        assertThat(provider.getSubject(token)).isEqualTo(userId.toString());
        Claims claims = provider.parseClaims(token);
        assertThat(claims.get("email", String.class)).isEqualTo("user@test.com");
        assertThat(claims.get("type", String.class)).isEqualTo("access");
    }

    @Test
    void generateRefreshToken_typeIsRefresh() {
        UUID userId = UUID.randomUUID();
        String token = provider.generateRefreshToken(userId);

        Claims claims = provider.parseClaims(token);
        assertThat(claims.get("type", String.class)).isEqualTo("refresh");
        assertThat(claims.getSubject()).isEqualTo(userId.toString());
    }

    @Test
    void validateToken_validToken_returnsTrue() {
        String token = provider.generateAccessToken(UUID.randomUUID(), "a@b.com");
        assertThat(provider.validateToken(token)).isTrue();
    }

    @Test
    void validateToken_tamperedToken_returnsFalse() {
        String token = provider.generateAccessToken(UUID.randomUUID(), "a@b.com");
        String tampered = token.substring(0, token.length() - 5) + "XXXXX";
        assertThat(provider.validateToken(tampered)).isFalse();
    }

    @Test
    void getJti_returnsNonNullId() {
        String token = provider.generateAccessToken(UUID.randomUUID(), "a@b.com");
        assertThat(provider.getJti(token)).isNotBlank();
    }
}
