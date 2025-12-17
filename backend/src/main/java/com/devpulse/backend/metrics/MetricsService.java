package com.devpulse.backend.metrics;

import com.devpulse.backend.service.SseService;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.micrometer.core.instrument.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.concurrent.TimeUnit;

/**
 * Registers all 10 custom Prometheus metrics for DevPulse backend.
 *
 * Metric names use dots in builder (Micrometer convention) — Prometheus
 * auto-converts to underscores, e.g. "devpulse.api.request.total" → "devpulse_api_request_total".
 */
@Component
@Slf4j
public class MetricsService {

    private final MeterRegistry meterRegistry;
    private final Counter rateLimitCounter;

    public MetricsService(MeterRegistry meterRegistry,
                           CircuitBreakerRegistry circuitBreakerRegistry,
                           SseService sseService) {
        this.meterRegistry = meterRegistry;

        // devpulse_rate_limit_exceeded_total
        this.rateLimitCounter = Counter.builder("devpulse.rate.limit.exceeded.total")
            .description("Number of rate limit violations")
            .register(meterRegistry);

        // devpulse_active_sse_connections (Gauge backed by SseService)
        Gauge.builder("devpulse.active.sse.connections", sseService, SseService::activeConnectionCount)
            .description("Number of active SSE connections")
            .register(meterRegistry);

        // devpulse_circuit_breaker_state{name} — 0=closed, 1=open, 2=half_open
        Gauge.builder("devpulse.circuit.breaker.state",
                circuitBreakerRegistry, registry -> {
                    try {
                        io.github.resilience4j.circuitbreaker.CircuitBreaker cb =
                            registry.circuitBreaker("aiWorker");
                        return switch (cb.getState()) {
                            case CLOSED    -> 0.0;
                            case OPEN      -> 1.0;
                            case HALF_OPEN -> 2.0;
                            default        -> -1.0;
                        };
                    } catch (Exception e) {
                        return -1.0;
                    }
                })
            .tag("name", "aiWorker")
            .description("Circuit breaker state: 0=closed, 1=open, 2=half_open")
            .register(meterRegistry);

        log.info("DevPulse metrics registered");
    }

    // ── Per-request metrics (recorded by MetricsInterceptor) ────────────────

    public void recordRequest(String method, String endpoint, int status) {
        Counter.builder("devpulse.api.request.total")
            .tag("method", method)
            .tag("endpoint", normalizeEndpoint(endpoint))
            .tag("status", String.valueOf(status))
            .register(meterRegistry)
            .increment();
    }

    public void recordLatency(String endpoint, long durationMs) {
        Timer.builder("devpulse.api.latency.seconds")
            .tag("endpoint", normalizeEndpoint(endpoint))
            .publishPercentiles(0.5, 0.95, 0.99)
            .serviceLevelObjectives(
                java.time.Duration.ofMillis(50),
                java.time.Duration.ofMillis(100),
                java.time.Duration.ofMillis(300),
                java.time.Duration.ofSeconds(1),
                java.time.Duration.ofSeconds(3),
                java.time.Duration.ofSeconds(10))
            .register(meterRegistry)
            .record(durationMs, TimeUnit.MILLISECONDS);
    }

    // ── Kafka metrics ────────────────────────────────────────────────────────

    public void recordKafkaProduced(String topic) {
        Counter.builder("devpulse.kafka.messages.produced.total")
            .tag("topic", topic)
            .register(meterRegistry)
            .increment();
    }

    public void recordKafkaConsumed(String topic, String status) {
        Counter.builder("devpulse.kafka.messages.consumed.total")
            .tag("topic", topic)
            .tag("status", status)
            .register(meterRegistry)
            .increment();
    }

    // ── Cache metrics ────────────────────────────────────────────────────────

    public void recordCacheHit(String keyType) {
        Counter.builder("devpulse.cache.hit.total")
            .tag("key_type", keyType)
            .register(meterRegistry)
            .increment();
    }

    public void recordCacheMiss(String keyType) {
        Counter.builder("devpulse.cache.miss.total")
            .tag("key_type", keyType)
            .register(meterRegistry)
            .increment();
    }

    // ── Rate limit + circuit breaker fallback ───────────────────────────────

    public void recordRateLimitExceeded() {
        rateLimitCounter.increment();
    }

    public void recordCircuitBreakerFallback(String reason) {
        Counter.builder("devpulse.circuit.breaker.fallback.total")
            .tag("reason", reason)
            .register(meterRegistry)
            .increment();
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    /**
     * Normalize endpoint paths to avoid high-cardinality labels.
     * e.g. /api/workspaces/550e8400.../documents → /api/workspaces/{id}/documents
     */
    private String normalizeEndpoint(String path) {
        return path.replaceAll(
            "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}");
    }
}
