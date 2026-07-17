"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Workspace } from "@/types";
import { api, setWorkspaceIdProvider } from "./api";
import { useAuth } from "./auth-context";

const STORAGE_KEY = "cs:workspace-id"; // non-sensitive: an integer id only

interface WorkspaceState {
  workspaces: Workspace[];
  current: Workspace | null;
  loading: boolean;
  switchWorkspace: (id: number) => void;
  reloadWorkspaces: () => Promise<void>;
  role: Workspace["role"];
  canWrite: boolean;
  isOwner: boolean;
}

const WorkspaceContext = createContext<WorkspaceState>({
  workspaces: [],
  current: null,
  loading: true,
  switchWorkspace: () => {},
  reloadWorkspaces: async () => {},
  role: null,
  canWrite: false,
  isOwner: false,
});

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const reloadWorkspaces = useCallback(async () => {
    if (!user) {
      setWorkspaces([]);
      setCurrentId(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const list = await api.get<Workspace[] | { results: Workspace[] }>("/api/v1/workspaces/");
      const items = Array.isArray(list) ? list : list.results;
      setWorkspaces(items);
      const stored = Number(localStorage.getItem(STORAGE_KEY));
      const preferred = items.find((w) => w.id === stored) || items[0] || null;
      setCurrentId(preferred ? preferred.id : null);
    } catch {
      setWorkspaces([]);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void reloadWorkspaces();
  }, [reloadWorkspaces]);

  // The api client pulls the workspace header through this provider.
  useEffect(() => {
    setWorkspaceIdProvider(() => currentId);
    if (currentId) localStorage.setItem(STORAGE_KEY, String(currentId));
  }, [currentId]);

  const switchWorkspace = useCallback((id: number) => {
    setCurrentId(id);
    localStorage.setItem(STORAGE_KEY, String(id));
  }, []);

  const current = useMemo(
    () => workspaces.find((w) => w.id === currentId) || null,
    [workspaces, currentId]
  );
  const role = current?.role ?? null;

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        current,
        loading,
        switchWorkspace,
        reloadWorkspaces,
        role,
        canWrite: role === "owner" || role === "admin",
        isOwner: role === "owner",
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceState {
  return useContext(WorkspaceContext);
}
