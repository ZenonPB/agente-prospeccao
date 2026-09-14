'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertCircle, Percent, Gauge, Handshake } from 'lucide-react';
import type { AnalyticsOverview } from '@/lib/api';
import { cn } from '@/lib/utils';

const STAGE_LABELS: Record<string, string> = {
  NOVO: 'Novos Encontrados', ANALISADO: 'Avaliados pela IA', QUALIFICADO: 'Aptos para Contato',
  DESQUALIFICADO: 'Fora do Perfil', CONTATADO: 'Mensagem Enviada', RESPONDIDO: 'Cliente Respondeu',
  REUNIAO_MARCADA: 'Reunião Agendada', REUNIAO_FEITA: 'Reunião Realizada',
  PROPOSTA_ENVIADA: 'Proposta Enviada', PERDIDO: 'Arquivados',
};
const STAGE_COLORS: Record<string, string> = {
  NOVO: '#3b82f6', ANALISADO: '#8b5cf6', QUALIFICADO: '#22c55e', DESQUALIFICADO: '#94a3b8',
  CONTATADO: '#f59e0b', RESPONDIDO: '#06b6d4', REUNIAO_MARCADA: '#ec4899', REUNIAO_FEITA: '#10b981',
  PROPOSTA_ENVIADA: '#f43f5e', PERDIDO: '#64748b',
};

