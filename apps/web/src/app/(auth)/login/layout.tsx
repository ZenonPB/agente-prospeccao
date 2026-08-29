import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Login",
  description:
    "Acesse o Prospect.ai e continue sua prospecção B2B com qualificação por IA.",
  noindex: false,
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
