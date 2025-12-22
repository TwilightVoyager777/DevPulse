import { apiClient } from "./client";
import { Workspace } from "@/lib/types";

export const listWorkspaces = () =>
  apiClient.get<Workspace[]>("/api/workspaces");

export const createWorkspace = (name: string) =>
  apiClient.post<Workspace>("/api/workspaces", { name });

export const deleteWorkspace = (id: string) =>
  apiClient.delete(`/api/workspaces/${id}`);
