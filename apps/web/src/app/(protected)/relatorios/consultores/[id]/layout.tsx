import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Perfil do consultor",
  description:
    "Desempenho individual de um consultor: leads atribuídos, contatados, reuniões, propostas e conversões.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
