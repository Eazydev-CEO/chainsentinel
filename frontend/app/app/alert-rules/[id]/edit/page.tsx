"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import AlertRuleForm from "@/components/alerts/AlertRuleForm";
import { BlockSkeleton } from "@/components/ui/Skeletons";
import { useWorkspace } from "@/lib/workspace-context";
import { alertRuleService } from "@/services/platform";
import type { AlertRule } from "@/types";

export default function EditAlertRulePage() {
  const { id } = useParams<{ id: string }>();
  const { current } = useWorkspace();
  const [rule, setRule] = useState<AlertRule | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!current) return;
    alertRuleService
      .get(Number(id))
      .then(setRule)
      .catch((err) => setError(err instanceof Error ? err.message : "Not found"));
  }, [id, current]);

  if (error) return <div className="alert alert-danger">{error}</div>;

  return (
    <div style={{ maxWidth: 960 }}>
      <PageHeader title="Edit alert rule" subtitle={rule?.name || ""} />
      {rule ? <AlertRuleForm rule={rule} /> : <BlockSkeleton height={420} />}
    </div>
  );
}
