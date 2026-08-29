import type { Metadata } from "next";
import Link from "next/link";
import { Compass, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Página não encontrada",
  description:
    "Esse caminho dentro do Prospect.ai não existe. Volte ao radar ou escolha uma das áreas abaixo.",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <div className="flex min-h-full w-full items-center justify-center py-12">
      <div className="flex w-full max-w-xl flex-col items-center gap-6 text-center animate-fade-up">
        <div className="sonar flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Compass className="h-6 w-6" aria-hidden="true" />
        </div>

        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Erro 404
          </p>
          <h1 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">
            Nada por aqui — ainda
          </h1>
          <p className="mx-auto max-w-md text-sm leading-relaxed text-muted-foreground">
            Esse caminho dentro do Prospect.ai não existe ou foi movido.
            Confira o link ou volte para uma das áreas conhecidas.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button render={<Link href="/dashboard" />} className="gap-2">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Visão geral
          </Button>
          <Button render={<Link href="/oportunidades" />} variant="outline">
            Oportunidades
          </Button>
          <Button render={<Link href="/campanhas" />} variant="outline">
            Campanhas
          </Button>
          <Button render={<Link href="/vendas" />} variant="outline">
            Negociações
          </Button>
        </div>
      </div>
    </div>
  );
}
