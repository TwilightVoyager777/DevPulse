import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { WorkspaceCard } from "@/components/workspace/WorkspaceCard";
import { Workspace } from "@/lib/types";

// Mock next/link
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockWorkspace: Workspace = {
  id: "ws-1",
  name: "My Workspace",
  ownerId: "user-1",
  createdAt: "2026-01-01T00:00:00Z",
};

describe("WorkspaceCard", () => {
  it("renders workspace name and link", () => {
    render(<WorkspaceCard workspace={mockWorkspace} onDelete={vi.fn()} />);
    expect(screen.getByText("My Workspace")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/workspaces/ws-1");
  });

  it("calls onDelete with workspace id when Delete is clicked", () => {
    const onDelete = vi.fn();
    render(<WorkspaceCard workspace={mockWorkspace} onDelete={onDelete} />);
    fireEvent.click(screen.getByRole("button", { name: /delete/i }));
    expect(onDelete).toHaveBeenCalledWith("ws-1");
  });

  it("renders created date", () => {
    render(<WorkspaceCard workspace={mockWorkspace} onDelete={vi.fn()} />);
    expect(screen.getByText(/created/i)).toBeInTheDocument();
  });
});
