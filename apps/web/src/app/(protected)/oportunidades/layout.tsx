import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Oportunidades",
  description:
    "Lista de leads qualificados com filtros por busca, status, score, atribuição e exportação em CSV.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
