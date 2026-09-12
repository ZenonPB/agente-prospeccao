'use client';

import { BarChart3, Database, Loader2, Target, TrendingUp } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { useCommercialIntelligence } from '@/hooks/use-commercial-platform';

const SIGNAL_LABELS: Record<string, string> = {
  NEW_FACTORY: 'Nova fábrica',
  HIRING_ENGINEER: 'Contratação de profissionais de engenharia',
  HAS_CNC: 'Possui máquinas CNC',
  INDUSTRIAL_EXPANSION: 'Expansão industrial',
  JOB_CHANGE: 'Mudança de empresa do decisor',
  ROLE_CHANGE: 'Mudança de cargo do decisor',
  WEBSITE_MISSING: 'Empresa sem site identificado',
  WEBSITE_OUTDATED: 'Site com sinais de desatualização',
  EVENT_UPCOMING: 'Evento próximo',
  PROCUREMENT: 'Movimentação de compras ou licitação',
};
const OFFER_LABELS: Record<string, string> = {
  trophies: 'Troféus e premiações',
  landing_page: 'Landing pages',
  landing_pages: 'Landing pages',
  web_systems_erp: 'Sistemas web e ERP',
  mechanical_project: 'Projeto mecânico',
  technical_drawing: 'Desenho técnico',
  machine_manual_nr12: 'Manuais de máquinas e NR-12',
  nr12_manual: 'Manuais de máquinas e NR-12',
  '3d_printing': 'Impressão 3D',
  laser_cutting_technical: 'Corte a laser técnico',
  laser_custom_products: 'Produtos personalizados a laser',
};
const PROVIDER_LABELS: Record<string, string> = {
  unknown: 'Fonte não identificada',
  google_places: 'Google Maps',
  places: 'Google Maps',
  hunter: 'Hunter',
  website: 'Site oficial',
  cnae: 'Dados cadastrais',
  pncp: 'Compras públicas',
};

function percent(value: number | null | undefined) {
  return value == null ? 'Sem dados' : `${Math.round(value * 100)}%`;
}
function money(value: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
}
function readableSignal(value: string) {
  return SIGNAL_LABELS[value] ?? value.replaceAll('_', ' ').toLowerCase().replace(/^./, (letter) => letter.toUpperCase());
}
function readableOffer(value: string) {
  return OFFER_LABELS[value] ?? value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase());
}
function readableProvider(value: string) {
  return PROVIDER_LABELS[value] ?? value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase());
}

