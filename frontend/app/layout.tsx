import type { Metadata } from "next";
import BootstrapClient from "@/components/BootstrapClient";
import Providers from "@/components/Providers";
import "sweetalert2/dist/sweetalert2.min.css";
import "@/styles/globals.scss"; // after sweetalert2 so cs-swal overrides win

export const metadata: Metadata = {
  title: {
    default: "ChainSentinel — Real-time EVM wallet & smart-contract monitoring",
    template: "%s · ChainSentinel",
  },
  description:
    "Real-time wallet, token, approval, and smart-contract monitoring across EVM networks. Alerts, webhooks and analytics for treasuries, DAOs and DeFi teams.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-bs-theme="dark">
      <body className="d-flex flex-column min-vh-100">
        <Providers>{children}</Providers>
        <BootstrapClient />
      </body>
    </html>
  );
}
