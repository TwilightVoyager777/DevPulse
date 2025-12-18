from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class ConversationMessage(BaseModel):
    role: str
    content: str


class DocumentIngestionEvent(BaseModel):
    documentId: uuid.UUID
    workspaceId: uuid.UUID
    sourceType: str          # "UPLOAD" | "SO_IMPORT"
    contentOrPath: str       # raw text content
    metadata: Optional[Dict[str, Any]] = None
    createdAt: datetime


class AiTaskEvent(BaseModel):
    taskId: uuid.UUID
    sessionId: uuid.UUID
    workspaceId: uuid.UUID
    userMessage: str
    conversationHistory: List[ConversationMessage] = Field(default_factory=list)
    createdAt: datetime


class SourceInfo(BaseModel):
    title: str
    score: float
    snippet: str
    documentId: uuid.UUID


class TaskStatusEvent(BaseModel):
    taskId: uuid.UUID
    sessionId: uuid.UUID
    workspaceId: uuid.UUID
    status: str              # "streaming" | "done" | "failed"
    chunk: Optional[str] = None
    isDone: bool = False
    fullResponse: Optional[str] = None
    sources: Optional[List[SourceInfo]] = None
    tokensUsed: Optional[int] = None
    latencyMs: Optional[int] = None
    errorMessage: Optional[str] = None
    userMessageHash: int = 0
