import PageHeader from "@/components/app/PageHeader";
import ContractMonitorForm from "@/components/monitors/ContractMonitorForm";

export default function NewContractMonitorPage() {
  return (
    <div style={{ maxWidth: 920 }}>
      <PageHeader
        title="New contract monitor"
        subtitle="Paste an ABI — events are extracted, validated and topic-hashed for you."
      />
      <ContractMonitorForm />
    </div>
  );
}
