import PageHeader from "@/components/app/PageHeader";
import WalletMonitorForm from "@/components/monitors/WalletMonitorForm";

export default function NewWalletMonitorPage() {
  return (
    <div style={{ maxWidth: 860 }}>
      <PageHeader title="New wallet monitor" subtitle="Validated, checksummed, duplicate-checked." />
      <WalletMonitorForm />
    </div>
  );
}
