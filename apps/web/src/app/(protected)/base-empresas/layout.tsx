import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Base de empresas",
  description:
    "Situação dos dados cadastrais que alimentam suas buscas.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
