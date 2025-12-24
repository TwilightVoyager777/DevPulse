"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

interface ImportSoModalProps {
  open: boolean;
  onClose: () => void;
  onImport: (url: string) => Promise<void>;
}

export function ImportSoModal({ open, onClose, onImport }: ImportSoModalProps) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setError("");
    setLoading(true);
    try {
      await onImport(url.trim());
      setUrl("");
      onClose();
    } catch {
      setError("Failed to import. Please check the URL.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Import from Stack Overflow">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          id="so-url"
          label="Stack Overflow question URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://stackoverflow.com/questions/..."
          type="url"
          autoFocus
          required
        />
        {error && <p className="text-sm text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={loading}>
            Import
          </Button>
        </div>
      </form>
    </Modal>
  );
}
