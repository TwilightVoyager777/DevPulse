package com.devpulse.backend.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.concurrent.TimeUnit;

/**
 * Manages all Redis key patterns:
 *   user:{userId}               TTL 5min  — user info cache
 *   ws:{workspaceId}            TTL 10min — workspace metadata cache
 *   docs:{workspaceId}          TTL 2min  — document list cache (invalidated on write)
 *   rl:{userId}:{minute}        TTL 60s   — rate limiting counter
 *   token:blacklist:{jti}       TTL = token remaining lifetime
 *   task:{taskId}               TTL 1h    — task status cache
 *   ai:cache:{wsId}:{hash}      TTL 30min — AI answer cache (circuit breaker fallback)
 *   stream:{sessionId}          Pub/Sub   — SSE streaming channel
 *   bm25:lock:{workspaceId}     TTL 60s   — BM25 rebuild distributed lock
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class RedisService {

    private static final int RATE_LIMIT_MAX = 10;

    private final StringRedisTemplate redisTemplate;

    // ── Token blacklist ─────────────────────────────────────────────────────

    public void blacklistToken(String jti, long ttlSeconds) {
        redisTemplate.opsForValue().set("token:blacklist:" + jti, "1", ttlSeconds, TimeUnit.SECONDS);
    }

    public boolean isTokenBlacklisted(String jti) {
        return Boolean.TRUE.equals(redisTemplate.hasKey("token:blacklist:" + jti));
    }

    // ── Rate limiting ───────────────────────────────────────────────────────

    /**
     * Returns true if the user has exceeded 10 requests/minute.
     * Uses INCR on key rl:{userId}:{currentMinute} with 60s TTL.
     */
    public boolean isRateLimited(String userId) {
        String minute = String.valueOf(Instant.now().getEpochSecond() / 60);
        String key = "rl:" + userId + ":" + minute;
        // Set with expiry only if the key doesn't exist yet
        redisTemplate.opsForValue().setIfAbsent(key, "0", 60L, TimeUnit.SECONDS);
        Long count = redisTemplate.opsForValue().increment(key);
        return count != null && count > RATE_LIMIT_MAX;
    }

    // ── Task status cache ───────────────────────────────────────────────────

    public void cacheTaskStatus(String taskId, String statusJson) {
        redisTemplate.opsForValue().set("task:" + taskId, statusJson, 1L, TimeUnit.HOURS);
    }

    public String getTaskStatus(String taskId) {
        return redisTemplate.opsForValue().get("task:" + taskId);
    }

    // ── AI answer cache (circuit breaker fallback) ─────────────────────────

    public void cacheAiResponse(String workspaceId, String questionHash, String response) {
        redisTemplate.opsForValue().set(
            "ai:cache:" + workspaceId + ":" + questionHash, response, 30L, TimeUnit.MINUTES);
    }

    public String getCachedAiResponse(String workspaceId, String questionHash) {
        return redisTemplate.opsForValue().get("ai:cache:" + workspaceId + ":" + questionHash);
    }

    // ── SSE Pub/Sub ─────────────────────────────────────────────────────────

    public void publishSseEvent(String sessionId, String eventJson) {
        redisTemplate.convertAndSend("stream:" + sessionId, eventJson);
    }

    // ── Generic cache helpers ───────────────────────────────────────────────

    public void set(String key, String value, long ttlSeconds) {
        redisTemplate.opsForValue().set(key, value, ttlSeconds, TimeUnit.SECONDS);
    }

    public String get(String key) {
        return redisTemplate.opsForValue().get(key);
    }

    public void delete(String key) {
        redisTemplate.delete(key);
    }

    public boolean hasKey(String key) {
        return Boolean.TRUE.equals(redisTemplate.hasKey(key));
    }
}
