from prometheus_client import Counter, Histogram, Gauge, Info

# App info gauge
APP_INFO = Info("devpulse_ai_worker", "AI Worker build info")

# ── Ingestion ─────────────────────────────────────────────────────────────────

INGESTION_DOCUMENTS_TOTAL = Counter(
    "devpulse_ingestion_documents_total",
    "Total documents ingested",
    ["status"],  # "indexed" | "failed"
)

INGESTION_CHUNKS_TOTAL = Counter(
    "devpulse_ingestion_chunks_total",
    "Total chunks created during ingestion",
)

INGESTION_LATENCY_SECONDS = Histogram(
    "devpulse_ingestion_latency_seconds",
    "Document ingestion duration in seconds",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# ── Retrieval ─────────────────────────────────────────────────────────────────

RETRIEVAL_LATENCY_SECONDS = Histogram(
    "devpulse_retrieval_latency_seconds",
    "Retrieval step latency in seconds",
    ["method"],  # "vector" | "bm25" | "rrf"
    buckets=[0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0],
)

RETRIEVAL_TOP_SCORE = Histogram(
    "devpulse_retrieval_top_score",
    "RRF top score distribution",
    buckets=[0.005, 0.01, 0.015, 0.02, 0.03, 0.05, 0.1],
)

RETRIEVAL_SOURCES_COUNT = Histogram(
    "devpulse_retrieval_sources_count",
    "Number of sources returned per retrieval",
    buckets=[0, 1, 2, 3, 4, 5, 10],
)

# ── BM25 cache ────────────────────────────────────────────────────────────────

BM25_CACHE_HIT_TOTAL = Counter(
    "devpulse_bm25_cache_hit_total",
    "BM25 index cache hits by layer",
    ["layer"],  # "memory" | "redis" | "postgres" | "rebuild"
)

# ── LLM ───────────────────────────────────────────────────────────────────────

LLM_TOKENS_TOTAL = Counter(
    "devpulse_llm_tokens_total",
    "Anthropic tokens consumed",
    ["type"],  # "prompt" | "completion"
)

LLM_LATENCY_SECONDS = Histogram(
    "devpulse_llm_latency_seconds",
    "LLM end-to-end latency in seconds",
    buckets=[1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0],
)

LLM_COST_USD_TOTAL = Counter(
    "devpulse_llm_cost_usd_total",
    "Estimated LLM cost in USD (claude-sonnet-4-6 pricing)",
)

AI_TASKS_TOTAL = Counter(
    "devpulse_ai_tasks_total",
    "Total AI tasks processed",
    ["status"],  # "success" | "failed"
)

# ── Guardrails ────────────────────────────────────────────────────────────────

GUARDRAIL_BLOCKED_TOTAL = Counter(
    "devpulse_guardrail_blocked_total",
    "Requests blocked by guardrails",
    ["reason"],  # "length" | "prompt_injection"
)

# ── Kafka ─────────────────────────────────────────────────────────────────────

KAFKA_MESSAGES_CONSUMED_TOTAL = Counter(
    "devpulse_kafka_messages_consumed_total",
    "Total Kafka messages consumed",
    ["topic", "status"],  # status: "success" | "error"
)

KAFKA_CONSUMER_LAG = Gauge(
    "devpulse_kafka_consumer_lag",
    "Kafka consumer lag by topic and partition",
    ["topic", "partition"],
)
