import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Oportunidade",
  description:
    "Detalhe do lead com visão geral, pitch para o vendedor, evidências, análise técnica, contatos, cadência, atividades e próximas tarefas.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
