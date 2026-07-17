import Footer from "@/components/public/Footer";
import PublicNavbar from "@/components/public/PublicNavbar";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PublicNavbar />
      <main className="flex-grow-1">{children}</main>
      <Footer />
    </>
  );
}
