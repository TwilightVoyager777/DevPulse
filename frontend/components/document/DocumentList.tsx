"use client";

import { useRef, useState } from "react";
import { Document } from "@/lib/types";
import { StatusBadge } from "@/components/ui/Badge";
import { UploadDocumentButton } from "./UploadDocumentButton";
import { ImportSoModal } from "./ImportSoModal";
import { Button } from "@/components/ui/Button";

interface DocumentListProps {
  documents: Document[];
  onUpload: (file: File) => Promise<void>;
  onDelete: (docId: string) => Promise<void>;
  onRetry: (docId: string) => Promise<void>;
  onImportSo: (url: string) => Promise<void>;
}

export function DocumentList({ documents, onUpload, onDelete, onRetry, onImportSo }: DocumentListProps) {
  const [showImport, setShowImport] = useState(false);
  const [dragging, setDragging] = useState(false);
  const dragCounter = useRef(0);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounter.current++;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounter.current--;
    if (dragCounter.current === 0) setDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    dragCounter.current = 0;
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    const allowed = [".txt", ".md", ".pdf"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!allowed.includes(ext)) return;
    await onUpload(file);
  };

  return (
    <div
      className={`relative flex flex-col gap-4 overflow-y-auto p-6 transition-colors ${
        dragging ? "bg-brand-950/40 ring-2 ring-inset ring-brand-600" : ""
      }`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {dragging && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-xl border-2 border-dashed border-brand-500 bg-gray-950/70">
          <p className="text-lg font-medium text-brand-400">Drop file to upload</p>
        </div>
      )}

      <div className="flex items-center gap-3">
        <UploadDocumentButton onUpload={onUpload} />
        <Button variant="secondary" size="sm" onClick={() => setShowImport(true)}>
          Import from Stack Overflow
        </Button>
      </div>

      {documents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-700 py-16 text-center text-gray-500">
          No documents yet. Upload a file, drag &amp; drop here, or import from Stack Overflow.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 px-4 py-3"
            >
              <div className="flex flex-1 flex-col gap-1 min-w-0">
                <span className="truncate text-sm font-medium text-white">{doc.title}</span>
                <div className="flex items-center gap-2">
                  <StatusBadge status={doc.status} />
                  {doc.chunkCount != null && (
                    <span className="text-xs text-gray-500">{doc.chunkCount} chunks</span>
                  )}
                  <span className="text-xs text-gray-600">{doc.sourceType}</span>
                </div>
                {doc.errorMessage && (
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-red-400">{doc.errorMessage}</p>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs text-amber-500 hover:text-amber-300 px-1 py-0 h-auto"
                      onClick={() => onRetry(doc.id)}
                    >
                      Retry
                    </Button>
                  </div>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="ml-3 shrink-0 text-gray-500 hover:text-red-400"
                onClick={() => onDelete(doc.id)}
              >
                Remove
              </Button>
            </div>
          ))}
        </div>
      )}

      <ImportSoModal
        open={showImport}
        onClose={() => setShowImport(false)}
        onImport={onImportSo}
      />
    </div>
  );
}
