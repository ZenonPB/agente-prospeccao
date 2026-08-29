import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Redefinir senha",
  description:
    "Defina uma nova senha para sua conta do Prospect.ai.",
  noindex: false,
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
