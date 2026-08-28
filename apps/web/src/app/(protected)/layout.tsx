import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { MobileBottomNav } from "@/components/layout/mobile-bottom-nav";
import { GuidedTourManager } from "@/components/tutorial/guided-tour-manager";
import { PageTransition } from "@/components/ui/motion";

export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/login");
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-4 pb-24 sm:p-6 lg:pb-6">
          <PageTransition>{children}</PageTransition>
        </main>
      </div>
      <MobileBottomNav />
      <GuidedTourManager />
    </div>
  );
}