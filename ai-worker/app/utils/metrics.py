from prometheus_client import Counter, Histogram, Gauge, Info

# App info gauge
APP_INFO = Info("devpulse_ai_worker", "AI Worker build info")

# Document ingestion
DOCS_INGESTED_TOTAL = Counter(
    "devpulse_docs_ingested_total",
    "Total documents ingested",
    ["status"],  # "success" | "failed"
)

CHUNKS_CREATED_TOTAL = Counter(
    "devpulse_chunks_created_total",
    "Total chunks created during ingestion",
)

INGESTION_DURATION_SECONDS = Histogram(
    "devpulse_ingestion_duration_seconds",
    "Document ingestion duration in seconds",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# AI tasks
AI_TASKS_TOTAL = Counter(
    "devpulse_ai_tasks_total",
    "Total AI tasks processed",
    ["status"],  # "success" | "failed"
)

AI_TASK_DURATION_SECONDS = Histogram(
    "devpulse_ai_task_duration_seconds",
    "AI task end-to-end duration (retrieval + LLM) in seconds",
    buckets=[1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0],
)

TOKENS_USED_TOTAL = Counter(
    "devpulse_tokens_used_total",
    "Total Anthropic tokens consumed",
)

# Retrieval
RETRIEVAL_SOURCES_COUNT = Histogram(
    "devpulse_retrieval_sources_count",
    "Number of sources returned per retrieval",
    buckets=[0, 1, 2, 3, 4, 5, 10],
)

# Kafka
KAFKA_MESSAGES_CONSUMED_TOTAL = Counter(
    "devpulse_kafka_messages_consumed_total",
    "Total Kafka messages consumed",
    ["topic", "status"],  # status: "success" | "error"
)
