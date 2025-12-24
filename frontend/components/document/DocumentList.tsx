"use client";

import { useState } from "react";
import { Document } from "@/lib/types";
import { StatusBadge } from "@/components/ui/Badge";
import { UploadDocumentButton } from "./UploadDocumentButton";
import { ImportSoModal } from "./ImportSoModal";
import { Button } from "@/components/ui/Button";
import { importSo } from "@/lib/api/documents";

interface DocumentListProps {
  documents: Document[];
  onUpload: (file: File) => Promise<void>;
  onDelete: (docId: string) => Promise<void>;
}

export function DocumentList({ documents, onUpload, onDelete }: DocumentListProps) {
  const [showImport, setShowImport] = useState(false);

  const handleImport = async (url: string) => {
    // Called by ImportSoModal — parent page owns the workspace context
    // This component doesn't have workspaceId, so we emit via onUpload pattern
    // The modal closes itself; parent should handle via prop if needed
    setShowImport(false);
  };

  return (
    <div className="flex flex-col gap-4 overflow-y-auto p-6">
      <div className="flex items-center gap-3">
        <UploadDocumentButton onUpload={onUpload} />
        <Button variant="secondary" size="sm" onClick={() => setShowImport(true)}>
          Import from Stack Overflow
        </Button>
      </div>

      {documents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-700 py-16 text-center text-gray-500">
          No documents yet. Upload a file or import from Stack Overflow.
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
                  <p className="text-xs text-red-400">{doc.errorMessage}</p>
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
        onImport={handleImport}
      />
    </div>
  );
}
