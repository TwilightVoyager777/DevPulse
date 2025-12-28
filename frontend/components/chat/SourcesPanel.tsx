"use client";

import { useState } from "react";
import { SourceInfo } from "@/lib/types";
import { cn } from "@/lib/cn";

interface SourcesPanelProps {
  sources: SourceInfo[];
  isOpen: boolean;
  onToggle: () => void;
}

export function SourcesPanel({ sources, isOpen, onToggle }: SourcesPanelProps) {
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <div
      className={cn(
        "flex flex-col border-l border-gray-800 bg-gray-900 transition-all duration-200",
        isOpen ? "w-[280px]" : "w-8"
      )}
    >
      {/* Toggle button */}
      <button
        onClick={onToggle}
        className="flex h-10 w-full items-center justify-center border-b border-gray-800 text-gray-500 hover:text-gray-300"
        title={isOpen ? "Collapse sources" : "Expand sources"}
      >
        <span className="text-xs font-mono">
          {isOpen ? "›" : "‹"}
        </span>
      </button>

      {isOpen && (
        <div className="flex flex-col overflow-y-auto p-3 gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-500 mb-1">
            Sources {sources.length > 0 && `(${sources.length})`}
          </p>

          {sources.length === 0 ? (
            <p className="text-xs text-gray-600 text-center py-4">
              No sources yet
            </p>
          ) : (
            sources.map((source, i) => (
              <div
                key={i}
                className="rounded-lg border border-gray-700 bg-gray-800 p-2.5 cursor-pointer hover:border-cyan-800 transition-colors"
                onClick={() => setExpanded(expanded === i ? null : i)}
              >
                <div className="flex items-start justify-between gap-1">
                  <p className="text-xs font-medium text-gray-300 line-clamp-1">
                    [{i + 1}] {source.title}
                  </p>
                  <span className="shrink-0 rounded bg-cyan-900/40 px-1 py-0.5 text-[10px] text-cyan-400">
                    {source.score.toFixed(3)}
                  </span>
                </div>
                <p className={cn(
                  "mt-1 text-[11px] text-gray-500",
                  expanded === i ? "" : "line-clamp-2"
                )}>
                  {expanded === i ? source.snippet : source.snippet.slice(0, 150)}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
