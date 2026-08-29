import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Configurações",
  description:
    "Perfil, aparência, segurança, chaves de API da organização, envio automático, SLAs, equipe e integrações.",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
