import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Campanhas",
  description:
    "Encontre empresas que combinam com o que você vende e acompanhe cada busca."
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
