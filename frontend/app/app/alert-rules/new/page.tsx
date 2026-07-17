import PageHeader from "@/components/app/PageHeader";
import AlertRuleForm from "@/components/alerts/AlertRuleForm";

export default function NewAlertRulePage() {
  return (
    <div style={{ maxWidth: 960 }}>
      <PageHeader title="New alert rule" subtitle="Evaluated against every confirmed event in this workspace." />
      <AlertRuleForm />
    </div>
  );
}
