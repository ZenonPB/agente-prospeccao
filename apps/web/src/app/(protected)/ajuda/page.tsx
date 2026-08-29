import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { HelpCircle, MessagesSquare, ShieldCheck } from "lucide-react";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Ajuda",
  description:
    "Perguntas frequentes, depoimentos de clientes e políticas do Prospect.ai.",
});

const SECTIONS = [
  { id: "faq", label: "Perguntas frequentes", icon: HelpCircle },
  { id: "depoimentos", label: "Depoimentos", icon: MessagesSquare },
  { id: "privacidade", label: "Privacidade e termos", icon: ShieldCheck },
] as const;

const FAQ_ITEMS: Array<{ question: string; answer: string }> = [
  {
    question: "TODO: como funciona a coleta de leads?",
    answer:
      "TODO: explicar aqui a integração com Google Places, CSVs e CNAE. Descreva o que entra, o que sai e o que o cliente precisa configurar.",
  },
  {
    question: "TODO: como a IA qualifica um lead?",
    answer:
      "TODO: explicar o score 0–100, a vertente aplicada, os fatores positivos/negativos e o que significa cada faixa (qualificado, desqualificado).",
  },
  {
    question: "TODO: como enviar mensagens de outreach?",
    answer:
      "TODO: explicar a cadência (passos configurados na vertente), o botão Gerar/Enviar mensagem e as opções de envio manual x automático (opt-in da org).",
  },
  {
    question: "TODO: quanto custa? Existe plano gratuito?",
    answer:
      "TODO: descrever os planos, limite diário de envios por org e o que está incluso em cada um.",
  },
  {
    question: "TODO: meus dados estão seguros?",
    answer:
      "TODO: descrever criptografia, segregação por organização, retenção de dados e onde encontrar a política completa (aba Privacidade nesta página).",
  },
];

const TESTIMONIALS: Array<{
  author: string;
  role: string;
  company: string;
  quote: string;
}> = [
  {
    author: "TODO: nome do cliente",
    role: "TODO: cargo",
    company: "TODO: empresa",
    quote: "TODO: depoimento real do cliente (1–3 frases, preferencialmente com um resultado concreto).",
  },
  {
    author: "TODO: nome do cliente",
    role: "TODO: cargo",
    company: "TODO: empresa",
    quote: "TODO: depoimento real do cliente (1–3 frases).",
  },
  {
    author: "TODO: nome do cliente",
    role: "TODO: cargo",
    company: "TODO: empresa",
    quote: "TODO: depoimento real do cliente (1–3 frases).",
  },
];

const TEAM_PHOTOS: Array<{ src: string; alt: string }> = [
  { src: "/imgs/alphamec/foto2.jpg", alt: "TODO: descrever a foto (ex.: equipe AlphaMec reunida em escritório)" },
  { src: "/imgs/alphamec/foto3.jpg", alt: "TODO: descrever a foto (ex.: membros do time em ação)" },
  { src: "/imgs/alphamec/nortear.jpg", alt: "TODO: descrever a foto (ex.: equipe no Evento Nortear)" },
];

