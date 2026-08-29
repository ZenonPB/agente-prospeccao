import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Nova campanha",
  description:
    "Assistente inteligente ou wizard passo a passo para criar uma nova campanha de prospecção B2B.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
