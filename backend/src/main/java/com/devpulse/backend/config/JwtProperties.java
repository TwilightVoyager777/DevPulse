package com.devpulse.backend.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "jwt")
public class JwtProperties {
    private String privateKey;
    private String publicKey;
    private int accessTokenExpiryMinutes = 15;
    private int refreshTokenExpiryDays = 7;
}
