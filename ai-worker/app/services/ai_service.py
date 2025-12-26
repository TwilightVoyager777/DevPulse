import logging
import re
import time
from typing import List

import anthropic

from app.config import get_settings
from app.models.schemas import (
    AiTaskEvent,
    TaskStatusEvent,
    SourceInfo,
    ConversationMessage,
)
from app.services.retrieval_service import hybrid_search
from app.utils.kafka_producer import publish_task_status
from app.utils.redis_client import cache_task_status
from app.utils.metrics import (
    AI_TASKS_TOTAL,
    LLM_TOKENS_TOTAL,
    LLM_LATENCY_SECONDS,
    LLM_COST_USD_TOTAL,
    GUARDRAIL_BLOCKED_TOTAL,
)

logger = logging.getLogger(__name__)

# claude-sonnet-4-6 pricing per 1M tokens
_INPUT_COST_PER_TOKEN = 3.0 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000

_MAX_QUERY_CHARS = 2000

_INJECTION_RE = re.compile(
    r"ignore previous instructions|ignore all instructions|you are now|act as"
    r"|jailbreak|\bDAN\b",
    re.IGNORECASE,
)

_SK_ANT_RE = re.compile(r"sk-ant-[A-Za-z0-9\-_]+")

_SYSTEM_TEMPLATE = """\
You are a precise technical Q&A assistant for developers. \
Answer questions based ONLY on the provided context. \
Always cite sources using [source_1], [source_2] notation. \
If the context is insufficient, clearly state what information is missing. \
Be concise and accurate. Prefer code examples when relevant.

Context:
{context}
"""


def _build_messages(
    user_message: str,
    history: List[ConversationMessage],
) -> List[dict]:
    messages = []
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _build_system_prompt(chunks: List[dict]) -> str:
    if not chunks:
        return (
            "You are a precise technical Q&A assistant for developers. "
            "No context documents are available; answer based on your training knowledge."
        )
    context_parts = []
    for i, chunk in enumerate(chunks[:5], 1):
        title = chunk.get("title", "Unknown")
        content = chunk["content"][:1000]
        context_parts.append(f"[source_{i}] {title}\n{content}")
    return _SYSTEM_TEMPLATE.format(context="\n\n---\n\n".join(context_parts))


def _failed_event(event: AiTaskEvent, message: str) -> TaskStatusEvent:
    return TaskStatusEvent(
        taskId=event.taskId,
        sessionId=event.sessionId,
        workspaceId=event.workspaceId,
        status="failed",
        isDone=True,
        errorMessage=message,
        userMessageHash=hash(event.userMessage) & 0x7FFFFFFF,
    )


async def process_ai_task(event: AiTaskEvent) -> None:
    """
    Full RAG + LLM pipeline with guardrails and metrics:
    1. Input guardrails (length, prompt injection)
    2. Hybrid retrieval → top-k chunks
    3. Build prompt
    4. Stream Claude response
    5. Output scan (redact secrets)
    6. Publish TaskStatusEvent chunks + final done event
    """
    settings = get_settings()
    start_ms = int(time.time() * 1000)
    task_id_str = str(event.taskId)

    # ── Input guardrails ──────────────────────────────────────────────────────
    if len(event.userMessage) > _MAX_QUERY_CHARS:
        GUARDRAIL_BLOCKED_TOTAL.labels(reason="length").inc()
        publish_task_status(_failed_event(
            event, f"Query exceeds maximum length of {_MAX_QUERY_CHARS} characters."
        ))
        return

    if _INJECTION_RE.search(event.userMessage):
        GUARDRAIL_BLOCKED_TOTAL.labels(reason="prompt_injection").inc()
        logger.warning("Prompt injection attempt blocked for task %s", task_id_str)
        degrade_event = TaskStatusEvent(
            taskId=event.taskId,
            sessionId=event.sessionId,
            workspaceId=event.workspaceId,
            status="done",
            isDone=True,
            fullResponse=(
                "I'm unable to process this request. "
                "Please ask a technical question about your documents."
            ),
            userMessageHash=hash(event.userMessage) & 0x7FFFFFFF,
        )
        publish_task_status(degrade_event)
        return

    # ── 1. Retrieve context ───────────────────────────────────────────────────
    try:
        chunks, sources = await hybrid_search(str(event.workspaceId), event.userMessage)
    except Exception as e:
        logger.error("Retrieval failed for task %s: %s", task_id_str, e)
        chunks, sources = [], []

    # ── 2. Build prompt ───────────────────────────────────────────────────────
    system_prompt = _build_system_prompt(chunks)
    messages = _build_messages(event.userMessage, event.conversationHistory)

    # ── 3. Stream Claude ──────────────────────────────────────────────────────
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    full_response = ""
    input_tokens = 0
    output_tokens = 0

    try:
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_tokens,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                chunk_event = TaskStatusEvent(
                    taskId=event.taskId,
                    sessionId=event.sessionId,
                    workspaceId=event.workspaceId,
                    status="streaming",
                    chunk=text,
                    isDone=False,
                    userMessageHash=hash(event.userMessage) & 0x7FFFFFFF,
                )
                publish_task_status(chunk_event)

            final_msg = await stream.get_final_message()
            input_tokens = final_msg.usage.input_tokens
            output_tokens = final_msg.usage.output_tokens

    except Exception as e:
        logger.error("Anthropic API error for task %s: %s", task_id_str, e)
        AI_TASKS_TOTAL.labels(status="failed").inc()
        publish_task_status(_failed_event(event, str(e)))
        return

    # ── 4. Output scan — redact API keys ─────────────────────────────────────
    full_response = _SK_ANT_RE.sub("[REDACTED]", full_response)

    # ── 5. Metrics ────────────────────────────────────────────────────────────
    latency_ms = int(time.time() * 1000) - start_ms
    LLM_TOKENS_TOTAL.labels(type="prompt").inc(input_tokens)
    LLM_TOKENS_TOTAL.labels(type="completion").inc(output_tokens)
    LLM_LATENCY_SECONDS.observe(latency_ms / 1000)
    LLM_COST_USD_TOTAL.inc(
        input_tokens * _INPUT_COST_PER_TOKEN + output_tokens * _OUTPUT_COST_PER_TOKEN
    )
    AI_TASKS_TOTAL.labels(status="success").inc()

    # ── 6. Publish done event ─────────────────────────────────────────────────
    tokens_used = input_tokens + output_tokens
    done_event = TaskStatusEvent(
        taskId=event.taskId,
        sessionId=event.sessionId,
        workspaceId=event.workspaceId,
        status="done",
        isDone=True,
        fullResponse=full_response,
        sources=sources,
        tokensUsed=tokens_used,
        latencyMs=latency_ms,
        userMessageHash=hash(event.userMessage) & 0x7FFFFFFF,
    )
    publish_task_status(done_event)

    try:
        await cache_task_status(task_id_str, done_event.model_dump_json())
    except Exception as e:
        logger.warning("Failed to cache task status: %s", e)

    logger.info(
        "Task %s completed: %d tokens (%d in / %d out), %d ms, %d sources",
        task_id_str, tokens_used, input_tokens, output_tokens, latency_ms, len(sources),
    )
