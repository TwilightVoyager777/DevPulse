import { apiClient } from "./client";
import { ChatSession } from "@/lib/types";

export const listSessions = (workspaceId: string) =>
  apiClient.get<ChatSession[]>(`/api/workspaces/${workspaceId}/sessions`);

export const createSession = (workspaceId: string, title?: string) =>
  apiClient.post<ChatSession>(`/api/workspaces/${workspaceId}/sessions`, {
    title: title ?? "New Chat",
  });

export const deleteSession = (workspaceId: string, sessionId: string) =>
  apiClient.delete(`/api/workspaces/${workspaceId}/sessions/${sessionId}`);
