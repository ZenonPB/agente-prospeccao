import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Aceitar convite",
  description:
    "Entre para a organização que te convidou no Prospect.ai.",
  noindex: false,
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
