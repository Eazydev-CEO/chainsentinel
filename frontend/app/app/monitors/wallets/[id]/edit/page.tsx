"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import WalletMonitorForm from "@/components/monitors/WalletMonitorForm";
import { BlockSkeleton } from "@/components/ui/Skeletons";
import { useWorkspace } from "@/lib/workspace-context";
import { walletMonitorService } from "@/services/monitors";
import type { WalletMonitor } from "@/types";

export default function EditWalletMonitorPage() {
  const { id } = useParams<{ id: string }>();
  const { current } = useWorkspace();
  const [monitor, setMonitor] = useState<WalletMonitor | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!current) return;
    walletMonitorService
      .get(Number(id))
      .then(setMonitor)
      .catch((err) => setError(err instanceof Error ? err.message : "Not found"));
  }, [id, current]);

  if (error) return <div className="alert alert-danger">{error}</div>;

  return (
    <div style={{ maxWidth: 860 }}>
      <PageHeader title="Edit wallet monitor" subtitle={monitor ? monitor.name : ""} />
      {monitor ? <WalletMonitorForm monitor={monitor} /> : <BlockSkeleton height={420} />}
    </div>
  );
}
