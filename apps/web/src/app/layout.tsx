import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Inter, Space_Grotesk, Geist_Mono } from "next/font/google";
import { cn } from "@/lib/utils";
import { Toaster } from "sonner";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "600", "700"],
});
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: {
    default: "Prospect.ai — Radar comercial inteligente",
    template: "%s · Prospect.ai",
  },
  description:
    "Plataforma de prospecção B2B com coleta, enriquecimento e qualificação por IA para gerar reuniões qualificadas.",
  applicationName: "Prospect.ai",
  authors: [{ name: "AlphaMec" }],
  keywords: [
    "prospecção B2B",
    "enriquecimento de leads",
    "qualificação de leads",
    "outreach automatizado",
    "inteligência comercial",
  ],
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: { index: false, follow: false },
  },
  openGraph: {
    type: "website",
    locale: "pt_BR",
    siteName: "Prospect.ai",
    title: "Prospect.ai — Radar comercial inteligente",
    description:
      "Plataforma de prospecção B2B com coleta, enriquecimento e qualificação por IA.",
  },
  twitter: {
    card: "summary",
    title: "Prospect.ai — Radar comercial inteligente",
    description:
      "Plataforma de prospecção B2B com coleta, enriquecimento e qualificação por IA.",
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const session = await getServerSession(authOptions);

  return (
    <html
      lang="pt-BR"
      suppressHydrationWarning
      className={cn(
        "font-sans",
        inter.variable,
        spaceGrotesk.variable,
        geistMono.variable,
      )}
    >
      <body className="font-sans antialiased bg-background text-foreground">
        <Script
          id="theme-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var s=localStorage.getItem('app-theme')||'alpha',r=document.documentElement;['light','dark','alpha'].forEach(function(t){r.classList.remove(t)});r.classList.add(['light','dark','alpha'].indexOf(s)>-1?s:'alpha')}catch(e){}})();`,
          }}
        />
        <Providers session={session}>
          {children}
          <Toaster richColors position="bottom-right" />
        </Providers>
      </body>
    </html>
  );
}