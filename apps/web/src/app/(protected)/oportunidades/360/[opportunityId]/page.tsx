'use client';

import { use, type ReactNode } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  Building2,
  CalendarClock,
  CircleDollarSign,
  Clock3,
  ExternalLink,
  Mail,
  MapPin,
  Phone,
  Target,
  UserRound,
} from 'lucide-react';

import { useOpportunity360 } from '@/hooks/use-opportunity-360';
import { offerProfileLabel, signalLabel } from '@/lib/offers';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import type { Opportunity360TimelineItem } from '@/types/opportunity-360';

const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const dateTime = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium', timeStyle: 'short' });

const STATUS_LABELS: Record<string, string> = {
  NOVO: 'Novo', QUALIFICADO: 'Apto para contato', CONTATADO: 'Contato realizado', RESPONDIDO: 'Cliente respondeu',
  REUNIAO_MARCADA: 'Reunião agendada', REUNIAO_FEITA: 'Reunião realizada', PROPOSTA_ENVIADA: 'Proposta enviada',
  CONVERTIDO: 'Ganho', PERDIDO: 'Perdido', DESQUALIFICADO: 'Desqualificado',
};

const TIMELINE_LABELS: Record<Opportunity360TimelineItem['type'], string> = {
  ACTIVITY: 'Atividade', TASK: 'Tarefa', FEEDBACK: 'Avaliação', OUTCOME: 'Resultado', SEQUENCE: 'Sequência', WORKFLOW: 'Automação', NEXT_ACTION: 'Próxima ação',
};

function formatDate(value: string | null | undefined) {
  if (!value) return 'Não informado';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Não informado' : dateTime.format(parsed);
}

function readableEvidence(value: unknown): string {
  if (typeof value === 'string') return value;
  if (!value || typeof value !== 'object') return 'Evidência registrada';
  const item = value as Record<string, unknown>;
  const title = item.title ?? item.signal ?? item.field ?? item.value;
  return typeof title === 'string' || typeof title === 'number' ? String(title) : 'Evidência registrada';
}

function valueOrDash(value: string | number | null | undefined) {
  return value === null || value === undefined || value === '' ? 'Não informado' : String(value);
}

