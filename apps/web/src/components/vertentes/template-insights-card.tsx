'use client';

import { TrendingUp, TrendingDown, Minus, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useAnalyticsTemplateInsights, type AnalyticsPeriod } from '@/hooks/use-api';

const SUGGESTION_META = {
  reforcar: {
    label: 'Reforçar peso',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    icon: TrendingUp,
  },
  reduzir: {
    label: 'Reduzir peso',
    className: 'border-red-200 bg-red-50 text-red-700',
    icon: TrendingDown,
  },
  neutro: {
    label: 'Sem ajuste',
    className: 'border-muted bg-muted text-muted-foreground',
    icon: Minus,
  },
} as const;

export function TemplateInsightsCard({ period }: { period?: AnalyticsPeriod }) {
  const { data, isLoading } = useAnalyticsTemplateInsights(period);

  if (isLoading) {
    return <Skeleton className="h-40 w-full" />;
  }

  const actionable = (data?.insights ?? []).filter((i) => i.suggestion !== 'neutro');

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          O que os resultados dizem sobre suas vertentes
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Compara características dos leads que fecharam negócio com as dos que
          foram perdidos. Use como guia ao revisar os pesos — nada muda sem você.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {!data || data.converted_total === 0 ? (
          <p className="flex items-start gap-2 rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            Ainda não há conversões ou perdas suficientes para gerar sugestões.
            Elas aparecem conforme o time trabalha os leads.
          </p>
        ) : actionable.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma característica com desvio relevante até agora
            ({data.converted_total} convertidos × {data.lost_total} perdidos).
          </p>
        ) : (
          <>
            {actionable.map((insight) => {
              const meta = SUGGESTION_META[insight.suggestion];
              const Icon = meta.icon;
              return (
                <div
                  key={insight.label}
                  className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 space-y-1">
                    <p className="truncate text-sm font-medium capitalize">{insight.label}</p>
                    <p className="text-xs text-muted-foreground">
                      Presente em {insight.converted_rate}% dos convertidos ×{' '}
                      {insight.lost_rate}% dos perdidos ({insight.converted} ×{' '}
                      {insight.lost} leads)
                    </p>
                  </div>
                  <Badge variant="outline" className={`shrink-0 gap-1 ${meta.className}`}>
                    <Icon className="h-3 w-3" aria-hidden="true" />
                    {meta.label}
                  </Badge>
                </div>
              );
            })}
            <p className="text-[11px] text-muted-foreground">{data.rationale}</p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
