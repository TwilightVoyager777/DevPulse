"use client";

import { ChatSession } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

interface SessionSidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelect: (session: ChatSession) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onCreate,
  onDelete,
}: SessionSidebarProps) {
  return (
    <div className="flex w-56 shrink-0 flex-col border-r border-gray-800 bg-gray-900">
      <div className="p-3">
        <Button variant="secondary" size="sm" className="w-full" onClick={onCreate}>
          + New chat
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={cn(
              "group flex cursor-pointer items-center justify-between px-3 py-2 text-sm",
              activeSessionId === s.id
                ? "bg-gray-800 text-white"
                : "text-gray-400 hover:bg-gray-800/50 hover:text-gray-200"
            )}
            onClick={() => onSelect(s)}
          >
            <span className="truncate">{s.title}</span>
            <button
              className="invisible ml-1 text-gray-600 hover:text-red-400 group-hover:visible"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(s.id);
              }}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
