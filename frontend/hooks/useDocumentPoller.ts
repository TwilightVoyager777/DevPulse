"use client";

import { useCallback, useRef } from "react";
import { getDocument } from "@/lib/api/documents";
import { Document } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["INDEXED", "FAILED"]);

/**
 * Polls GET /api/workspaces/{wId}/documents/{docId} every 2s until the
 * document status reaches INDEXED or FAILED, then calls onComplete.
 */
export function useDocumentPoller(workspaceId: string) {
  const timersRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  const startPolling = useCallback(
    (docId: string, onComplete: (doc: Document) => void) => {
      // Don't start duplicate pollers for the same doc
      if (timersRef.current.has(docId)) return;

      const timer = setInterval(async () => {
        try {
          const { data } = await getDocument(workspaceId, docId);
          if (TERMINAL_STATUSES.has(data.status)) {
            clearInterval(timer);
            timersRef.current.delete(docId);
            onComplete(data);
          }
        } catch {
          // ignore transient errors — keep polling
        }
      }, POLL_INTERVAL_MS);

      timersRef.current.set(docId, timer);
    },
    [workspaceId]
  );

  const stopPolling = useCallback((docId: string) => {
    const timer = timersRef.current.get(docId);
    if (timer) {
      clearInterval(timer);
      timersRef.current.delete(docId);
    }
  }, []);

  return { startPolling, stopPolling };
}
