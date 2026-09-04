'use client';

import { Badge } from '@/components/ui/badge';
import { Lightbulb } from 'lucide-react';

/**
 * Sinais explicativos do card ("por que prospectar", doc 16): 3–5 evidências
 * fortes vindas do scoring — cada chip é o title de um item de `evidence`
 * real, portanto rastreável por construção. Nada é inferido aqui: se o lead
 * não tem evidência, o card não afirma nada.
 */
export function WhyProspectSignals({ signals }: { signals?: string[] }) {
  if (!signals?.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Lightbulb className="h-3.5 w-3.5 shrink-0 text-amber-500" aria-hidden="true" />
      {signals.slice(0, 5).map((signal) => (
        <Badge
          key={signal}
          variant="outline"
          className="max-w-full truncate text-xs font-normal"
          title={signal}
        >
          {signal}
        </Badge>
      ))}
    </div>
  );
}
