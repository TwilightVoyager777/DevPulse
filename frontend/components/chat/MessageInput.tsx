"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";

interface MessageInputProps {
  onSend: (content: string) => void;
  disabled: boolean;
}

export function MessageInput({ onSend, disabled }: MessageInputProps) {
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
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-3 border-t border-gray-800 bg-gray-950 p-4"
    >
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? "AI is responding..." : "Ask a question… (Enter to send)"}
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
  );
}
