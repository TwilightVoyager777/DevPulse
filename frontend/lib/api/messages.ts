import { apiClient } from "./client";
import { Message, SendMessageResponse } from "@/lib/types";

export const listMessages = (workspaceId: string, sessionId: string) =>
  apiClient.get<Message[]>(`/api/workspaces/${workspaceId}/sessions/${sessionId}/messages`);

export const sendMessage = (workspaceId: string, sessionId: string, content: string) =>
  apiClient.post<SendMessageResponse>(
    `/api/workspaces/${workspaceId}/sessions/${sessionId}/messages`,
    { content }
  );
