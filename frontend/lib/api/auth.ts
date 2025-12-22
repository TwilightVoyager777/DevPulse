import { apiClient } from "./client";
import { AuthResponse } from "@/lib/types";

export const register = (email: string, password: string, displayName: string) =>
  apiClient.post<AuthResponse>("/api/auth/register", { email, password, displayName });

export const login = (email: string, password: string) =>
  apiClient.post<AuthResponse>("/api/auth/login", { email, password });

export const logout = (refreshToken: string) =>
  apiClient.post("/api/auth/logout", { refreshToken });

export const refreshToken = (token: string) =>
  apiClient.post<AuthResponse>("/api/auth/refresh", { refreshToken: token });
