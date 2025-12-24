"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SseChunk } from "@/lib/types";
import { getAccessToken } from "@/lib/auth-tokens";

interface UseSseOptions {
  workspaceId: string;
  sessionId: string;
  taskId: string | null;
  onChunk: (chunk: SseChunk) => void;
  onDone: (chunk: SseChunk) => void;
  onError: (msg: string) => void;
}

export function useSse({ workspaceId, sessionId, taskId, onChunk, onDone, onError }: UseSseOptions) {
  const [streaming, setStreaming] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!taskId || !sessionId) return;

    // Close any existing connection
    if (esRef.current) {
      esRef.current.close();
    }

    const token = getAccessToken();
    const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
    const url = `${BASE}/api/workspaces/${workspaceId}/sessions/${sessionId}/stream?taskId=${taskId}&token=${token}`;

    const es = new EventSource(url);
    esRef.current = es;
    setStreaming(true);

    es.onmessage = (event) => {
      try {
        const data: SseChunk = JSON.parse(event.data);
        if (data.isDone) {
          onDone(data);
          es.close();
          esRef.current = null;
          setStreaming(false);
        } else {
          onChunk(data);
        }
      } catch (e) {
        console.error("SSE parse error:", e);
      }
    };

    es.onerror = () => {
      onError("Connection lost. Please try again.");
      es.close();
      esRef.current = null;
      setStreaming(false);
    };
  }, [workspaceId, sessionId, taskId, onChunk, onDone, onError]);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
    };
  }, [connect]);

  return { streaming };
}
