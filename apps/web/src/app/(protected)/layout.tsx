import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { MobileBottomNav } from "@/components/layout/mobile-bottom-nav";
import { GuidedTourManager } from "@/components/tutorial/guided-tour-manager";
import { PageTransition } from "@/components/ui/motion";

export const metadata: Metadata = {
  title: { default: "App", template: "%s · Prospect.ai" },
  robots: { index: false, follow: false, nocache: true, googleBot: { index: false, follow: false } },
};

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
    <div className="flex h-dvh w-full max-w-full min-h-0 overflow-hidden bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Header />
        <main className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto p-4 pb-24 sm:p-6 lg:pb-6">
          <div className="min-w-0 max-w-full">
            <PageTransition>{children}</PageTransition>
          </div>
        </main>
      </div>
      <MobileBottomNav />
      <GuidedTourManager />
    </div>
  );
}