import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Campanha",
  description:
    "Empresas encontradas, análise e oportunidades da campanha.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
