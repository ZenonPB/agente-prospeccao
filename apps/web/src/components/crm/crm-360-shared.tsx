import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Clock3, ListTodo, Target } from 'lucide-react';
import { offerProfileLabel, signalLabel } from '@/lib/offers';
import type { Crm360Opportunity, Crm360Task, Crm360TimelineItem } from '@/types/crm-360';

const dateTime = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium', timeStyle: 'short' });

export function formatCrmDate(value: string | null | undefined) {
  if (!value) return 'Não informado';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Não informado' : dateTime.format(parsed);
}

export function humanCrmKey(value: string | null | undefined) {
  if (!value) return 'Não informado';
  return value.replaceAll('_', ' ').toLowerCase().replace(/^./, (letter) => letter.toUpperCase());
}

export function safeHref(value: string) {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

export function CrmMetric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="mt-1 truncate text-xl font-semibold" title={value}>{value}</p>
        {hint && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

export function CrmOpportunities({ opportunities }: { opportunities: Crm360Opportunity[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Target className="h-5 w-5" aria-hidden="true" /> Oportunidades</CardTitle>
        <CardDescription>Ofertas avaliadas a partir dos sinais já persistidos.</CardDescription>
      </CardHeader>
      <CardContent>
        {opportunities.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma oportunidade avaliada.</p>
        ) : (
          <ul className="space-y-2">
            {opportunities.slice(0, 12).map((item) => (
              <li key={item.id}>
                <Link href={`/oportunidades/360/${item.id}`} className="block rounded-lg border p-3 outline-none transition-colors hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{offerProfileLabel(item.offer_key)}</span>
                    <Badge variant="secondary">{item.score} pontos</Badge>
                  </div>
                  {item.signals_matched.length > 0 && (
                    <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                      {item.signals_matched.slice(0, 3).map(signalLabel).join(' · ')}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function CrmTasks({ tasks }: { tasks: Crm360Task[] }) {
  const open = tasks.filter((item) => item.status !== 'COMPLETED' && item.status !== 'CANCELLED');
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><ListTodo className="h-5 w-5" aria-hidden="true" /> Tarefas abertas</CardTitle>
        <CardDescription>Próximos trabalhos já materializados no CRM.</CardDescription>
      </CardHeader>
      <CardContent>
        {open.length === 0 ? <p className="text-sm text-muted-foreground">Nenhuma tarefa aberta.</p> : (
          <ul className="space-y-2">
            {open.slice(0, 10).map((item) => (
              <li key={item.id} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div><p className="font-medium">{item.title}</p>{item.description && <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>}</div>
                  <Badge variant="outline">{humanCrmKey(item.status)}</Badge>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{item.due_at ? `Prazo: ${formatCrmDate(item.due_at)}` : 'Sem prazo definido'}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function CrmTimeline({ items }: { items: Crm360TimelineItem[] }) {
  return (
    <Card className="xl:sticky xl:top-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Clock3 className="h-5 w-5" aria-hidden="true" /> Histórico comercial</CardTitle>
        <CardDescription>Eventos persistidos, do mais recente ao mais antigo.</CardDescription>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? <p className="text-sm text-muted-foreground">Ainda não há eventos comerciais registrados.</p> : (
          <ol className="relative space-y-5 border-l pl-5">
            {items.slice(0, 100).map((item) => (
              <li key={`${item.type}:${item.source_entity}:${item.occurred_at ?? ''}`} className="relative">
                <span className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-background bg-foreground" aria-hidden="true" />
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="text-[10px]">{humanCrmKey(item.type)}</Badge>
                  {item.occurred_at && <time dateTime={item.occurred_at} className="text-xs text-muted-foreground">{formatCrmDate(item.occurred_at)}</time>}
                </div>
                <p className="mt-1 text-sm font-medium">{humanCrmKey(item.title)}</p>
                {item.description && <p className="mt-0.5 break-words text-sm text-muted-foreground">{item.description}</p>}
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
