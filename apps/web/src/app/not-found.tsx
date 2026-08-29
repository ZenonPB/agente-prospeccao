import type { Metadata } from "next";
import Link from "next/link";
import { Compass, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Página não encontrada",
  description:
    "O endereço que você procura não existe ou foi movido. Volte ao radar e continue prospectando.",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <main
      role="main"
      className="flex min-h-dvh w-full items-center justify-center bg-background px-6 py-12"
    >
      <div className="flex w-full max-w-md flex-col items-center gap-6 text-center animate-fade-up">
        <div className="sonar flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Compass className="h-7 w-7" aria-hidden="true" />
        </div>

        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Erro 404
          </p>
          <h1 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
            Esse caminho não leva a lugar nenhum
          </h1>
          <p className="mx-auto max-w-sm text-sm leading-relaxed text-muted-foreground">
            A página que você procura não existe ou foi movida. Confira o
            endereço ou volte para o radar comercial.
          </p>
        </div>

        <div className="flex w-full flex-col gap-2 sm:flex-row sm:justify-center">
          <Button render={<Link href="/dashboard" />} className="gap-2">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Voltar ao radar
          </Button>
          <Button render={<Link href="/oportunidades" />} variant="outline">
            Ver oportunidades
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          Precisa de ajuda?{" "}
          <Link
            href="/ajuda"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Acesse a central de ajuda
          </Link>
        </p>
      </div>
    </main>
  );
}
