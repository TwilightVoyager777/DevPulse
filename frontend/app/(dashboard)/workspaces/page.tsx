"use client";

import { useState } from "react";
import useSWR from "swr";
import { listWorkspaces, createWorkspace, deleteWorkspace } from "@/lib/api/workspaces";
import { WorkspaceCard } from "@/components/workspace/WorkspaceCard";
import { CreateWorkspaceModal } from "@/components/workspace/CreateWorkspaceModal";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { Workspace } from "@/lib/types";

export default function WorkspacesPage() {
  const { data, isLoading, mutate } = useSWR("/workspaces", () =>
    listWorkspaces().then((r) => r.data)
  );
  const [showCreate, setShowCreate] = useState(false);

  const handleCreate = async (name: string) => {
    const { data: ws } = await createWorkspace(name);
    mutate((prev) => (prev ? [...prev, ws] : [ws]), false);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this workspace? All documents and sessions will be removed.")) return;
    await deleteWorkspace(id);
    mutate((prev) => prev?.filter((w: Workspace) => w.id !== id), false);
  };

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Workspaces</h1>
          <p className="mt-1 text-sm text-gray-400">
            Organize your knowledge bases and chat sessions
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>New workspace</Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      ) : data && data.length > 0 ? (
        <div className="flex flex-col gap-3">
          {data.map((ws: Workspace) => (
            <WorkspaceCard key={ws.id} workspace={ws} onDelete={handleDelete} />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-gray-700 py-20 text-center text-gray-500">
          No workspaces yet. Create one to get started.
        </div>
      )}

      <CreateWorkspaceModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreate={handleCreate}
      />
    </div>
  );
}
