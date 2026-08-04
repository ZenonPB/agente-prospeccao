import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Inter, Space_Grotesk, Geist_Mono } from "next/font/google";
import { cn } from "@/lib/utils";
import { Toaster } from "sonner";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "600", "700"],
});
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  title: "Agente Prospecção",
  description: "Plataforma de Inteligência Comercial",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
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
        <Providers>
          {children}
          <Toaster richColors position="bottom-right" />
        </Providers>
      </body>
    </html>
  );
}