function safeExternalHref(value: string) {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

function humanKey(value: string) {
  return value.replaceAll('_', ' ').toLowerCase().replace(/^./, (letter) => letter.toUpperCase());
}

function humanAction(value: string) {
  const labels: Record<string, string> = {
    CALL: 'Ligar', EMAIL: 'Enviar e-mail', WHATSAPP: 'Falar pelo WhatsApp', LINKEDIN: 'Abordar pelo LinkedIn', RESEARCH: 'Pesquisar decisor', FOLLOW_UP: 'Fazer acompanhamento',
  };
  return labels[value] ?? humanKey(value);
}

export default function Opportunity360Page(props: { params: Promise<{ opportunityId: string }> }) {
  const { opportunityId } = use(props.params);
  const query = useOpportunity360(opportunityId);

  if (query.isLoading) return <Opportunity360Skeleton />;

  if (query.isError || !query.data) {
    return (
      <div className="space-y-6">
        <Link href="/oportunidades" className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Voltar para oportunidades
        </Link>
        <EmptyState title="Não foi possível abrir esta oportunidade" description="Ela pode não existir neste workspace ou você pode não ter acesso a ela." />
      </div>
    );
  }

  const data = query.data;
  const { opportunity, lead, company, commercial, decision_maker: decisionMaker } = data;
  const openTasks = data.tasks.filter((task) => task.status !== 'COMPLETED' && task.status !== 'CANCELLED');
  const latestFeedback = data.usefulness_feedback[0];

  return (
    <main className="space-y-6">
      <Link href={`/oportunidades/${lead.id}`} className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Voltar para o cliente
      </Link>

      <PageHeader
        eyebrow="CRM · Oportunidade"
        title={company.name || lead.company_name}
        description={`${offerProfileLabel(opportunity.offer_key)}${opportunity.offer_version ? ` · versão ${opportunity.offer_version}` : ''}`}
        actions={<div className="flex flex-wrap gap-2"><Badge variant="secondary" className="px-3 py-1.5 text-sm">{opportunity.score} pontos</Badge><Badge variant="outline" className="px-3 py-1.5 text-sm">{STATUS_LABELS[commercial.status ?? ''] ?? 'Etapa não informada'}</Badge></div>}
      />

      <section aria-label="Resumo da oportunidade" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={<Target aria-hidden="true" />} label="Potencial desta oferta" value={`${opportunity.score} pontos`} hint={`${opportunity.signals_matched.length} sinal(is) favorável(is)`} />
        <MetricCard icon={<UserRound aria-hidden="true" />} label="Responsável" value={data.owner?.name || 'Não atribuído'} hint={data.owner?.assigned_at ? `Desde ${formatDate(data.owner.assigned_at)}` : 'Defina um responsável no CRM'} />
        <MetricCard icon={<CircleDollarSign aria-hidden="true" />} label="Valor" value={commercial.value == null ? 'Não informado' : currency.format(commercial.value)} hint={commercial.expected_close_date ? `Previsão: ${formatDate(commercial.expected_close_date)}` : 'Sem previsão de fechamento'} />
        <MetricCard icon={<CalendarClock aria-hidden="true" />} label="Próxima ação" value={data.next_action?.action ? humanAction(data.next_action.action) : 'Não definida'} hint={data.next_action?.deadline ? formatDate(data.next_action.deadline) : `${openTasks.length} tarefa(s) aberta(s)`} />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]">
        <div className="space-y-6">
          <section aria-labelledby="qualification-title">
            <Card>
              <CardHeader><CardTitle id="qualification-title">Por que esta oportunidade está priorizada</CardTitle><CardDescription>Sinais observados e componentes disponíveis da avaliação comercial.</CardDescription></CardHeader>
              <CardContent className="space-y-5">
                {opportunity.signals_matched.length > 0 ? <div className="flex flex-wrap gap-2">{opportunity.signals_matched.map((signal) => <Badge key={signal} variant="secondary">{signalLabel(signal)}</Badge>)}</div> : <p className="text-sm text-muted-foreground">Nenhum sinal favorável foi persistido nesta avaliação.</p>}
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <SmallMetric label="Aderência ao perfil" value={data.qualification.icp_fit} /><SmallMetric label="Necessidade" value={data.qualification.need} /><SmallMetric label="Intenção" value={data.qualification.intent} /><SmallMetric label="Momento" value={data.qualification.timing} />
                </div>
                {opportunity.evidence.length > 0 && <div><h3 className="text-sm font-medium">Evidências registradas</h3><ul className="mt-2 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">{opportunity.evidence.slice(0, 8).map((evidence, index) => <li key={`${readableEvidence(evidence)}-${index}`} className="rounded-lg border p-3">{readableEvidence(evidence)}</li>)}</ul></div>}
                {Object.keys(opportunity.score_breakdown).length > 0 && <div><h3 className="text-sm font-medium">Composição da pontuação</h3><dl className="mt-2 grid gap-2 sm:grid-cols-2">{Object.entries(opportunity.score_breakdown).slice(0, 8).map(([key, value]) => <div key={key} className="flex items-center justify-between gap-3 rounded-lg bg-muted/50 px-3 py-2 text-sm"><dt className="text-muted-foreground">{humanKey(key)}</dt><dd className="font-medium">{String(value)}</dd></div>)}</dl></div>}
              </CardContent>
            </Card>
          </section>

          <section aria-label="Empresa e decisor" className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2"><Building2 className="h-5 w-5" aria-hidden="true" /> Empresa</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                <dl className="space-y-3"><InfoRow label="Empresa" value={company.name} /><InfoRow label="Segmento" value={company.industry} /><InfoRow label="Localização" value={[company.city, company.state].filter(Boolean).join(', ') || null} icon={<MapPin className="h-4 w-4" aria-hidden="true" />} /><InfoRow label="CNPJ" value={company.cnpj} /></dl>
                {company.website && <a href={safeExternalHref(company.website)} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Abrir site <ExternalLink className="h-4 w-4" aria-hidden="true" /></a>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2"><UserRound className="h-5 w-5" aria-hidden="true" /> Decisor e contato</CardTitle></CardHeader>
              <CardContent>
                {decisionMaker ? <div className="space-y-3 text-sm"><div><p className="font-medium">{decisionMaker.name || 'Nome não informado'}</p><p className="text-muted-foreground">{decisionMaker.title || 'Cargo não informado'}</p></div><dl className="space-y-3">{decisionMaker.email && <InfoRow label="E-mail" value={decisionMaker.email} icon={<Mail className="h-4 w-4" aria-hidden="true" />} />}{decisionMaker.phone && <InfoRow label="Telefone" value={decisionMaker.phone} icon={<Phone className="h-4 w-4" aria-hidden="true" />} />}<InfoRow label="Confiança do contato" value={decisionMaker.contact_confidence == null ? null : `${Math.round(decisionMaker.contact_confidence)}%`} /><InfoRow label="Confiança da identidade" value={decisionMaker.identity_confidence == null ? null : `${Math.round(decisionMaker.identity_confidence)}%`} /></dl></div> : <p className="text-sm text-muted-foreground">Ainda não há um decisor principal confirmado para esta oportunidade.</p>}
              </CardContent>
            </Card>
          </section>

          <section aria-labelledby="work-title">
            <Card>
              <CardHeader><CardTitle id="work-title">Próxima ação e tarefas</CardTitle><CardDescription>Itens operacionais já registrados para este cliente.</CardDescription></CardHeader>
              <CardContent className="space-y-4">
                {data.next_action ? <div className="rounded-xl border bg-muted/30 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium">{humanAction(data.next_action.action)}</p>{data.next_action.deadline && <Badge variant="outline">{formatDate(data.next_action.deadline)}</Badge>}</div><p className="mt-1 text-sm text-muted-foreground">{data.next_action.why}</p></div> : <p className="text-sm text-muted-foreground">Nenhuma próxima ação foi definida.</p>}
                {openTasks.length > 0 ? <ul className="space-y-2">{openTasks.slice(0, 8).map((task) => <li key={task.id} className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><p className="font-medium">{task.title}</p><p className="text-sm text-muted-foreground">{task.description || humanAction(task.task_type)}</p></div><time dateTime={task.due_at ?? undefined} className="shrink-0 text-sm text-muted-foreground">{task.due_at ? formatDate(task.due_at) : 'Sem prazo'}</time></li>)}</ul> : <p className="text-sm text-muted-foreground">Não há tarefas abertas.</p>}
              </CardContent>
            </Card>
          </section>

          <section aria-label="Resultados e qualidade" className="grid gap-6 lg:grid-cols-2">
            <Card><CardHeader><CardTitle>Resultados comerciais</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><dl className="space-y-3"><InfoRow label="Etapa" value={commercial.negotiation_stage ? humanKey(commercial.negotiation_stage) : STATUS_LABELS[commercial.status ?? '']} /><InfoRow label="Situação do contrato" value={commercial.contract_outcome ? humanKey(commercial.contract_outcome) : null} /><InfoRow label="Valor" value={commercial.value == null ? null : currency.format(commercial.value)} /><InfoRow label="Resultados atribuídos" value={String(data.outcomes.length)} /></dl>{data.outcomes.slice(0, 4).map((outcome) => <div key={outcome.id} className="rounded-lg border p-3"><div className="flex items-center justify-between gap-2"><span className="font-medium">{humanKey(outcome.outcome)}</span>{outcome.value > 0 && <span>{currency.format(outcome.value)}</span>}</div><p className="mt-1 text-xs text-muted-foreground">{formatDate(outcome.recorded_at)}</p></div>)}</CardContent></Card>
            <Card><CardHeader><CardTitle>Qualidade percebida pelo time</CardTitle></CardHeader><CardContent>{latestFeedback ? <div className="space-y-2"><Badge variant={latestFeedback.useful ? 'secondary' : 'outline'}>{latestFeedback.useful ? 'Lead considerado útil' : 'Lead considerado não útil'}</Badge>{latestFeedback.reason && <p className="text-sm text-muted-foreground">Motivo: {humanKey(latestFeedback.reason)}</p>}{latestFeedback.detail && <p className="text-sm text-muted-foreground">{latestFeedback.detail}</p>}<p className="text-xs text-muted-foreground">{formatDate(latestFeedback.updated_at || latestFeedback.created_at)}</p></div> : <p className="text-sm text-muted-foreground">Esta oportunidade ainda não recebeu avaliação de utilidade.</p>}</CardContent></Card>
          </section>
        </div>

        <section aria-labelledby="timeline-title" className="min-w-0">
          <Card className="xl:sticky xl:top-6">
            <CardHeader><CardTitle id="timeline-title" className="flex items-center gap-2"><Clock3 className="h-5 w-5" aria-hidden="true" /> Histórico comercial</CardTitle><CardDescription>Eventos reais registrados neste cliente, do mais recente ao mais antigo.</CardDescription></CardHeader>
            <CardContent>{data.timeline.length > 0 ? <ol className="relative space-y-5 border-l pl-5">{data.timeline.map((item) => <li key={`${item.type}:${item.source_entity}:${item.occurred_at ?? ''}`} className="relative"><span className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-background bg-foreground" aria-hidden="true" /><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="text-[10px]">{TIMELINE_LABELS[item.type]}</Badge>{item.occurred_at && <time dateTime={item.occurred_at} className="text-xs text-muted-foreground">{formatDate(item.occurred_at)}</time>}</div><p className="mt-1 text-sm font-medium">{item.title}</p>{item.description && <p className="mt-0.5 break-words text-sm text-muted-foreground">{humanKey(item.description)}</p>}{item.actor?.name && <p className="mt-1 text-xs text-muted-foreground">Por {item.actor.name}</p>}</li>)}</ol> : <p className="text-sm text-muted-foreground">Ainda não há eventos comerciais registrados.</p>}</CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}

function MetricCard({ icon, label, value, hint }: { icon: ReactNode; label: string; value: string; hint: string }) {
  return <Card><CardContent className="p-4"><div className="flex items-center gap-2 text-sm text-muted-foreground">{icon}<span>{label}</span></div><p className="mt-2 truncate text-lg font-semibold" title={value}>{value}</p><p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{hint}</p></CardContent></Card>;
}

function SmallMetric({ label, value }: { label: string; value: number | null | undefined }) {
  return <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-semibold">{value == null ? 'Sem dado suficiente' : `${Math.round(value)} pontos`}</p></div>;
}

function InfoRow({ label, value, icon }: { label: string; value: string | number | null | undefined; icon?: ReactNode }) {
  return <div className="flex items-start justify-between gap-4 border-b pb-2 last:border-b-0 last:pb-0"><dt className="flex items-center gap-1.5 text-muted-foreground">{icon}{label}</dt><dd className="max-w-[62%] break-words text-right font-medium">{valueOrDash(value)}</dd></div>;
}

function Opportunity360Skeleton() {
  return <div className="space-y-6" role="status" aria-label="Carregando oportunidade"><Skeleton className="h-11 w-48" /><div className="space-y-2"><Skeleton className="h-5 w-32" /><Skeleton className="h-9 w-80 max-w-full" /><Skeleton className="h-5 w-64 max-w-full" /></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((item) => <Skeleton key={item} className="h-28" />)}</div><div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]"><Skeleton className="h-[620px]" /><Skeleton className="h-[620px]" /></div><span className="sr-only">Carregando dados comerciais da oportunidade.</span></div>;
}
