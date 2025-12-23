"use client";

import { Workspace } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import Link from "next/link";

interface WorkspaceCardProps {
  workspace: Workspace;
  onDelete: (id: string) => void;
}

export function WorkspaceCard({ workspace, onDelete }: WorkspaceCardProps) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-gray-800 bg-gray-900 p-5 transition-colors hover:border-gray-700">
      <Link href={`/workspaces/${workspace.id}`} className="flex-1">
        <h3 className="font-semibold text-white hover:text-brand-400 transition-colors">
          {workspace.name}
        </h3>
        <p className="mt-1 text-xs text-gray-500">
          Created {new Date(workspace.createdAt).toLocaleDateString()}
        </p>
      </Link>
      <Button
        variant="ghost"
        size="sm"
        className="text-gray-500 hover:text-red-400"
        onClick={() => onDelete(workspace.id)}
      >
        Delete
      </Button>
    </div>
  );
}
