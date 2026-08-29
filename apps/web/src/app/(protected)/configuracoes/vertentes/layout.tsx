import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Vertentes",
  description:
    "Crie, duplique e personalize perfis de empresa (vertentes) que a IA usa para qualificar e abordar leads.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
