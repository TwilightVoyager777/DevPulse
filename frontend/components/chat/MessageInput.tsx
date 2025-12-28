"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";

interface MessageInputProps {
  onSend: (content: string) => void;
  onRetry?: () => void;
  disabled: boolean;
  error?: string | null;
}

export function MessageInput({ onSend, onRetry, disabled, error }: MessageInputProps) {
  const [content, setContent] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = content.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setContent("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  return (
    <div className="border-t border-gray-800 bg-gray-950">
      {error && (
        <div className="flex items-center gap-3 px-4 py-2 text-sm text-red-400">
          <span>{error}</span>
          {onRetry && (
            <button
              onClick={onRetry}
              className="rounded px-2 py-0.5 text-xs text-amber-400 hover:text-amber-300 border border-amber-800 hover:border-amber-600 transition-colors"
            >
              Retry
            </button>
          )}
        </div>
      )}
      <form onSubmit={handleSubmit} className="flex items-end gap-3 p-4">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? "AI is thinking..." : "Ask a question… (Enter to send)"}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-xl border border-gray-700 bg-gray-800 px-4 py-3 text-sm text-gray-100
                     placeholder:text-gray-500 focus:border-brand-500 focus:outline-none
                     disabled:cursor-not-allowed disabled:opacity-50
                     max-h-40 overflow-y-auto"
          style={{ minHeight: "2.75rem" }}
        />
        <Button
          type="submit"
          disabled={disabled || !content.trim()}
          loading={disabled}
          size="md"
        >
          Send
        </Button>
      </form>
    </div>
  );
}
