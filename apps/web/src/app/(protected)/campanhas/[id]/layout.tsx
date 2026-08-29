import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Campanha",
  description:
    "Detalhe da campanha: status, leads coletados, qualificação, importação CSV, descoberta por CNAE e PNCP.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
