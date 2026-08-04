'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertCircle, Percent, Gauge } from 'lucide-react';
import type { AnalyticsOverview } from '@/lib/api';

const STAGE_LABELS: Record<string, string> = {
  NOVO: 'Encontrados',
  ANALISADO: 'Analisados',
  QUALIFICADO: 'Aptos',
  DESQUALIFICADO: 'Desqualificados',
  CONTATADO: 'Mensagem enviada',
  RESPONDIDO: 'Respondeu',
  REUNIAO_MARCADA: 'Reunião marcada',
  REUNIAO_FEITA: 'Reunião realizada',
  PROPOSTA_ENVIADA: 'Proposta enviada',
  PERDIDO: 'Perdidos',
};

const STAGE_COLORS: Record<string, string> = {
  NOVO: '#3b82f6', ANALISADO: '#8b5cf6', QUALIFICADO: '#22c55e', DESQUALIFICADO: '#94a3b8',
  CONTATADO: '#f59e0b', RESPONDIDO: '#06b6d4', REUNIAO_MARCADA: '#ec4899', REUNIAO_FEITA: '#10b981',
  PROPOSTA_ENVIADA: '#f43f5e', PERDIDO: '#64748b',
};

export function FunnelCard({ overview }: { overview: AnalyticsOverview }) {
  const maxCount = Math.max(1, ...overview.funnel.map((s) => s.count));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Funil</CardTitle>
        <CardDescription>Volume de leads por etapa</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {overview.funnel.map((stage) => {
          const pct = (stage.count / maxCount) * 100;
          const color = STAGE_COLORS[stage.stage] || '#64748b';
          return (
            <div key={stage.stage} className="flex items-center gap-3">
              <span className="w-36 shrink-0 truncate text-sm text-muted-foreground">
                {STAGE_LABELS[stage.stage] || stage.stage}
              </span>
              <div className="relative h-7 flex-1 overflow-hidden rounded-md bg-muted/50">
                <div
                  className="absolute inset-y-0 left-0 rounded-md transition-all"
                  style={{ width: `${Math.max(pct, stage.count > 0 ? 4 : 0)}%`, backgroundColor: color }}
                />
              </div>
              <span className="w-10 shrink-0 text-right text-sm font-medium tabular-nums">
                {stage.count}
              </span>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

const RATES = [
  { key: 'conversion_rate', label: 'Conversão', hint: 'convertidos / qualificados' },
  { key: 'response_rate', label: 'Resposta', hint: 'responderam / contatados' },
  { key: 'meeting_rate', label: 'Reunião', hint: 'reuniões / qualificados' },
] as const;

export function RatesCard({ overview }: { overview: AnalyticsOverview }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Percent className="h-4 w-4 text-muted-foreground" />
          Taxas
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {RATES.map((r) => (
          <div key={r.key} className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">{r.label}</p>
              <p className="text-xs text-muted-foreground">{r.hint}</p>
            </div>
            <span className="text-xl font-bold tabular-nums">
              {overview[r.key]}%
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

const BAND_COLORS = ['#0f766e', '#10b981', '#f59e0b', '#ef4444'];

export function ScoreBandsCard({ overview }: { overview: AnalyticsOverview }) {
  const maxCount = Math.max(1, ...overview.leads_by_score_band.map((b) => b.count));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-4 w-4 text-muted-foreground" />
          Score
        </CardTitle>
        <CardDescription>Taxa de acerto por faixa de pontuação</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {overview.leads_by_score_band.map((band, i) => {
          const pct = (band.count / maxCount) * 100;
          const convPct = band.conversion_rate;
          const convBarPct = band.count > 0 ? (band.converted / band.count) * 100 : 0;
          return (
            <div key={band.band} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{band.band}</span>
                <span className="font-medium tabular-nums">
                  {band.count}
                  <span className="mx-1.5 text-muted-foreground/60">·</span>
                  {band.converted} convertido{band.converted === 1 ? '' : 's'}
                  <span className="ml-1.5 rounded-md bg-muted px-1.5 py-0.5 text-xs font-medium tabular-nums">
                    {convPct}%
                  </span>
                </span>
              </div>
              <div className="relative h-6 overflow-hidden rounded-md bg-muted/50">
                <div
                  className="absolute inset-y-0 left-0 rounded-md"
                  style={{ width: `${Math.max(pct, band.count > 0 ? 4 : 0)}%`, backgroundColor: BAND_COLORS[i] }}
                  aria-hidden="true"
                />
                {band.converted > 0 && (
                  <div
                    className="absolute inset-y-0 left-0 rounded-l-md bg-emerald-500/80"
                    style={{ width: `${Math.max(convBarPct, 2)}%` }}
                    aria-hidden="true"
                  />
                )}
              </div>
              <p className="text-[11px] text-muted-foreground">
                {band.converted === 0
                  ? 'Sem conversões nesta faixa'
                  : `${convPct}% dos leads desta faixa foram convertidos`}
              </p>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export function ChartCardSkeleton({ lines = 5 }: { lines?: number }) {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-4 w-48" />
      </CardHeader>
      <CardContent className="space-y-2.5">
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-6 flex-1" />
            <Skeleton className="h-4 w-8" />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function ChartCardError({ title, message }: { title: string; message: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 text-red-600">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="text-sm font-medium">Erro ao carregar</p>
        </div>
        <p className="mt-1 text-xs text-red-500">{message}</p>
      </CardContent>
    </Card>
  );
}
