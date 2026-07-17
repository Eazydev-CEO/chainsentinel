import Link from "next/link";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="hero-gradient min-vh-100 d-flex flex-column">
      <div className="container py-4">
        <Link href="/" className="fw-bold fs-5 text-body">
          ⛓ Chain<span style={{ color: "var(--cs-accent)" }}>Sentinel</span>
        </Link>
      </div>
      <div className="flex-grow-1 d-flex align-items-center justify-content-center px-3 pb-5">
        <div className="w-100" style={{ maxWidth: 460 }}>
          {children}
        </div>
      </div>
    </div>
  );
}