export function CommercialIntelligenceDashboard() {
  const query = useCommercialIntelligence();
  if (query.isLoading) return <div className="flex min-h-52 items-center justify-center text-muted-foreground" role="status"><Loader2 className="mr-2 size-5 animate-spin" aria-hidden="true" />Analisando resultados comerciais...</div>;
  if (query.isError || !query.data) return <EmptyState title="Não foi possível analisar os resultados" description="Tente novamente em alguns instantes." />;
  const data = query.data;
  const coverage = data.coverage;
  const attribution = data.attribution;

  return <div className="space-y-6">
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumo da inteligência comercial">
      <Metric icon={<Database className="size-4" aria-hidden="true" />} label="Empresas conhecidas" value={coverage.known_companies.toLocaleString('pt-BR')} />
      <Metric icon={<Target className="size-4" aria-hidden="true" />} label="Oportunidades com bom perfil" value={coverage.icp_matches.toLocaleString('pt-BR')} />
      <Metric icon={<TrendingUp className="size-4" aria-hidden="true" />} label="Resultados ligados à oferta correta" value={percent(attribution.attribution_rate)} />
      <Metric icon={<BarChart3 className="size-4" aria-hidden="true" />} label="Vitórias entre as 25 primeiras" value={percent(data.precision.won_top_25)} />
    </section>

    {attribution.unattributed_outcomes > 0 ? <Card className="border-amber-500/30 bg-amber-500/5"><CardContent className="p-5"><p className="font-medium">{attribution.unattributed_outcomes} resultado(s) ainda não estão ligados a uma oportunidade específica.</p><p className="mt-1 text-sm text-muted-foreground">Eles não entram no aprendizado de sinais. Isso evita que o sistema atribua uma venda à oferta errada por aproximação.</p></CardContent></Card> : null}

    <div className="grid gap-6 xl:grid-cols-2">
      <Card><CardHeader><CardTitle>Sinais que mais ajudam a vender</CardTitle><CardDescription>Compara resposta, reunião e venda somente quando há amostra suficiente e resultado ligado à oportunidade correta.</CardDescription></CardHeader><CardContent className="space-y-3">{!data.signal_effectiveness.length ? <EmptyState title="Ainda não há amostra suficiente" description="Conforme respostas, reuniões e vendas forem registradas, os sinais mais úteis aparecerão aqui." /> : data.signal_effectiveness.slice(0, 10).map((item) => <article key={item.signal} className="rounded-xl border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-medium">{readableSignal(item.signal)}</h3><p className="text-sm text-muted-foreground">Base: {item.sample_size} oportunidades</p></div><Badge variant="secondary">{percent(item.win_rate)} fecharam</Badge></div><div className="mt-3 grid grid-cols-3 gap-3 text-sm"><div><p className="text-muted-foreground">Responderam</p><p className="font-medium">{percent(item.reply_rate)}</p></div><div><p className="text-muted-foreground">Chegaram a reunião</p><p className="font-medium">{percent(item.meeting_rate)}</p></div><div><p className="text-muted-foreground">Receita média</p><p className="font-medium">{money(item.revenue_per_signal)}</p></div></div></article>)}</CardContent></Card>
      <Card><CardHeader><CardTitle>Fontes que trazem melhor retorno</CardTitle><CardDescription>Mostra volume, reuniões, vendas, custo conhecido e receita atribuída. Custo zero não gera uma porcentagem artificial de retorno.</CardDescription></CardHeader><CardContent className="space-y-3">{!data.provider_effectiveness.length ? <EmptyState title="Sem histórico de fontes" description="As fontes aparecerão após campanhas e resultados atribuídos." /> : data.provider_effectiveness.slice(0, 10).map((item) => <article key={item.provider} className="rounded-xl border p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-medium">{readableProvider(item.provider)}</h3><p className="text-sm text-muted-foreground">{item.candidates} candidatos · {item.meetings} reuniões · {item.wins} vendas</p></div><Badge variant="outline">{item.roi == null ? 'Retorno sem custo calculável' : `${Math.round(item.roi * 100)}% de retorno`}</Badge></div><p className="mt-3 text-sm text-muted-foreground">Custo registrado: {money(item.cost)} · Receita atribuída: {money(item.revenue)}</p></article>)}</CardContent></Card>
    </div>

    <div className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
      <Card><CardHeader><CardTitle>Qualidade do topo da fila</CardTitle><CardDescription>Verifica se as oportunidades priorizadas realmente geram avanço comercial.</CardDescription></CardHeader><CardContent className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1"><Quality label="Respostas nas 10 primeiras" value={data.precision.reply_top_10} /><Quality label="Reuniões nas 10 primeiras" value={data.precision.meeting_top_10} /><Quality label="Vendas nas 25 primeiras" value={data.precision.won_top_25} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Cobertura comercial</CardTitle><CardDescription>Mostra quanto da base conhecida já está pronta para abordagem. O tamanho total do mercado permanece “desconhecido” até existir uma fonte confiável.</CardDescription></CardHeader><CardContent><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><Coverage label="Empresas conhecidas" value={coverage.known_companies} /><Coverage label="Leads registrados" value={coverage.leads} /><Coverage label="Bom perfil comercial" value={coverage.icp_matches} /><Coverage label="Pessoas contatáveis" value={coverage.contactable_people} /><Coverage label="Já prospectados" value={coverage.prospected_leads} /><Coverage label="Clientes ganhos" value={coverage.won_leads} /></div></CardContent></Card>
    </div>

    <Card><CardHeader><CardTitle>Segmentos que mais convertem por oferta</CardTitle><CardDescription>Aprendizado separado por oferta e segmento, sem misturar contextos comerciais diferentes.</CardDescription></CardHeader><CardContent>{!data.niche_priors.length ? <EmptyState title="Ainda não há segmentos com amostra mínima" description="São necessários resultados suficientes no mesmo contexto antes de sugerir um padrão." /> : <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{data.niche_priors.map((item) => <article key={`${item.offer_key}:${item.segment}`} className="rounded-xl border p-4"><p className="text-sm text-muted-foreground">{readableOffer(item.offer_key)}</p><h3 className="mt-1 font-medium">{item.segment}</h3><p className="mt-3 text-sm">{percent(item.win_rate)} de vendas em {item.sample_size} oportunidade(s)</p><p className="mt-1 text-sm text-muted-foreground">Receita atribuída: {money(item.revenue)}</p></article>)}</div>}</CardContent></Card>
  </div>;
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <div className="rounded-xl border bg-card p-4"><div className="flex items-center gap-2 text-sm text-muted-foreground">{icon}{label}</div><p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p></div>; }
function Quality({ label, value }: { label: string; value: number | null }) { return <div className="rounded-lg border p-3"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-1 text-xl font-semibold">{percent(value)}</p></div>; }
function Coverage({ label, value }: { label: string; value: number }) { return <div><p className="text-sm text-muted-foreground">{label}</p><p className="mt-1 text-xl font-semibold tabular-nums">{value.toLocaleString('pt-BR')}</p></div>; }
