"use client";

import { AuthProvider } from "@/lib/auth-context";
import { WorkspaceProvider } from "@/lib/workspace-context";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <WorkspaceProvider>{children}</WorkspaceProvider>
    </AuthProvider>
  );
}
