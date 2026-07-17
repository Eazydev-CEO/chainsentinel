/** Display helpers: addresses, amounts (wei → human), dates. */

export function shortAddress(address: string | null | undefined, chars = 6): string {
  if (!address) return "—";
  if (address.length <= chars * 2 + 2) return address;
  return `${address.slice(0, chars + 2)}…${address.slice(-4)}`;
}

export function shortHash(hash: string | null | undefined): string {
  if (!hash) return "—";
  return `${hash.slice(0, 10)}…${hash.slice(-6)}`;
}

/** Format a raw base-unit amount using `decimals` without float loss. */
export function formatUnits(raw: string | null | undefined, decimals: number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") return "—";
  let value: bigint;
  try {
    value = BigInt(raw);
  } catch {
    return raw;
  }
  const d = decimals ?? 18;
  if (d === 0) return value.toLocaleString();
  const base = BigInt(10) ** BigInt(d);
  const whole = value / base;
  const fraction = value % base;
  if (fraction === BigInt(0)) return whole.toLocaleString();
  const fractionStr = fraction.toString().padStart(d, "0").replace(/0+$/, "").slice(0, 6);
  return `${whole.toLocaleString()}.${fractionStr}`;
}

export function formatAmount(event: {
  amount_wei: string | null;
  token_decimals: number | null;
  token_symbol: string;
  event_type: string;
  token_id?: string;
}, nativeSymbol = "ETH"): string {
  if (event.event_type.startsWith("nft")) {
    return event.token_id ? `Token #${event.token_id}` : "NFT";
  }
  if (event.amount_wei === null) return "—";
  if (event.event_type.startsWith("native")) {
    return `${formatUnits(event.amount_wei, 18)} ${nativeSymbol}`;
  }
  const symbol = event.token_symbol || "units";
  if (event.token_decimals === null) return `${event.amount_wei} raw ${symbol}`;
  return `${formatUnits(event.amount_wei, event.token_decimals)} ${symbol}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 0) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(iso);
}

export function eventTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    native_received: "Native received",
    native_sent: "Native sent",
    erc20_received: "ERC-20 received",
    erc20_sent: "ERC-20 sent",
    nft_received: "NFT received",
    nft_sent: "NFT sent",
    approval_created: "Approval created",
    approval_changed: "Approval changed",
    approval_revoked: "Approval revoked",
    approval_for_all: "Approval for all",
    contract_event: "Contract event",
    large_transfer: "Large transfer",
  };
  return labels[type] || type;
}
