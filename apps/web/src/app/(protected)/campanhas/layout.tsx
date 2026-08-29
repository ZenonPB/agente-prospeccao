import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Campanhas",
  description:
    "Crie buscas de prospecção, importe CSVs, descubra empresas por CNAE e acompanhe o pipeline de cada campanha.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
