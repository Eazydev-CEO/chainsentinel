"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { User } from "@/types";
import { api } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
    workspace_name?: string;
  }) => Promise<User>;
  logout: () => Promise<void>;
  reloadUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  login: async () => {
    throw new Error("AuthProvider missing");
  },
  register: async () => {
    throw new Error("AuthProvider missing");
  },
  logout: async () => {},
  reloadUser: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const reloadUser = useCallback(async () => {
    try {
      const me = await api.get<User>("/api/v1/auth/me/");
      setUser(me);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await api.get<User>("/api/v1/auth/me/");
        if (!cancelled) setUser(me);
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    const onUnauthorized = () => setUser(null);
    window.addEventListener("cs:unauthorized", onUnauthorized);
    return () => {
      cancelled = true;
      window.removeEventListener("cs:unauthorized", onUnauthorized);
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const me = await api.post<User>("/api/v1/auth/login/", { email, password });
    setUser(me);
    return me;
  }, []);

  const register = useCallback(async (payload: Parameters<AuthState["register"]>[0]) => {
    const me = await api.post<User>("/api/v1/auth/register/", payload);
    setUser(me);
    return me;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/v1/auth/logout/");
    } finally {
      setUser(null);
      if (typeof window !== "undefined") window.location.href = "/login";
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, reloadUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
