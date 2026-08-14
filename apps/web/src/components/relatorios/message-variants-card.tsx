'use client';

import { FlaskConical } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useAnalyticsMessageVariants, type AnalyticsPeriod } from '@/hooks/use-api';

interface Props {
  period: AnalyticsPeriod;
}

export function MessageVariantsCard({ period }: Props) {
  const q = useAnalyticsMessageVariants(period);

  if (q.isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-56" />
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (q.isError || !q.data) return null;

  const variants = q.data.variants;
  if (variants.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-muted-foreground" />
            A/B de mensagens
          </CardTitle>
          <CardDescription>
            Marque uma variante (A/B) em uma etapa da cadência para começar a medir.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const winner = variants.length > 1
    ? variants.reduce((acc, v) => (v.response_rate > acc.response_rate ? v : acc), variants[0])
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-muted-foreground" />
          A/B de mensagens
        </CardTitle>
        <CardDescription>
          Resposta por variante de cadência no período
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {variants.map((v) => {
          const isWinner = winner && v.variant === winner.variant && variants.length > 1;
          return (
            <div
              key={v.variant}
              className={
                'flex items-center justify-between rounded-md border px-3 py-2 ' +
                (isWinner ? 'border-emerald-300 bg-emerald-50 dark:bg-emerald-900/20' : 'border-border')
              }
            >
              <div>
                <p className="text-sm font-semibold">Variante {v.variant}</p>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {v.sent} enviadas · {v.opened} aberturas · {v.clicked} cliques · {v.responded} respostas
                </p>
              </div>
              <div className="text-right text-sm">
                <p className="font-medium tabular-nums">{v.response_rate}%</p>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {v.open_rate}% abertura · {v.click_rate}% cliques
                </p>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
