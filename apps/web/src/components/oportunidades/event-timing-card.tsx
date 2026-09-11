'use client';

import { CalendarDays, ExternalLink, Hourglass, Megaphone } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useIntelligenceEvents } from '@/hooks/use-api';

const urgencyLabels: Record<string, string> = {
  today: 'hoje',
  high: 'alta',
  medium: 'média',
  low: 'baixa',
  very_low: 'muito baixa',
  expired: 'expirado',
  unknown: 'indefinida',
};

const channelLabels: Record<string, string> = {
  email: 'E-mail',
  phone: 'Telefone',
  whatsapp: 'WhatsApp',
  instagram: 'Instagram',
};

function timingNumber(timing: Record<string, unknown>, key: string): number | null {
  const value = timing[key];
  return typeof value === 'number' ? value : null;
}

function formatEventDate(iso: string): string {
  const parsed = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleDateString('pt-BR');
}

// Card "Evento → timing → canal" para leads vindos de evento: usa o endpoint
// de inteligência já existente (filtrado pelo lead) em vez de inventar dado.
export function EventTimingCard({ leadId }: { leadId: string }) {
  const eventsQ = useIntelligenceEvents(100, !!leadId);
  const event = eventsQ.data?.events.find((item) => item.lead_id === leadId) ?? null;

  if (eventsQ.isLoading || eventsQ.isError || !event) return null;

  const timing = event.timing ?? {};
  const daysUntil = timingNumber(timing, 'days_until');
  const timingScore = timingNumber(timing, 'timing_score');
  const urgencyRaw = typeof timing.urgency === 'string' ? timing.urgency : 'unknown';
  const timingText =
    daysUntil != null
      ? `faltam ${daysUntil} dias · urgência ${urgencyLabels[urgencyRaw] ?? urgencyRaw}`
      : `urgência ${urgencyLabels[urgencyRaw] ?? urgencyRaw}`;

  return (
    <Card className="border-l-4 border-l-emerald-500">
      <CardContent className="space-y-3 pt-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Oportunidade de evento
          </span>
          {event.action_status === 'ready' ? (
            <Badge className="bg-emerald-100 text-emerald-800">Pronto para abordar</Badge>
          ) : event.action_status === 'needs_review' ? (
            <Badge className="bg-amber-100 text-amber-800">Precisa de revisão</Badge>
          ) : null}
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
              Evento
            </p>
            <p className="text-sm font-medium leading-snug">{event.name}</p>
            <p className="text-xs text-muted-foreground">
              {formatEventDate(event.event_date)}
              {event.location ? ` · ${event.location}` : ''}
            </p>
          </div>
          <div className="space-y-1">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Hourglass className="h-3.5 w-3.5" aria-hidden="true" />
              Timing
            </p>
            <p className="text-sm font-medium leading-snug">{timingText}</p>
            {timingScore != null && (
              <p className="text-xs text-muted-foreground">score de timing {timingScore}/100</p>
            )}
          </div>
          <div className="space-y-1">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Megaphone className="h-3.5 w-3.5" aria-hidden="true" />
              Canal
            </p>
            <p className="text-sm font-medium leading-snug">
              {event.recommended_channel
                ? (channelLabels[event.recommended_channel] ?? event.recommended_channel)
                : 'A definir'}
            </p>
            {event.next_action && (
              <p className="text-xs text-muted-foreground">{event.next_action}</p>
            )}
          </div>
        </div>
        {event.source_url && (
          <a
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            href={event.source_url}
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            Abrir fonte do evento
          </a>
        )}
      </CardContent>
    </Card>
  );
}
