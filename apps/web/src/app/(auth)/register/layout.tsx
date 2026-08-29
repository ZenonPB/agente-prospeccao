import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Criar conta",
  description:
    "Crie sua conta gratuita no Prospect.ai e comece a prospectar com IA em minutos.",
  noindex: false,
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