export function FunnelCard({ overview, activeStatus, onStatusFilter }: {
  overview: AnalyticsOverview;
  activeStatus?: string[];
  onStatusFilter?: (status: string) => void;
}) {
  const maxCount = Math.max(1, ...overview.funnel.map((s) => s.count));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Funil</CardTitle>
        <CardDescription>{onStatusFilter ? 'Clique em uma etapa para filtrar toda a página.' : 'Volume de leads por etapa'}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {overview.funnel.map((stage) => {
          const pct = (stage.count / maxCount) * 100;
          const color = STAGE_COLORS[stage.stage] || '#64748b';
          const selected = activeStatus?.includes(stage.stage);
          return (
            <button
              key={stage.stage}
              type="button"
              disabled={!onStatusFilter}
              onClick={() => onStatusFilter?.(stage.stage)}
              className={cn('flex w-full items-center gap-3 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', onStatusFilter && 'cursor-pointer hover:bg-muted/40', selected && 'bg-primary/5 ring-1 ring-primary/40')}
              aria-pressed={onStatusFilter ? !!selected : undefined}
            >
              <span className="w-20 shrink-0 truncate px-1 text-xs text-muted-foreground sm:w-36 sm:text-sm">{STAGE_LABELS[stage.stage] || stage.stage}</span>
              <span className="relative h-7 flex-1 overflow-hidden rounded-md bg-muted/50">
                <span className="absolute inset-y-0 left-0 rounded-md transition-all" style={{ width: `${Math.max(pct, stage.count > 0 ? 4 : 0)}%`, backgroundColor: color }} />
              </span>
              <span className="w-10 shrink-0 pr-1 text-right text-sm font-medium tabular-nums">{stage.count}</span>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}

const RATES = [
  { key: 'conversion_rate', label: 'Taxa de Fechamento', hint: 'vendas fechadas / clientes aptos' },
  { key: 'response_rate', label: 'Taxa de Resposta', hint: 'clientes que responderam / mensagens enviadas' },
  { key: 'meeting_rate', label: 'Taxa de Agendamento', hint: 'reuniões agendadas / clientes aptos' },
] as const;
export function RatesCard({ overview }: { overview: AnalyticsOverview }) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><Percent className="h-4 w-4 text-muted-foreground" />Taxas Principais</CardTitle></CardHeader><CardContent className="space-y-3">{RATES.map((r) => <div key={r.key} className="flex items-center justify-between"><div><p className="text-sm font-medium">{r.label}</p><p className="text-xs text-muted-foreground">{r.hint}</p></div><span className="text-xl font-bold tabular-nums">{overview[r.key]}%</span></div>)}</CardContent></Card>;
}

const BAND_COLORS = ['#0f766e', '#10b981', '#f59e0b', '#ef4444'];
export function ScoreBandsCard({ overview, activeBuckets, onBucketFilter }: {
  overview: AnalyticsOverview;
  activeBuckets?: string[];
  onBucketFilter?: (bucket: string) => void;
}) {
  const maxCount = Math.max(1, ...overview.leads_by_score_band.map((b) => b.count));
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Gauge className="h-4 w-4 text-muted-foreground" />Acerto por Faixa de Pontuação</CardTitle><CardDescription>{onBucketFilter ? 'Clique em uma faixa para cruzar o filtro com os demais gráficos.' : 'Contratos fechados em cada faixa.'}</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        {overview.leads_by_score_band.map((band, i) => {
          const pct = (band.count / maxCount) * 100;
          const selected = activeBuckets?.includes(band.band);
          return (
            <button key={band.band} type="button" disabled={!onBucketFilter} onClick={() => onBucketFilter?.(band.band)} className={cn('w-full rounded-lg p-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', onBucketFilter && 'hover:bg-muted/40', selected && 'bg-primary/5 ring-1 ring-primary/40')} aria-pressed={onBucketFilter ? !!selected : undefined}>
              <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">{band.band}</span><span className="font-medium tabular-nums">{band.count} · {band.converted} convertido{band.converted === 1 ? '' : 's'} <span className="ml-1 rounded-md bg-muted px-1.5 py-0.5 text-xs">{band.conversion_rate}%</span></span></div>
              <div className="relative mt-1.5 h-5 overflow-hidden rounded-md bg-muted/50"><div className="absolute inset-y-0 left-0 rounded-md" style={{ width: `${Math.max(pct, band.count > 0 ? 4 : 0)}%`, backgroundColor: BAND_COLORS[i] }} /></div>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}

const NEG_STAGE_LABELS_CARD: Record<string, string> = { RD: 'RD — Demonstração', ORCAMENTO: 'Orçamento', RP: 'RP — Proposta' };
const OUTCOME_META: Record<string, { label: string; color: string }> = { APROVADO: { label: 'Aprovado', color: '#22c55e' }, REPROVADO: { label: 'Reprovado', color: '#ef4444' }, EM_ANALISE: { label: 'Em análise', color: '#f59e0b' } };

export function NegotiationCard({ overview, activeStages, activeOutcomes, onStageFilter, onOutcomeFilter }: {
  overview: AnalyticsOverview;
  activeStages?: string[];
  activeOutcomes?: string[];
  onStageFilter?: (stage: string) => void;
  onOutcomeFilter?: (outcome: string) => void;
}) {
  const stageMax = Math.max(1, ...overview.negotiation_distribution.map((s) => s.count));
  const outcomeMax = Math.max(1, ...overview.contracts_by_outcome.map((o) => o.count));
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Handshake className="h-4 w-4 text-muted-foreground" />Negociação</CardTitle><CardDescription>Clique em uma linha para cruzar filtros.</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5"><p className="text-xs font-medium text-muted-foreground">Estágio</p>{overview.negotiation_distribution.map((s) => { const pct = (s.count / stageMax) * 100; const selected = activeStages?.includes(s.stage); return <button key={s.stage} type="button" disabled={!onStageFilter} onClick={() => onStageFilter?.(s.stage)} className={cn('flex w-full items-center gap-3 rounded-md p-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', onStageFilter && 'hover:bg-muted/40', selected && 'bg-primary/5 ring-1 ring-primary/40')} aria-pressed={onStageFilter ? !!selected : undefined}><span className="w-20 shrink-0 truncate text-xs text-muted-foreground sm:w-32 sm:text-sm">{NEG_STAGE_LABELS_CARD[s.stage] || s.stage}</span><span className="relative h-5 flex-1 overflow-hidden rounded-md bg-muted/50"><span className="absolute inset-y-0 left-0 rounded-md bg-violet-400" style={{ width: `${Math.max(pct, s.count > 0 ? 4 : 0)}%` }} /></span><span className="w-10 text-right text-sm font-medium">{s.count}</span></button>; })}</div>
        <div className="space-y-1.5"><p className="text-xs font-medium text-muted-foreground">Resultado do contrato</p>{overview.contracts_by_outcome.map((o) => { const meta = OUTCOME_META[o.outcome] || { label: o.outcome, color: '#64748b' }; const pct = (o.count / outcomeMax) * 100; const selected = activeOutcomes?.includes(o.outcome); return <button key={o.outcome} type="button" disabled={!onOutcomeFilter} onClick={() => onOutcomeFilter?.(o.outcome)} className={cn('flex w-full items-center gap-3 rounded-md p-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', onOutcomeFilter && 'hover:bg-muted/40', selected && 'bg-primary/5 ring-1 ring-primary/40')} aria-pressed={onOutcomeFilter ? !!selected : undefined}><span className="w-20 shrink-0 truncate text-xs text-muted-foreground sm:w-32 sm:text-sm">{meta.label}</span><span className="relative h-5 flex-1 overflow-hidden rounded-md bg-muted/50"><span className="absolute inset-y-0 left-0 rounded-md" style={{ width: `${Math.max(pct, o.count > 0 ? 4 : 0)}%`, backgroundColor: meta.color }} /></span><span className="w-10 text-right text-sm font-medium">{o.count}</span></button>; })}</div>
      </CardContent>
    </Card>
  );
}

export function ChartCardSkeleton({ lines = 5 }: { lines?: number }) { return <Card><CardHeader><Skeleton className="h-5 w-32" /><Skeleton className="h-4 w-48" /></CardHeader><CardContent className="space-y-2.5">{Array.from({ length: lines }).map((_, i) => <div key={i} className="flex items-center gap-3"><Skeleton className="h-4 w-32" /><Skeleton className="h-6 flex-1" /><Skeleton className="h-4 w-8" /></div>)}</CardContent></Card>; }
export function ChartCardError({ title, message }: { title: string; message: string }) { return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent><div className="flex items-center gap-2 text-red-600"><AlertCircle className="h-4 w-4 shrink-0" /><p className="text-sm font-medium">Erro ao carregar</p></div><p className="mt-1 text-xs text-red-500">{message}</p></CardContent></Card>; }
