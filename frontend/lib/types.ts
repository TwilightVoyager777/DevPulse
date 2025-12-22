export interface User {
  id: string;
  email: string;
  displayName: string;
  role: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
  user: User;
}

export interface Workspace {
  id: string;
  name: string;
  ownerId: string;
  createdAt: string;
}

export type DocumentStatus = "PENDING" | "PROCESSING" | "INDEXED" | "FAILED";

export interface Document {
  id: string;
  workspaceId: string;
  title: string;
  sourceType: string;
  status: DocumentStatus;
  chunkCount: number | null;
  errorMessage: string | null;
  createdAt: string;
  indexedAt: string | null;
}

export interface ChatSession {
  id: string;
  workspaceId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface Message {
  id: string;
  sessionId: string;
  role: "user" | "assistant";
  content: string;
  sources: SourceInfo[] | null;
  createdAt: string;
}

export interface SourceInfo {
  title: string;
  score: number;
  snippet: string;
  documentId: string;
}

export interface Task {
  id: string;
  status: "PENDING" | "PROCESSING" | "DONE" | "FAILED";
  payload: string | null;
}

export interface SendMessageResponse {
  taskId: string;
  messageId: string;
}

export interface SseChunk {
  taskId: string;
  sessionId: string;
  workspaceId: string;
  status: "streaming" | "done" | "failed";
  chunk: string | null;
  isDone: boolean;
  fullResponse: string | null;
  sources: SourceInfo[] | null;
  tokensUsed: number | null;
  latencyMs: number | null;
  errorMessage: string | null;
}
