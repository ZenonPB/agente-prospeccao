'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Filter, AlertCircle } from 'lucide-react';
import type { AnalyticsFunnel, AnalyticsFunnelStage } from '@/lib/api';

const FUNNEL_COLORS = ['#134e4a', '#0f766e', '#0d9488', '#14b8a6', '#2dd4bf'];

function leakLabel(stage: AnalyticsFunnelStage): { continued: string; leaked: string | null } {
  const conv = stage.conversion_rate;
  if (conv == null) return { continued: '—', leaked: null };
  const leaked = Math.round((100 - conv) * 10) / 10;
  return {
    continued: `${conv.toLocaleString('pt-BR')}% seguiram`,
    leaked: leaked > 0 ? `vazou ${leaked.toLocaleString('pt-BR')}%` : null,
  };
}

export function FunnelEndToEndCard({ funnel }: { funnel: AnalyticsFunnel }) {
  if (funnel.total_leads === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Funil ponta-a-ponta</CardTitle>
          <CardDescription>Do achado ao fechamento — onde o funil afina</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertCircle className="h-4 w-4" />
            Sem leads no período. Nenhum dado para exibir.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          Passo a Passo de Vendas (Do Encontro ao Fechamento)
        </CardTitle>
        <CardDescription>
          Acompanhe o caminho dos clientes desde a busca inicial até o contrato fechado.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {funnel.funnel.map((stage, index) => {
          const { continued, leaked } = leakLabel(stage);
          const width = Math.max(stage.share_of_total, stage.count > 0 ? 5 : 0);
          return (
            <div key={stage.key}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate text-sm font-medium">{stage.label}</span>
                <span className="shrink-0 text-sm tabular-nums">
                  <b>{stage.count}</b>
                  <span className="ml-1.5 text-xs text-muted-foreground">
                    {stage.share_of_total.toLocaleString('pt-BR')}% do total
                  </span>
                </span>
              </div>
              <div className="flex justify-center py-1.5">
                <div
                  className="flex h-7 items-center rounded-lg"
                  style={{
                    width: `${width}%`,
                    minWidth: stage.count > 0 ? 20 : 0,
                    backgroundColor: FUNNEL_COLORS[Math.min(index, FUNNEL_COLORS.length - 1)],
                  }}
                  aria-hidden="true"
                />
              </div>
              {index > 0 && (
                <div
                  className={`flex items-center justify-center gap-1 text-[11px] ${
                    leaked ? 'text-red-600' : 'text-muted-foreground'
                  }`}
                >
                  <span>{continued}</span>
                  {leaked && <span className="font-medium">· {leaked}</span>}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export function FunnelEndToEndSkeleton() {
  const widths = ['w-full', 'w-3/4', 'w-2/5', 'w-1/4', 'w-1/6'];
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-4 w-64" />
      </CardHeader>
      <CardContent className="space-y-2">
        {widths.map((width) => (
          <div key={width} className="flex flex-col items-center gap-1.5">
            <Skeleton className="h-4 w-full" />
            <Skeleton className={`h-7 ${width}`} />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}