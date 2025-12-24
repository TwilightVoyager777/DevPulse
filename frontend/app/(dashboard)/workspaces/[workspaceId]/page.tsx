"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { listSessions, createSession, deleteSession } from "@/lib/api/sessions";
import { listDocuments, uploadDocument, deleteDocument } from "@/lib/api/documents";
import { SessionSidebar } from "@/components/chat/SessionSidebar";
import { MessageList } from "@/components/chat/MessageList";
import { MessageInput } from "@/components/chat/MessageInput";
import { DocumentList } from "@/components/document/DocumentList";
import { Button } from "@/components/ui/Button";
import { useChat } from "@/hooks/useChat";
import { ChatSession, Document } from "@/lib/types";

type Panel = "chat" | "docs";

export default function WorkspacePage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;

  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [panel, setPanel] = useState<Panel>("chat");

  const { data: sessions, mutate: mutateSessions } = useSWR(
    `/sessions/${workspaceId}`,
    () => listSessions(workspaceId).then((r) => r.data)
  );

  const { data: documents, mutate: mutateDocs } = useSWR(
    `/docs/${workspaceId}`,
    () => listDocuments(workspaceId).then((r) => r.data)
  );

  const { messages, streamingContent, sending, streaming, loadMessages, send } =
    useChat(workspaceId, activeSession?.id ?? null);

  // Auto-select first session
  useEffect(() => {
    if (sessions && sessions.length > 0 && !activeSession) {
      setActiveSession(sessions[0]);
    }
  }, [sessions, activeSession]);

  // Load messages when session changes
  useEffect(() => {
    if (activeSession) loadMessages();
  }, [activeSession, loadMessages]);

  const handleCreateSession = async () => {
    const { data: session } = await createSession(workspaceId);
    mutateSessions((prev: ChatSession[] | undefined) =>
      prev ? [session, ...prev] : [session], false
    );
    setActiveSession(session);
  };

  const handleDeleteSession = async (id: string) => {
    await deleteSession(workspaceId, id);
    mutateSessions(
      (prev: ChatSession[] | undefined) => prev?.filter((s) => s.id !== id),
      false
    );
    if (activeSession?.id === id) {
      setActiveSession(null);
    }
  };

  const handleUpload = async (file: File) => {
    const { data: doc } = await uploadDocument(workspaceId, file);
    mutateDocs((prev: Document[] | undefined) => (prev ? [doc, ...prev] : [doc]), false);
  };

  const handleDeleteDoc = async (docId: string) => {
    await deleteDocument(workspaceId, docId);
    mutateDocs(
      (prev: Document[] | undefined) => prev?.filter((d) => d.id !== docId),
      false
    );
  };

  return (
    <div className="flex h-full">
      {/* Session sidebar */}
      <SessionSidebar
        sessions={sessions ?? []}
        activeSessionId={activeSession?.id ?? null}
        onSelect={setActiveSession}
        onCreate={handleCreateSession}
        onDelete={handleDeleteSession}
      />

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Panel toggle */}
        <div className="flex h-10 items-center gap-1 border-b border-gray-800 px-4">
          <button
            className={`rounded px-3 py-1 text-sm ${
              panel === "chat"
                ? "bg-gray-800 text-white"
                : "text-gray-500 hover:text-gray-300"
            }`}
            onClick={() => setPanel("chat")}
          >
            Chat
          </button>
          <button
            className={`rounded px-3 py-1 text-sm ${
              panel === "docs"
                ? "bg-gray-800 text-white"
                : "text-gray-500 hover:text-gray-300"
            }`}
            onClick={() => setPanel("docs")}
          >
            Documents ({documents?.length ?? 0})
          </button>
        </div>

        {panel === "chat" ? (
          activeSession ? (
            <div className="flex flex-1 flex-col overflow-hidden">
              <MessageList messages={messages} streamingContent={streamingContent} />
              <MessageInput onSend={send} disabled={sending || streaming} />
            </div>
          ) : (
            <div className="flex flex-1 items-center justify-center text-gray-600">
              <div className="text-center">
                <p className="mb-4">No sessions yet</p>
                <Button onClick={handleCreateSession}>Start a chat</Button>
              </div>
            </div>
          )
        ) : (
          <DocumentList
            documents={documents ?? []}
            onUpload={handleUpload}
            onDelete={handleDeleteDoc}
          />
        )}
      </div>
    </div>
  );
}
