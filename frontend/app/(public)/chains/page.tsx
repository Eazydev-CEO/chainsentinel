import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Supported chains" };

const CHAINS = [
  { name: "Ethereum", symbol: "ETH", confs: 12, block: "~12s", testnet: "Sepolia", explorer: "etherscan.io" },
  { name: "BNB Smart Chain", symbol: "BNB", confs: 15, block: "~3s", testnet: "BSC Testnet", explorer: "bscscan.com" },
  { name: "Polygon", symbol: "POL", confs: 30, block: "~2.1s", testnet: "Amoy", explorer: "polygonscan.com" },
  { name: "Base", symbol: "ETH", confs: 12, block: "~2s", testnet: "Base Sepolia", explorer: "basescan.org" },
  { name: "Arbitrum One", symbol: "ETH", confs: 20, block: "~0.3s", testnet: "Arbitrum Sepolia", explorer: "arbiscan.io" },
  { name: "Optimism", symbol: "ETH", confs: 12, block: "~2s", testnet: "OP Sepolia", explorer: "optimistic.etherscan.io" },
];

export default function ChainsPage() {
  return (
    <div className="container py-5">
      <div className="text-center mb-5">
        <span className="section-eyebrow">Networks</span>
        <h1 className="fw-bold mt-2">Supported EVM chains</h1>
        <p className="text-secondary mx-auto" style={{ maxWidth: 640 }}>
          Every chain ships with sensible default confirmation counts (override them per
          monitor), a matching testnet for development, and explorer deep-links on every event.
        </p>
      </div>

      <div className="row g-4 mb-5">
        {CHAINS.map((chain) => (
          <div className="col-md-6 col-lg-4" key={chain.name}>
            <div className="cs-card p-4 h-100">
              <div className="d-flex align-items-center gap-2 mb-3">
                <span className="status-dot dot-green" aria-hidden="true" />
                <h5 className="fw-semibold mb-0">{chain.name}</h5>
              </div>
              <dl className="row small mb-0 text-secondary">
                <dt className="col-7 fw-normal">Native currency</dt>
                <dd className="col-5 text-end text-body">{chain.symbol}</dd>
                <dt className="col-7 fw-normal">Default confirmations</dt>
                <dd className="col-5 text-end text-body">{chain.confs}</dd>
                <dt className="col-7 fw-normal">Block time</dt>
                <dd className="col-5 text-end text-body">{chain.block}</dd>
                <dt className="col-7 fw-normal">Dev testnet</dt>
                <dd className="col-5 text-end text-body">{chain.testnet}</dd>
                <dt className="col-7 fw-normal">Explorer</dt>
                <dd className="col-5 text-end text-body">{chain.explorer}</dd>
              </dl>
            </div>
          </div>
        ))}
      </div>

      <div className="cs-card p-4 mb-5">
        <h5 className="fw-semibold">Bring your own RPC</h5>
        <p className="text-secondary small mb-0">
          ChainSentinel connects through RPC providers you configure — Alchemy, Infura, Ankr,
          QuickNode or your own nodes. Providers are prioritized per chain; health checks,
          rate-limit awareness and exponential-backoff failover keep ingestion running when a
          provider degrades. Mainnet chains are disabled by default until you deliberately
          enable them with real endpoints.
        </p>
      </div>

      <div className="text-center">
        <Link href="/register" className="btn btn-primary btn-lg px-5">
          Start monitoring →
        </Link>
      </div>
    </div>
  );
}
