"use client";

import React, { createContext, useCallback, useEffect, useState } from "react";
import { User } from "@/lib/types";
import * as authApi from "@/lib/api/auth";
import { setTokens, clearTokens, getAccessToken } from "@/lib/auth-tokens";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => {},
  register: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Restore user from token on mount (parse JWT payload)
    const token = getAccessToken();
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        setUser({
          id: payload.sub,
          email: payload.email ?? "",
          displayName: payload.displayName ?? "",
          role: payload.role ?? "USER",
        });
      } catch {
        clearTokens();
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await authApi.login(email, password);
    setTokens(data.accessToken, data.refreshToken);
    setUser({ id: String(data.userId), email: data.email, displayName: data.displayName, role: "USER" });
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      const { data } = await authApi.register(email, password, displayName);
      setTokens(data.accessToken, data.refreshToken);
      setUser({ id: String(data.userId), email: data.email, displayName: data.displayName, role: "USER" });
    },
    []
  );

  const logout = useCallback(async () => {
    const { getRefreshToken } = await import("@/lib/auth-tokens");
    const rt = getRefreshToken();
    if (rt) {
      try {
        await authApi.logout(rt);
      } catch {
        // ignore logout errors
      }
    }
    clearTokens();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
