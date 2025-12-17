package com.devpulse.backend.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Manages SSE emitters and bridges Redis Pub/Sub messages to browser SSE connections.
 * Registered as a pattern listener on "stream:*" in RedisConfig.
 */
@Service
@Slf4j
public class SseService implements MessageListener {

    private static final long SSE_TIMEOUT_MS = 300_000L; // 5 minutes

    private final Map<String, CopyOnWriteArrayList<SseEmitter>> emittersBySession =
        new ConcurrentHashMap<>();

    public SseEmitter createEmitter(String sessionId) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        emittersBySession.computeIfAbsent(sessionId, k -> new CopyOnWriteArrayList<>()).add(emitter);

        Runnable cleanup = () -> removeEmitter(sessionId, emitter);
        emitter.onCompletion(cleanup);
        emitter.onTimeout(cleanup);
        emitter.onError(e -> {
            log.debug("SSE error for session {}: {}", sessionId, e.getMessage());
            removeEmitter(sessionId, emitter);
        });

        log.debug("SSE emitter registered for session {}, total={}", sessionId,
            emittersBySession.get(sessionId).size());
        return emitter;
    }

    /**
     * Called by RedisMessageListenerContainer when a message arrives on stream:* pattern.
     */
    @Override
    public void onMessage(Message message, byte[] pattern) {
        String channel = new String(message.getChannel());
        // channel = "stream:{sessionId}"
        String sessionId = channel.length() > 7 ? channel.substring(7) : "";
        String payload = new String(message.getBody());

        CopyOnWriteArrayList<SseEmitter> emitters = emittersBySession.get(sessionId);
        if (emitters == null || emitters.isEmpty()) return;

        emitters.removeIf(emitter -> {
            try {
                emitter.send(SseEmitter.event().data(payload));
                return false;
            } catch (IOException e) {
                log.debug("Removing dead SSE emitter for session {}", sessionId);
                return true;
            }
        });
    }

    public int activeConnectionCount() {
        return emittersBySession.values().stream().mapToInt(List::size).sum();
    }

    private void removeEmitter(String sessionId, SseEmitter emitter) {
        CopyOnWriteArrayList<SseEmitter> emitters = emittersBySession.get(sessionId);
        if (emitters != null) {
            emitters.remove(emitter);
            if (emitters.isEmpty()) {
                emittersBySession.remove(sessionId);
            }
        }
    }
}
