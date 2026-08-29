import type { Metadata } from "next";

/**
 * Helper para `generateMetadata` em page.tsx server components.
 * Centraliza o template/title/description e mantém o robots noindex para
 * páginas autenticadas (o app inteiro é privado).
 */
export function buildPageMetadata({
  title,
  description,
  noindex = true,
}: {
  title: string;
  description: string;
  noindex?: boolean;
}): Metadata {
  return {
    title,
    description,
    robots: noindex
      ? { index: false, follow: false, nocache: true, googleBot: { index: false, follow: false } }
      : { index: true, follow: true },
    openGraph: {
      title,
      description,
      type: "website",
      locale: "pt_BR",
      siteName: "Prospect.ai",
    },
    twitter: {
      card: "summary",
      title,
      description,
    },
  };
}
