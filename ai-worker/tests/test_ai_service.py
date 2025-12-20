import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import AiTaskEvent, ConversationMessage
from app.services.ai_service import _build_messages, _build_system_prompt


def make_event(**kwargs):
    defaults = dict(
        taskId=uuid.uuid4(),
        sessionId=uuid.uuid4(),
        workspaceId=uuid.uuid4(),
        userMessage="What is Python GIL?",
        conversationHistory=[],
        createdAt=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return AiTaskEvent(**defaults)


def test_build_messages_no_history():
    messages = _build_messages("What is Redis?", [])
    assert messages == [{"role": "user", "content": "What is Redis?"}]


def test_build_messages_with_history():
    history = [
        ConversationMessage(role="user", content="Hi"),
        ConversationMessage(role="assistant", content="Hello!"),
    ]
    messages = _build_messages("What is Redis?", history)
    assert len(messages) == 3
    assert messages[-1] == {"role": "user", "content": "What is Redis?"}
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_build_system_prompt_with_chunks():
    chunks = [
        {"title": "Python Guide", "content": "Python is a programming language.", "id": "c1", "document_id": "d1", "chunk_index": 0},
    ]
    prompt = _build_system_prompt(chunks)
    assert "Python Guide" in prompt
    assert "Python is a programming language." in prompt
    assert "Context documents" in prompt


def test_build_system_prompt_no_chunks():
    prompt = _build_system_prompt([])
    assert "training knowledge" in prompt


@pytest.mark.asyncio
async def test_process_ai_task_publishes_done_event(mocker):
    event = make_event()

    # Mock retrieval
    mocker.patch(
        "app.services.ai_service.hybrid_search",
        return_value=([], []),
    )

    # Mock Anthropic streaming
    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)

    async def fake_text_stream():
        for token in ["Paris ", "is ", "the ", "answer."]:
            yield token

    mock_stream.text_stream = fake_text_stream()
    mock_final = MagicMock()
    mock_final.usage.input_tokens = 50
    mock_final.usage.output_tokens = 20
    mock_stream.get_final_message = AsyncMock(return_value=mock_final)

    mock_client = AsyncMock()
    mock_client.messages.stream.return_value = mock_stream

    mocker.patch("app.services.ai_service.anthropic.AsyncAnthropic", return_value=mock_client)

    published = []
    mocker.patch(
        "app.services.ai_service.publish_task_status",
        side_effect=lambda e: published.append(e),
    )
    mocker.patch("app.services.ai_service.cache_task_status", new_callable=AsyncMock)

    from app.services.ai_service import process_ai_task
    await process_ai_task(event)

    # Should have streaming chunks + 1 done event
    assert len(published) >= 2
    done_events = [e for e in published if e.isDone]
    assert len(done_events) == 1
    assert done_events[0].status == "done"
    assert "Paris" in done_events[0].fullResponse
    assert done_events[0].tokensUsed == 70


@pytest.mark.asyncio
async def test_process_ai_task_handles_api_error(mocker):
    event = make_event()
    mocker.patch("app.services.ai_service.hybrid_search", return_value=([], []))

    mock_client = AsyncMock()
    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(side_effect=Exception("API Error"))
    mock_client.messages.stream.return_value = mock_stream
    mocker.patch("app.services.ai_service.anthropic.AsyncAnthropic", return_value=mock_client)

    published = []
    mocker.patch("app.services.ai_service.publish_task_status", side_effect=lambda e: published.append(e))

    from app.services.ai_service import process_ai_task
    await process_ai_task(event)

    failed = [e for e in published if e.status == "failed"]
    assert len(failed) == 1
