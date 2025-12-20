import logging
import time
from typing import List, AsyncIterator

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

logger = logging.getLogger(__name__)

_SYSTEM_TEMPLATE = """\
You are DevPulse, an expert AI assistant for software developers.
Answer questions based on the provided context documents.
If the context does not contain enough information, say so clearly.
Always cite relevant information from the context.

Context documents:
{context}
"""


def _build_messages(
    user_message: str,
    history: List[ConversationMessage],
) -> List[dict]:
    """Build Anthropic messages list from conversation history + new message."""
    messages = []
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _build_system_prompt(chunks: List[dict]) -> str:
    if not chunks:
        return "You are DevPulse, an expert AI assistant for software developers. Answer based on your training knowledge."
    context_parts = []
    for i, chunk in enumerate(chunks[:5], 1):
        title = chunk.get("title", "Unknown")
        content = chunk["content"][:1000]  # limit per-chunk context
        context_parts.append(f"[{i}] {title}\n{content}")
    context = "\n\n---\n\n".join(context_parts)
    return _SYSTEM_TEMPLATE.format(context=context)


async def process_ai_task(event: AiTaskEvent) -> None:
    """
    Full RAG + LLM pipeline:
    1. Hybrid retrieval → top-k chunks
    2. Build prompt
    3. Stream Claude response
    4. Publish TaskStatusEvent chunks + final done event
    """
    settings = get_settings()
    start_ms = int(time.time() * 1000)
    task_id_str = str(event.taskId)

    # 1. Retrieve context
    try:
        chunks, sources = await hybrid_search(
            str(event.workspaceId), event.userMessage
        )
    except Exception as e:
        logger.error("Retrieval failed for task %s: %s", task_id_str, e)
        chunks, sources = [], []

    # 2. Build prompt
    system_prompt = _build_system_prompt(chunks)
    messages = _build_messages(event.userMessage, event.conversationHistory)

    # 3. Stream Claude
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    full_response = ""
    tokens_used = None

    try:
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_tokens,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                # Publish streaming chunk
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

            # Get final usage
            final_msg = await stream.get_final_message()
            tokens_used = final_msg.usage.input_tokens + final_msg.usage.output_tokens

    except Exception as e:
        logger.error("Anthropic API error for task %s: %s", task_id_str, e)
        error_event = TaskStatusEvent(
            taskId=event.taskId,
            sessionId=event.sessionId,
            workspaceId=event.workspaceId,
            status="failed",
            isDone=True,
            errorMessage=str(e),
            userMessageHash=hash(event.userMessage) & 0x7FFFFFFF,
        )
        publish_task_status(error_event)
        return

    # 4. Publish done event
    latency_ms = int(time.time() * 1000) - start_ms
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

    # Cache the response for circuit breaker fallback
    try:
        status_json = done_event.model_dump_json()
        await cache_task_status(task_id_str, status_json)
    except Exception as e:
        logger.warning("Failed to cache task status: %s", e)

    logger.info(
        "Task %s completed: %d tokens, %d ms, %d sources",
        task_id_str, tokens_used or 0, latency_ms, len(sources),
    )
