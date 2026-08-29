import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Equipe",
  description:
    "Gerencie membros da organização, papéis de venda, convites, metas e transferência de propriedade.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
