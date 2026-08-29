import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Relatórios",
  description:
    "Visão executiva das vendas: KPIs, funil, ranking de oportunidades, desempenho por consultor e mapa de calor por estado.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
