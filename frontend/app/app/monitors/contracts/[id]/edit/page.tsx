"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import ContractMonitorForm from "@/components/monitors/ContractMonitorForm";
import { BlockSkeleton } from "@/components/ui/Skeletons";
import { useWorkspace } from "@/lib/workspace-context";
import { contractMonitorService } from "@/services/monitors";
import type { ContractMonitor } from "@/types";

export default function EditContractMonitorPage() {
  const { id } = useParams<{ id: string }>();
  const { current } = useWorkspace();
  const [monitor, setMonitor] = useState<ContractMonitor | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!current) return;
    contractMonitorService
      .get(Number(id))
      .then(setMonitor)
      .catch((err) => setError(err instanceof Error ? err.message : "Not found"));
  }, [id, current]);

  if (error) return <div className="alert alert-danger">{error}</div>;

  return (
    <div style={{ maxWidth: 920 }}>
      <PageHeader title="Edit contract monitor" subtitle={monitor ? monitor.name : ""} />
      {monitor ? <ContractMonitorForm monitor={monitor} /> : <BlockSkeleton height={420} />}
    </div>
  );
}
