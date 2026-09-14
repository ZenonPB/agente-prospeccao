import type { Metadata } from 'next';
import Link from 'next/link';
import {
  ArrowRight,
  BarChart3,
  BriefcaseBusiness,
  HelpCircle,
  Lightbulb,
  Megaphone,
  ShieldCheck,
  Target,
  Users,
} from 'lucide-react';
import { PageHeader } from '@/components/ui/page-header';
import { Card, CardContent } from '@/components/ui/card';
import { TourCard } from '@/components/configuracoes/tour-card';
import { buildPageMetadata } from '@/lib/metadata';

export const metadata: Metadata = buildPageMetadata({
  title: 'Como usar',
  description: 'Guia prático, tutorial e perguntas frequentes do Prospect.ai.',
});

const WORKFLOW = [
  { step: '1', title: 'Diga o que quer vender', description: 'Crie uma busca escrevendo em linguagem normal o serviço e o tipo de cliente que você procura.', href: '/campanhas/nova', action: 'Criar uma busca', icon: Megaphone },
  { step: '2', title: 'Revise quem vale abordar', description: 'Confira os leads encontrados, os motivos da recomendação e as evidências antes de gastar tempo no contato.', href: '/oportunidades', action: 'Ver oportunidades', icon: Target },
  { step: '3', title: 'Trabalhe a fila do dia', description: 'Use Minha carteira para saber quem precisa de atenção agora, sem depender de memória ou planilhas paralelas.', href: '/crm', action: 'Abrir minha carteira', icon: BriefcaseBusiness },
  { step: '4', title: 'Registre o que aconteceu', description: 'Mantenha estágio, próxima ação, responsável, reunião, proposta e resultado atualizados nas negociações.', href: '/vendas', action: 'Abrir negociações', icon: ArrowRight },
  { step: '5', title: 'Veja o que está funcionando', description: 'Use os resultados para comparar buscas, períodos e desempenho sem confundir coincidência com causa.', href: '/relatorios', action: 'Ver resultados', icon: BarChart3 },
  { step: '6', title: 'Ensine o sistema com fatos reais', description: 'Avaliações e resultados ajudam a sugerir melhorias; nenhuma mudança na avaliação é publicada sem revisão humana.', href: '/inteligencia-comercial', action: 'Ver o que está funcionando', icon: Lightbulb },
] as const;

const FAQ_ITEMS = [
  {
    question: 'O que eu faço quando abro o sistema?',
    answer: 'Comece por Minha carteira. Ela reúne o que precisa de atenção hoje. Se a equipe precisa de novos leads, vá em Encontrar novos clientes e descreva em uma frase o serviço que quer vender e para quem.',
  },
  {
    question: 'A nota da IA decide sozinha se devo falar com uma empresa?',
    answer: 'Não. A nota serve para priorizar. Abra o lead e confira os motivos e evidências. Informação ausente não é tratada como evidência negativa, e inferências ficam separadas de fatos. A decisão comercial continua sendo humana.',
  },
  {
    question: 'De onde vêm as empresas e contatos?',
    answer: 'O sistema combina fontes habilitadas pela equipe, como busca de empresas, dados públicos, importações autorizadas e serviços de contato. Cada fonte tem limites. As conexões externas podem ser testadas por administradores em Configurações.',
  },
  {
    question: 'Como evito esquecer follow-ups?',
    answer: 'Registre a próxima ação e use a fila de Minha carteira. Acompanhamentos automáticos ajudam a organizar os próximos passos, mas o envio e a abordagem continuam sujeitos às permissões e regras da organização.',
  },
  {
    question: 'Como o sistema aprende?',
    answer: 'Avaliações humanas e resultados registrados viram evidência para análise. Quando há amostra suficiente, o sistema pode propor uma nova versão da estratégia. Gestores revisam, aprovam e publicam explicitamente; também é possível voltar para uma versão anterior.',
  },
  {
    question: 'Qual a diferença entre Encontrar novos clientes, Pesquisar na base e Minha carteira?',
    answer: 'Encontrar novos clientes busca empresas novas para prospectar. Pesquisar na base pesquisa empresas e pessoas que já estão cadastradas. Minha carteira mostra o que precisa da sua atenção agora.',
  },
  {
    question: 'Os dados de uma organização aparecem em outra?',
    answer: 'Não. Buscas, leads, empresas, pessoas, resultados, chaves e configurações são separados por organização. A separação é validada a cada acesso.',
  },
  {
    question: 'Posso testar Google, IA e busca de contatos sem expor minhas chaves?',
    answer: 'Sim. Em Configurações, administradores podem usar “Testar conexões”. O teste faz uma chamada mínima ao serviço e devolve apenas o estado da conexão; o valor da chave e a resposta bruta nunca são mostrados na interface.',
  },
];

