import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Esqueci minha senha",
  description:
    "Receba por email um link para redefinir sua senha do Prospect.ai.",
  noindex: false,
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
