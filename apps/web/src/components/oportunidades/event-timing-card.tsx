'use client';

import { CalendarDays, ExternalLink, Hourglass, Megaphone, Users } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useIntelligenceEvents } from '@/hooks/use-api';
import { offerProfileLabel } from '@/lib/offers';

const windowLabels: Record<string, string> = {
  ideal: 'Bom momento para abordar',
  closing: 'Vale agir logo',
  late: 'Prazo apertado',
  planning: 'Ainda em planejamento',
  early: 'Ainda cedo para abordagem ativa',
  closed: 'Evento já passou',
  unknown: 'Momento ainda incerto',
};

const channelLabels: Record<string, string> = {
  email: 'E-mail',
  phone: 'Telefone',
  whatsapp: 'WhatsApp',
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
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

function eventContext(provenance?: Record<string, unknown>): string | null {
  const intelligence = provenance?.intelligence;
  if (!intelligence || typeof intelligence !== 'object') return null;
  const context = (intelligence as Record<string, unknown>).context;
  if (context === 'mej') return 'Movimento Empresa Júnior';
  if (context === 'sports') return 'Evento esportivo';
  if (context === 'general') return 'Evento ou premiação';
  return null;
}

export function EventTimingCard({ leadId }: { leadId: string }) {
  const eventsQ = useIntelligenceEvents(100, !!leadId);
  const event = eventsQ.data?.events.find((item) => item.lead_id === leadId) ?? null;

  if (eventsQ.isLoading || eventsQ.isError || !event) return null;

  const timing = event.timing ?? {};
  const daysUntil = timingNumber(timing, 'days_until');
  const purchaseWindow = typeof timing.purchase_window === 'string' ? timing.purchase_window : 'unknown';
  const context = eventContext(event.provenance);

  return (
    <Card className="border-l-4 border-l-emerald-500">
      <CardContent className="space-y-4 pt-6">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Oportunidade ligada a um evento</p>
            <p className="mt-1 text-sm font-medium">{offerProfileLabel(event.offer_key)}</p>
          </div>
          {event.action_status === 'ready' ? (
            <Badge className="bg-emerald-100 text-emerald-800">Contato pronto para revisão</Badge>
          ) : event.action_status === 'needs_review' ? (
            <Badge className="bg-amber-100 text-amber-800">Precisa completar informações</Badge>
          ) : null}
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className="space-y-1">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />Evento
            </p>
            <p className="text-sm font-medium leading-snug">{event.name}</p>
            <p className="text-xs text-muted-foreground">{formatEventDate(event.event_date)}{event.location ? ` · ${event.location}` : ''}</p>
          </div>
          <div className="space-y-1">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Users className="h-3.5 w-3.5" aria-hidden="true" />Contexto
            </p>
            <p className="text-sm font-medium">{context ?? 'Ainda em análise'}</p>
            <p className="text-xs text-muted-foreground">A classificação é baseada nas evidências encontradas e pode ser revisada.</p>
          </div>
          <div className="space-y-1">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Hourglass className="h-3.5 w-3.5" aria-hidden="true" />Melhor momento
            </p>
            <p className="text-sm font-medium">{windowLabels[purchaseWindow] ?? 'Momento ainda incerto'}</p>
            {daysUntil != null ? <p className="text-xs text-muted-foreground">{daysUntil >= 0 ? `Faltam ${daysUntil} dias` : 'Evento encerrado'}</p> : null}
          </div>
          <div className="space-y-1">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Megaphone className="h-3.5 w-3.5" aria-hidden="true" />Próximo contato
            </p>
            <p className="text-sm font-medium">{event.recommended_channel ? (channelLabels[event.recommended_channel] ?? event.recommended_channel) : 'A definir'}</p>
            {event.next_action ? <p className="text-xs text-muted-foreground">{event.next_action}</p> : null}
          </div>
        </div>

        {event.source_url ? (
          <a
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            href={event.source_url}
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            Ver a fonte usada para identificar o evento
          </a>
        ) : null}
      </CardContent>
    </Card>
  );
}
