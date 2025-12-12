package com.devpulse.backend.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class RedisServiceTest {

    @Mock StringRedisTemplate redisTemplate;
    @Mock ValueOperations<String, String> valueOps;
    @InjectMocks RedisService redisService;

    @Test
    void blacklistToken_setsKeyWithTtl() {
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        redisService.blacklistToken("jti-123", 900L);
        verify(valueOps).set("token:blacklist:jti-123", "1", 900L, TimeUnit.SECONDS);
    }

    @Test
    void isTokenBlacklisted_keyExists_returnsTrue() {
        when(redisTemplate.hasKey("token:blacklist:jti-456")).thenReturn(true);
        assertThat(redisService.isTokenBlacklisted("jti-456")).isTrue();
    }

    @Test
    void isTokenBlacklisted_keyAbsent_returnsFalse() {
        when(redisTemplate.hasKey("token:blacklist:jti-789")).thenReturn(false);
        assertThat(redisService.isTokenBlacklisted("jti-789")).isFalse();
    }

    @Test
    void isRateLimited_underLimit_returnsFalse() {
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        when(valueOps.increment(anyString())).thenReturn(5L);
        assertThat(redisService.isRateLimited("user1")).isFalse();
        verify(valueOps).setIfAbsent(anyString(), eq("0"), eq(60L), eq(TimeUnit.SECONDS));
    }

    @Test
    void isRateLimited_atLimit_returnsTrue() {
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        when(valueOps.increment(anyString())).thenReturn(11L);
        assertThat(redisService.isRateLimited("user1")).isTrue();
    }

    @Test
    void getCachedAiResponse_hit_returnsValue() {
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        when(valueOps.get("ai:cache:ws1:hash1")).thenReturn("Cached answer");
        assertThat(redisService.getCachedAiResponse("ws1", "hash1")).isEqualTo("Cached answer");
    }

    @Test
    void getCachedAiResponse_miss_returnsNull() {
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        when(valueOps.get("ai:cache:ws1:hash2")).thenReturn(null);
        assertThat(redisService.getCachedAiResponse("ws1", "hash2")).isNull();
    }
}
