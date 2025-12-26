"use client";

import { useCallback, useRef, useState } from "react";
import { Message, SseChunk } from "@/lib/types";
import { listMessages, sendMessage } from "@/lib/api/messages";
import { getAccessToken } from "@/lib/auth-tokens";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export function useChat(workspaceId: string, sessionId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const streamingContentRef = useRef("");

  const loadMessages = useCallback(async () => {
    if (!sessionId) return;
    const { data } = await listMessages(workspaceId, sessionId);
    setMessages(data);
    setStreamingContent("");
    streamingContentRef.current = "";
    setTaskId(null);
  }, [workspaceId, sessionId]);

  const send = useCallback(
    async (content: string) => {
      if (!sessionId || sending || streaming) return;

      // Optimistically append user message
      const tempUserMsg: Message = {
        id: crypto.randomUUID(),
        sessionId,
        role: "user",
        content,
        sources: null,
        tokensUsed: null,
        latencyMs: null,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempUserMsg]);
      setSending(true);
      setStreamingContent("");
      streamingContentRef.current = "";

      try {
        const { data } = await sendMessage(workspaceId, sessionId, content);
        const newTaskId = data.taskId;
        setTaskId(newTaskId);
        setSending(false);
        setStreaming(true);

        // Open SSE connection
        if (esRef.current) esRef.current.close();
        const token = getAccessToken();
        const url = `${BASE}/api/workspaces/${workspaceId}/sessions/${sessionId}/stream?taskId=${newTaskId}&token=${token}`;
        const es = new EventSource(url);
        esRef.current = es;

        es.onmessage = (event) => {
          try {
            const chunk: SseChunk = JSON.parse(event.data);
            if (chunk.isDone) {
              const finalContent = chunk.fullResponse ?? streamingContentRef.current;
              const assistantMsg: Message = {
                id: crypto.randomUUID(),
                sessionId,
                role: "assistant",
                content: finalContent,
                sources: chunk.sources ?? null,
                tokensUsed: chunk.tokensUsed ?? null,
                latencyMs: chunk.latencyMs ?? null,
                createdAt: new Date().toISOString(),
              };
              setMessages((prev) => [...prev, assistantMsg]);
              setStreamingContent("");
              streamingContentRef.current = "";
              setStreaming(false);
              setTaskId(null);
              es.close();
              esRef.current = null;
            } else if (chunk.chunk) {
              streamingContentRef.current += chunk.chunk;
              setStreamingContent(streamingContentRef.current);
            }
          } catch (e) {
            console.error("SSE parse error:", e);
          }
        };

        es.onerror = () => {
          setStreaming(false);
          setStreamingContent("");
          streamingContentRef.current = "";
          es.close();
          esRef.current = null;
        };
      } catch {
        setSending(false);
        setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
      }
    },
    [workspaceId, sessionId, sending, streaming]
  );

  return {
    messages,
    streamingContent,
    taskId,
    sending,
    streaming,
    loadMessages,
    send,
  };
}
