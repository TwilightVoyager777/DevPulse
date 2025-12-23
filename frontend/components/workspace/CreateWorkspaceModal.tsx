"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

interface CreateWorkspaceModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string) => Promise<void>;
}

export function CreateWorkspaceModal({ open, onClose, onCreate }: CreateWorkspaceModalProps) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError("");
    setLoading(true);
    try {
      await onCreate(name.trim());
      setName("");
      onClose();
    } catch {
      setError("Failed to create workspace.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="New Workspace">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          id="ws-name"
          label="Workspace name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="My Project"
          autoFocus
          required
        />
        {error && <p className="text-sm text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={loading}>
            Create
          </Button>
        </div>
      </form>
    </Modal>
  );
}
