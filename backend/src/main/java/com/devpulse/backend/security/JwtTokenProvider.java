package com.devpulse.backend.security;

import com.devpulse.backend.config.JwtProperties;
import io.jsonwebtoken.*;
import org.springframework.stereotype.Component;

import java.security.*;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import java.util.Date;
import java.util.UUID;

@Component
public class JwtTokenProvider {

    private final RSAPrivateKey privateKey;
    private final RSAPublicKey publicKey;
    private final int accessExpiryMinutes;
    private final int refreshExpiryDays;

    public JwtTokenProvider(JwtProperties props) {
        RSAPrivateKey priv;
        RSAPublicKey pub;
        try {
            priv = loadPrivateKey(props.getPrivateKey());
            pub = loadPublicKey(props.getPublicKey());
        } catch (Exception e) {
            throw new IllegalStateException(
                "Failed to load JWT RSA keys. Ensure JWT_PRIVATE_KEY and JWT_PUBLIC_KEY are set correctly.", e);
        }
        this.privateKey = priv;
        this.publicKey = pub;
        this.accessExpiryMinutes = props.getAccessTokenExpiryMinutes();
        this.refreshExpiryDays = props.getRefreshTokenExpiryDays();
    }

    public String generateAccessToken(UUID userId, String email) {
        return Jwts.builder()
            .id(UUID.randomUUID().toString())
            .subject(userId.toString())
            .claim("email", email)
            .claim("type", "access")
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + (long) accessExpiryMinutes * 60_000))
            .signWith(privateKey)
            .compact();
    }

    public String generateRefreshToken(UUID userId) {
        return Jwts.builder()
            .id(UUID.randomUUID().toString())
            .subject(userId.toString())
            .claim("type", "refresh")
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + (long) refreshExpiryDays * 86_400_000))
            .signWith(privateKey)
            .compact();
    }

    public Claims parseClaims(String token) {
        return Jwts.parser()
            .verifyWith(publicKey)
            .build()
            .parseSignedClaims(token)
            .getPayload();
    }

    public boolean validateToken(String token) {
        try {
            parseClaims(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }

    public String getJti(String token) {
        return parseClaims(token).getId();
    }

    public String getSubject(String token) {
        return parseClaims(token).getSubject();
    }

    private RSAPrivateKey loadPrivateKey(String pem) throws Exception {
        String cleaned = pem.replaceAll("-----BEGIN.*?-----", "")
                            .replaceAll("-----END.*?-----", "")
                            .replaceAll("\\s+", "");
        byte[] decoded = Base64.getDecoder().decode(cleaned);
        KeyFactory kf = KeyFactory.getInstance("RSA");
        return (RSAPrivateKey) kf.generatePrivate(new PKCS8EncodedKeySpec(decoded));
    }

    private RSAPublicKey loadPublicKey(String pem) throws Exception {
        String cleaned = pem.replaceAll("-----BEGIN.*?-----", "")
                            .replaceAll("-----END.*?-----", "")
                            .replaceAll("\\s+", "");
        byte[] decoded = Base64.getDecoder().decode(cleaned);
        KeyFactory kf = KeyFactory.getInstance("RSA");
        return (RSAPublicKey) kf.generatePublic(new X509EncodedKeySpec(decoded));
    }
}
