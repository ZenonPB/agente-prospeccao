import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { HelpCircle, Users, ShieldCheck } from "lucide-react";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Ajuda",
  description:
    "Perguntas frequentes, quem opera a plataforma e políticas do Prospect.ai.",
});

const SECTIONS = [
  { id: "faq", label: "Perguntas frequentes", icon: HelpCircle },
  { id: "equipe", label: "Quem opera", icon: Users },
  { id: "privacidade", label: "Privacidade e termos", icon: ShieldCheck },
] as const;

const FAQ_ITEMS: Array<{ question: string; answer: string }> = [
  {
    question: "De onde vêm os leads?",
    answer:
      "De três fontes: busca no Google Places (nome, endereço, avaliação e site quando existem), importação de planilha CSV e descoberta por CNAE a partir de dados da Receita Federal. Leads repetidos são unificados dentro da sua organização por CNPJ, domínio ou identificador do Places — a mesma empresa não aparece duas vezes na sua base.",
  },
  {
    question: "Como a IA qualifica um lead?",
    answer:
      "Cada campanha tem um modelo de pontuação que diz o que importa para aquela oferta (por exemplo: para quem vende sites, ter um site desatualizado ou não ter site pesa a favor). A IA dá uma nota de 0 a 100: a partir de 60 o lead fica QUALIFICADO e entra na fila de contato; abaixo disso fica DESQUALIFICADO e não recebe mensagens. Ela também marca a prioridade (Quente, Morno ou Frio) e lista os motivos e evidências, que você confere na aba Evidências do lead. Lead sem site também é pontuado — nunca é descartado só por não ter site. Se a IA falhar, o lead continua como NOVO para ser avaliado de novo depois.",
  },
  {
    question: "Como funciona o envio das mensagens?",
    answer:
      "Cada lead qualificado entra numa cadência de até 4 mensagens: dia 0, dia 3, dia 7 e dia 14 (o calendário pode variar por vertente). Por padrão, você revisa e envia cada mensagem manualmente; o envio automático só acontece se a sua organização ativar a opção, e mesmo assim respeita o limite diário de envios, a janela de horário configurada e só usa e-mails verificados. Quando o lead responde, ele muda para RESPONDIDO e a cadência para. Pedidos de STOP viram opt-out imediato. Se a cadência terminar sem resposta, o lead fica como PERDIDO e pode voltar à fila depois de 90 dias.",
  },
  {
    question: "O que cada papel pode fazer?",
    answer:
      "Consultores criam as próprias campanhas e trabalham os próprios leads no kanban. Analistas e gestores enxergam todos os leads da organização e acessam os relatórios e o BI (consultores não veem relatórios). Criar organizações, convidar membros, trocar papéis de venda e configurar chaves e limites de envio é restrito aos donos e administradores da organização.",
  },
  {
    question: "Como falo com o lead pelo WhatsApp?",
    answer:
      "No cartão do lead (kanban ou página de detalhe) há o botão de WhatsApp: ele abre a conversa com a mensagem da campanha já preenchida com o nome do decisor e um fato real sobre a empresa. Você confere e aperta enviar — o disparo é sempre feito por uma pessoa, nunca automático. O contato fica registrado no histórico do lead.",
  },
  {
    question: "Meus dados e os dos leads estão seguros?",
    answer:
      "Cada organização só enxerga os próprios dados; chaves de serviços externos ficam criptografadas e nunca são exibidas; ações administrativas ficam registradas em log de auditoria. A análise de sites dos prospectados é sempre passiva — só lê informações públicas, sem testar senhas nem sondar vulnerabilidades. Detalhes na seção Privacidade e termos abaixo.",
  },
];

const TEAM_PHOTOS: Array<{ src: string; alt: string }> = [
  {
    src: "/imgs/alphamec/foto2.jpg",
    alt: "Seis integrantes da equipe AlphaMec de camisa polo bordô posando sorridentes em frente ao painel Avance Gerações em um evento",
  },
  {
    src: "/imgs/alphamec/foto3.jpg",
    alt: "Integrante da equipe AlphaMec de camisa polo bordô e crachá do Avance Gerações assistindo a uma palestra em auditório",
  },
  {
    src: "/imgs/alphamec/nortear.jpg",
    alt: "Grupo da equipe AlphaMec segurando a bandeira assinada Alphamec Empresa Jr. em um evento",
  },
];

export default function AjudaPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-10">
      <PageHeader
        eyebrow="Suporte"
        title="Central de ajuda"
        description="Respostas rápidas, quem opera a plataforma e nossas políticas."
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
            O essencial para coletar, qualificar e contatar leads na plataforma.
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
        id="equipe"
        aria-labelledby="equipe-title"
        className="scroll-mt-24 space-y-4"
      >
        <div className="space-y-1">
          <h2
            id="equipe-title"
            className="font-heading text-xl font-semibold tracking-tight"
          >
            Quem opera
          </h2>
          <p className="text-sm text-muted-foreground">
            O Prospect.ai é operado pela equipe da AlphaMec Empresa Jr.
          </p>
        </div>

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
            Resumo de como tratamos dados na plataforma.
          </p>
        </div>

        {/* Texto operacional mínimo fiel ao comportamento atual do sistema;
            precisa de revisão jurídica antes de virar política definitiva. */}
        <Card>
          <CardContent className="space-y-4 p-5 text-sm leading-relaxed text-muted-foreground">
            <h3 className="text-base font-semibold text-foreground">
              1. Dados que coletamos
            </h3>
            <p>
              Dados de cadastro (nome e e-mail), dados de uso da plataforma e
              dados dos leads prospectados a partir de fontes públicas: Google
              Places, Receita Federal, sites das próprias empresas e planilhas
              CSV importadas pela sua organização.
            </p>

            <h3 className="text-base font-semibold text-foreground">
              2. Como usamos os dados
            </h3>
            <p>
              Usamos os dados exclusivamente para gerar e gerenciar oportunidades
              comerciais dentro da sua organização. Leads coletados por uma
              organização nunca ficam visíveis para outra. Não vendemos dados a
              terceiros.
            </p>

            <h3 className="text-base font-semibold text-foreground">
              3. Compartilhamento
            </h3>
            <p>
              Compartilhamos dados apenas com os prestadores essenciais ao
              funcionamento: hospedagem, envio de e-mails e modelos de IA
              acionados com as chaves configuradas pela organização. Chaves e
              segredos ficam criptografados e nunca são exibidos na interface.
            </p>

            <h3 className="text-base font-semibold text-foreground">
              4. Direitos do titular (LGPD)
            </h3>
            <p>
              Você pode pedir acesso, correção ou eliminação dos seus dados ao
              administrador da sua organização. Leads que pedirem para não ser
              mais contatados (resposta STOP ou opt-out) são marcados e excluídos
              de todos os envios futuros.
            </p>

            <h3 className="text-base font-semibold text-foreground">
              5. Retenção e segurança
            </h3>
            <p>
              O acesso é separado por organização e por papel, ações
              administrativas ficam registradas em log de auditoria e a análise
              de sites de prospectados é sempre passiva (somente leitura de
              conteúdo público).
            </p>

            <h3 className="text-base font-semibold text-foreground">
              6. Cookies
            </h3>
            <p>
              Usamos apenas cookies essenciais de sessão e autenticação,
              necessários para manter você conectado com segurança.
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