const TEAM_PHOTOS = [
  { src: '/imgs/alphamec/foto2.jpg', alt: 'Equipe AlphaMec reunida em um evento' },
  { src: '/imgs/alphamec/foto3.jpg', alt: 'Integrante da AlphaMec em um evento' },
  { src: '/imgs/alphamec/nortear.jpg', alt: 'Equipe AlphaMec com a bandeira da empresa júnior' },
] as const;

export default function AjudaPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-10">
      <PageHeader
        eyebrow="Ajuda"
        title="Como usar o Prospect.ai"
        description="Um caminho simples para prospectar, vender e aprender com o que realmente aconteceu."
      />

      <TourCard />

      <section aria-labelledby="workflow-title" className="space-y-4">
        <div>
          <h2 id="workflow-title" className="font-heading text-xl font-semibold tracking-tight">Fluxo recomendado no dia a dia</h2>
          <p className="mt-1 text-sm text-muted-foreground">Você não precisa usar todas as telas. Este é o caminho principal para a operação comercial.</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {WORKFLOW.map(({ step, title, description, href, action, icon: Icon }) => (
            <Card key={step} className="transition-colors hover:border-primary/30">
              <CardContent className="flex gap-4 p-5">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 font-semibold text-primary">{step}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2"><Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" /><h3 className="font-semibold">{title}</h3></div>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{description}</p>
                  <Link href={href} className="mt-3 inline-flex min-h-10 items-center gap-1 text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{action}<ArrowRight className="h-4 w-4" /></Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section id="faq" aria-labelledby="faq-title" className="scroll-mt-24 space-y-4">
        <div>
          <h2 id="faq-title" className="flex items-center gap-2 font-heading text-xl font-semibold tracking-tight"><HelpCircle className="h-5 w-5" />Perguntas frequentes</h2>
          <p className="mt-1 text-sm text-muted-foreground">Respostas curtas para as dúvidas que mais travam a operação.</p>
        </div>
        <div className="space-y-2">
          {FAQ_ITEMS.map((item) => (
            <details key={item.question} className="group rounded-xl border bg-card p-4 open:shadow-sm">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium"><span>{item.question}</span><span className="text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true">▾</span></summary>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{item.answer}</p>
            </details>
          ))}
        </div>
      </section>

      <section id="equipe" aria-labelledby="equipe-title" className="scroll-mt-24 space-y-4">
        <div>
          <h2 id="equipe-title" className="flex items-center gap-2 font-heading text-xl font-semibold tracking-tight"><Users className="h-5 w-5" />Quem opera</h2>
          <p className="mt-1 text-sm text-muted-foreground">O Prospect.ai é operado pela equipe da AlphaMec Empresa Jr.</p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {TEAM_PHOTOS.map((photo) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={photo.src} src={photo.src} alt={photo.alt} className="aspect-[4/3] w-full rounded-xl border object-cover" loading="lazy" />
          ))}
        </div>
      </section>

      <section id="privacidade" aria-labelledby="privacidade-title" className="scroll-mt-24 space-y-4">
        <div>
          <h2 id="privacidade-title" className="flex items-center gap-2 font-heading text-xl font-semibold tracking-tight"><ShieldCheck className="h-5 w-5" />Privacidade e segurança</h2>
          <p className="mt-1 text-sm text-muted-foreground">Resumo operacional. A política jurídica definitiva deve ser revisada antes de publicação externa.</p>
        </div>
        <Card>
          <CardContent className="space-y-4 p-5 text-sm leading-relaxed text-muted-foreground">
            <p><strong className="text-foreground">Separação por organização.</strong> Cada organização acessa apenas seus próprios dados, configurações e credenciais.</p>
            <p><strong className="text-foreground">Chaves de acesso.</strong> Chaves externas são armazenadas de forma protegida e a interface nunca devolve o valor salvo. Em produção, a chave mestra de criptografia é obrigatória.</p>
            <p><strong className="text-foreground">Contato comercial.</strong> Opt-out deve ser respeitado. Campanhas externas e automações permanecem condicionadas às permissões, limites, serviços habilitados e base legal aplicável.</p>
            <p><strong className="text-foreground">Dados e evidências.</strong> O sistema distingue fatos, inferências e informação desconhecida. Análises automáticas não substituem revisão humana quando uma decisão comercial exige contexto.</p>
            <p><strong className="text-foreground">Auditoria.</strong> Alterações administrativas e operações comerciais relevantes mantêm trilha para permitir investigação, aprendizado e correção.</p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
