"use client";

import { useEffect, useRef } from "react";
import { Message } from "@/lib/types";
import { StreamingMessage } from "./StreamingMessage";
import { cn } from "@/lib/cn";

interface MessageListProps {
  messages: Message[];
  streamingContent: string;
}

export function MessageList({ messages, streamingContent }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
      {messages.length === 0 && !streamingContent && (
        <div className="flex flex-1 items-center justify-center text-gray-600">
          Ask anything about your documents
        </div>
      )}

      {messages.map((msg) => (
        <div
          key={msg.id}
          className={cn("flex gap-3", msg.role === "user" && "flex-row-reverse")}
        >
          <div
            className={cn(
              "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold",
              msg.role === "user"
                ? "bg-gray-700 text-gray-300"
                : "bg-brand-600 text-white"
            )}
          >
            {msg.role === "user" ? "U" : "AI"}
          </div>
          <div
            className={cn(
              "max-w-[75%] rounded-xl px-4 py-3 text-sm",
              msg.role === "user"
                ? "bg-gray-700 text-gray-100"
                : "bg-gray-800 text-gray-100"
            )}
          >
            <p className="whitespace-pre-wrap">{msg.content}</p>
            {msg.sources && msg.sources.length > 0 && (
              <div className="mt-2 border-t border-gray-700 pt-2">
                <p className="text-xs text-gray-500 mb-1">Sources:</p>
                {msg.sources.map((s, i) => (
                  <p key={i} className="text-xs text-gray-400">
                    [{i + 1}] {s.title} — {s.snippet.slice(0, 80)}...
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}

      {streamingContent && <StreamingMessage content={streamingContent} />}
      <div ref={bottomRef} />
    </div>
  );
}
