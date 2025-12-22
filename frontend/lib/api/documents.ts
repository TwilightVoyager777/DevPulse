import { apiClient } from "./client";
import { Document } from "@/lib/types";

export const listDocuments = (workspaceId: string) =>
  apiClient.get<Document[]>(`/api/workspaces/${workspaceId}/documents`);

export const uploadDocument = (workspaceId: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiClient.post<Document>(`/api/workspaces/${workspaceId}/documents`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const importSo = (workspaceId: string, url: string) =>
  apiClient.post<Document>(`/api/workspaces/${workspaceId}/documents/import-so`, { url });

export const deleteDocument = (workspaceId: string, documentId: string) =>
  apiClient.delete(`/api/workspaces/${workspaceId}/documents/${documentId}`);