export default function AjudaPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-10">
      <PageHeader
        eyebrow="Suporte"
        title="Central de ajuda"
        description="Respostas rápidas, depoimentos de clientes e nossas políticas."
      />

      <nav aria-label="Seções da central de ajuda" className="flex flex-wrap gap-2">
        {SECTIONS.map((section) => (
          <a
            key={section.id}
            href={`#${section.id}`}
            className="inline-flex items-center gap-2 rounded-full border bg-card px-4 py-2 text-sm font-medium hover:border-primary hover:text-primary"
          >
            <section.icon className="h-4 w-4" aria-hidden="true" />
            {section.label}
          </a>
        ))}
      </nav>

      <section id="faq" aria-labelledby="faq-title" className="scroll-mt-24 space-y-4">
        <div className="space-y-1">
          <h2 id="faq-title" className="font-heading text-xl font-semibold tracking-tight">
            Perguntas frequentes
          </h2>
          <p className="text-sm text-muted-foreground">
            TODO: revisar/reescrever as 5 perguntas abaixo antes de publicar.
          </p>
        </div>

        <div className="space-y-2">
          {FAQ_ITEMS.map((item, i) => (
            <details
              key={i}
              className="group rounded-xl border bg-card p-4 open:shadow-sm"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium">
                <span>{item.question}</span>
                <span
                  className="ml-auto text-muted-foreground transition-transform group-open:rotate-180"
                  aria-hidden="true"
                >
                  ▾
                </span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {item.answer}
              </p>
            </details>
          ))}
        </div>
      </section>

      <section
        id="depoimentos"
        aria-labelledby="depoimentos-title"
        className="scroll-mt-24 space-y-4"
      >
        <div className="space-y-1">
          <h2
            id="depoimentos-title"
            className="font-heading text-xl font-semibold tracking-tight"
          >
            Depoimentos
          </h2>
          <p className="text-sm text-muted-foreground">
            TODO: substituir pelos depoimentos reais abaixo. Adicione fotos da
            equipe com descrições acessíveis.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          {TESTIMONIALS.map((t, i) => (
            <Card key={i} className="h-full">
              <CardContent className="flex h-full flex-col gap-3 p-5">
                <p className="text-sm leading-relaxed">“{t.quote}”</p>
                <div className="mt-auto text-xs text-muted-foreground">
                  <p className="font-semibold text-foreground">{t.author}</p>
                  <p>
                    {t.role} · {t.company}
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Fotos da equipe
          </h3>
          <p className="text-sm text-muted-foreground">
            TODO: revisar/editar as descrições (alt) das fotos abaixo para
            acessibilidade e SEO.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {TEAM_PHOTOS.map((photo) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={photo.src}
                src={photo.src}
                alt={photo.alt}
                className="aspect-[4/3] w-full rounded-xl border object-cover"
                loading="lazy"
              />
            ))}
          </div>
        </div>
      </section>

      <section
        id="privacidade"
        aria-labelledby="privacidade-title"
        className="scroll-mt-24 space-y-4"
      >
        <div className="space-y-1">
          <h2
            id="privacidade-title"
            className="font-heading text-xl font-semibold tracking-tight"
          >
            Privacidade e termos
          </h2>
          <p className="text-sm text-muted-foreground">
            TODO: o time jurídico/comercial precisa preencher o texto abaixo
            com a política real. Estrutura sugerida (placeholders).
          </p>
        </div>

        <Card>
          <CardContent className="space-y-4 p-5 text-sm leading-relaxed text-muted-foreground">
            <h3 className="text-base font-semibold text-foreground">
              1. Dados que coletamos
            </h3>
            <p>
              TODO: listar dados de cadastro (nome, e-mail), dados de uso da
              plataforma e dados de leads coletados em fontes públicas
              (Google Places, Receita Federal, CSVs importados).
            </p>

            <h3 className="text-base font-semibold text-foreground">
              2. Como usamos os dados
            </h3>
            <p>
              TODO: explicar a finalidade (geração de oportunidades
              comerciais), a base legal (legítimo interesse / execução de
              contrato) e que os dados não são vendidos a terceiros.
            </p>

            <h3 className="text-base font-semibold text-foreground">
              3. Compartilhamento
            </h3>
            <p>
              TODO: listar prestadores essenciais (hospedagem, envio de
              e-mail, modelos de IA) e informar se há transferência
              internacional.
            </p>

            <h3 className="text-base font-semibold text-foreground">
              4. Direitos do titular (LGPD)
            </h3>
            <p>
              TODO: explicar como exercer os direitos de acesso,
              correção, portabilidade, eliminação e revogação de
              consentimento, com canal de contato (e-mail do DPO/responsável).
            </p>

            <h3 className="text-base font-semibold text-foreground">
              5. Retenção e segurança
            </h3>
            <p>
              TODO: prazo de retenção dos leads, criptografia em trânsito e
              em repouso, controle de acesso por organização e logs de
              auditoria.
            </p>

            <h3 className="text-base font-semibold text-foreground">
              6. Cookies
            </h3>
            <p>
              TODO: listar cookies essenciais (sessão, CSRF) e qualquer
              analytics/marketing usado, com opt-out.
            </p>

            <p className="border-t pt-4 text-xs">
              Última atualização: TODO: data. Versão: TODO: número.
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
