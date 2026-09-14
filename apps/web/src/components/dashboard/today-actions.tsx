'use client';

import Link from 'next/link';
import { AlertCircle, CalendarClock } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useOperatingQueue } from '@/hooks/use-sales-operating';

function formatDue(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date);
}

export function TodayActions() {
  const queue = useOperatingQueue(6);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle>O que precisa de você hoje</CardTitle>
          {queue.data ? <Badge variant="secondary">{queue.data.total}</Badge> : null}
        </div>
      </CardHeader>
      <CardContent>
        {queue.isLoading ? (
          <div className="space-y-2">{[1, 2, 3].map((item) => <Skeleton key={item} className="h-16 w-full rounded-lg" />)}</div>
        ) : queue.isError ? (
          <div role="alert" className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />Fila indisponível no momento.
          </div>
        ) : queue.data?.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Tudo em dia. Nenhuma ação prioritária agora.</p>
        ) : (
          <div className="space-y-2">
            {queue.data?.items.map((item) => (
              <Link
                key={item.lead_id}
                href={`/oportunidades/${item.lead_id}`}
                className="block rounded-lg border p-3 transition-colors hover:border-primary/40 hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.company_name}</p>
                    <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{item.recommended_action || item.reasons[0]}</p>
                  </div>
                  {item.opportunity_score != null ? <Badge variant="secondary" className="shrink-0">{item.opportunity_score}</Badge> : null}
                </div>
                {item.due_at ? (
                  <p className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
                    <CalendarClock className="h-3 w-3" aria-hidden="true" />{formatDue(item.due_at)}
                  </p>
                ) : null}
              </Link>
            ))}
            <Link href="/crm" className="block pt-1 text-center text-xs font-medium text-primary hover:underline">Ver toda a fila comercial</Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
