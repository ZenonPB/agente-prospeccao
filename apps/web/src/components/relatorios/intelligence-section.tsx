'use client';

import { CalendarDays, ExternalLink, Loader2, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useIntelligence } from '@/hooks/use-api';

function formatDate(value: string) {
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium' }).format(new Date(`${value}T12:00:00`));
}

export function IntelligenceSection() {
  const { events, outcomes } = useIntelligence();

  if (events.isLoading || outcomes.isLoading) {
    return <div className="flex items-center justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  if (events.isError || outcomes.isError) {
    return <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">Não foi possível carregar a inteligência comercial agora. Tente novamente mais tarde.</p>;
  }

  const metrics = outcomes.data?.metrics ?? [];
  const eventItems = events.data?.events ?? [];

  return (
    <section className="space-y-4" aria-labelledby="inteligencia-comercial">
      <div>
        <h2 id="inteligencia-comercial" className="font-heading text-lg font-semibold">Inteligência comercial</h2>
        <p className="text-sm text-muted-foreground">Sinais de oportunidade e resultados por oferta.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><CalendarDays className="h-4 w-4 text-primary" />Eventos futuros</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {eventItems.length === 0 ? <p className="text-sm text-muted-foreground">Nenhum evento futuro foi encontrado.</p> : eventItems.slice(0, 6).map((event) => (
              <div key={event.id} className="flex items-start justify-between gap-3 rounded-lg border p-3">
                <div className="min-w-0"><p className="font-medium">{event.name}</p><p className="text-xs text-muted-foreground">{formatDate(event.event_date)} · {event.location || 'Local não informado'}</p></div>
                <a className="shrink-0 text-primary" href={event.source_url} target="_blank" rel="noreferrer" aria-label={`Abrir fonte de ${event.name}`}><ExternalLink className="h-4 w-4" /></a>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><TrendingUp className="h-4 w-4 text-primary" />Resultados por oferta</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {metrics.length === 0 ? <p className="text-sm text-muted-foreground">Ainda não há resultados comerciais registrados.</p> : metrics.map((metric) => (
              <div key={`${metric.offer_key}-${metric.offer_version || 'atual'}`} className="flex items-center justify-between gap-3 rounded-lg border p-3"><div><p className="font-medium">{metric.offer_key}</p><p className="text-xs text-muted-foreground">{metric.won} de {metric.total} conversões · ticket médio R$ {metric.average_ticket.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p></div><strong className="text-emerald-600">{metric.conversion_rate.toLocaleString('pt-BR')}%</strong></div>
            ))}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}