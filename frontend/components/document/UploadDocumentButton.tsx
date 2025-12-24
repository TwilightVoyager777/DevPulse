"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";

interface UploadDocumentButtonProps {
  onUpload: (file: File) => Promise<void>;
}

export function UploadDocumentButton({ onUpload }: UploadDocumentButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      await onUpload(file);
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".txt,.md,.pdf"
        className="hidden"
        onChange={handleChange}
      />
      <Button
        variant="primary"
        size="sm"
        loading={loading}
        onClick={() => inputRef.current?.click()}
      >
        Upload document
      </Button>
    </>
  );
}
