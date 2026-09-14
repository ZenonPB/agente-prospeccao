'use client';

import { useDeferredValue, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, Building2, CalendarClock, Layers3, Search, Sparkles, Target, UserRound } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import { useOperatingQueue, useOperatingSearch } from '@/hooks/use-sales-operating';
import { offerProfileLabel } from '@/lib/offers';
import type { OperatingSearchItem } from '@/lib/sales-operating-api';

const SEARCH_GROUPS = [
  ['companies', 'Empresas', Building2],
  ['persons', 'Pessoas', UserRound],
  ['leads', 'Leads', Target],
  ['opportunities', 'Oportunidades por oferta', Layers3],
  ['campaigns', 'Campanhas', Sparkles],
] as const;

function SearchGroup({ title, icon: Icon, items }: { title: string; icon: typeof Building2; items: OperatingSearchItem[] }) {
  if (items.length === 0) return null;
  return (
    <section aria-label={title} className="space-y-2">
      <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Icon className="h-4 w-4" aria-hidden="true" />{title}
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <Link key={`${title}-${item.id}`} href={item.href} className="rounded-lg border p-3 transition-colors hover:border-primary/40 hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <p className="truncate text-sm font-medium">{item.title}</p>
            {item.subtitle ? <p className="mt-0.5 truncate text-xs text-muted-foreground">{item.subtitle}</p> : null}
          </Link>
        ))}
      </div>
    </section>
  );
}

function QueueSkeleton() {
  return <div className="space-y-3">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}</div>;
}

export default function CrmHomePage() {
  const [search, setSearch] = useState('');
  const deferredSearch = useDeferredValue(search.trim());
  const queue = useOperatingQueue(20);
  const searchQuery = useOperatingSearch(deferredSearch);
  const groups = searchQuery.data?.groups;
  const visibleResultCount = groups
    ? groups.companies.length + groups.persons.length + groups.leads.length + groups.opportunities.length + groups.campaigns.length
    : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operação comercial"
        title="Central comercial"
        description="Encontre qualquer cliente e veja, em ordem de prioridade, o que precisa da sua atenção hoje."
        actions={<Link href="/crm/operacao" className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-xs transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><Layers3 className="mr-2 h-4 w-4" />Oportunidades</Link>}
      />

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Buscar cliente, pessoa ou oportunidade</CardTitle>
          <CardDescription>Uma busca única no seu workspace. Resultados de outros workspaces nunca aparecem aqui.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Ex.: Acme, Maria, troféus..." className="pl-9" aria-label="Buscar no CRM" autoComplete="off" />
          </div>
          {deferredSearch.length === 1 ? <p className="text-sm text-muted-foreground">Digite mais um caractere para buscar.</p> : null}
          {searchQuery.isLoading && deferredSearch.length >= 2 ? <Skeleton className="h-24 w-full" /> : null}
          {searchQuery.isError ? <div role="alert" className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />Não foi possível concluir a busca agora.</div> : null}
          {groups && visibleResultCount > 0 ? <div className="space-y-5">{SEARCH_GROUPS.map(([key, title, Icon]) => <SearchGroup key={key} title={title} icon={Icon} items={groups[key]} />)}</div> : null}
          {groups && deferredSearch.length >= 2 && visibleResultCount === 0 && !searchQuery.isLoading ? <p className="rounded-lg bg-muted/40 p-4 text-sm text-muted-foreground">Nenhum resultado encontrado neste workspace.</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><CardTitle>O que precisa de você hoje</CardTitle><CardDescription>Prioridade calculada a partir de prazos, estágio, tarefas e recomendações já registradas.</CardDescription></div>
            {queue.data ? <Badge variant="secondary">{queue.data.total} pendência{queue.data.total === 1 ? '' : 's'}</Badge> : null}
          </div>
        </CardHeader>
        <CardContent>
          {queue.isLoading ? <QueueSkeleton /> : queue.isError ? (
            <div role="alert" className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />Não foi possível carregar sua fila. Atualize a página para tentar novamente.</div>
          ) : queue.data?.items.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center"><CalendarClock className="mx-auto h-7 w-7 text-muted-foreground" aria-hidden="true" /><p className="mt-3 font-medium">Tudo em dia</p><p className="mt-1 text-sm text-muted-foreground">Não há ações prioritárias para você neste momento.</p></div>
          ) : (
            <div className="space-y-3">
              {queue.data?.items.map((item, index) => (
                <Link key={item.lead_id} href={`/oportunidades/${item.lead_id}`} className="block rounded-xl border p-4 transition-colors hover:border-primary/40 hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <div className="flex gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">{index + 1}</div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2"><p className="truncate font-medium">{item.company_name}</p>{item.opportunity_score != null ? <Badge variant="secondary">aderência {item.opportunity_score}</Badge> : null}{item.offer_key ? <Badge variant="outline">{offerProfileLabel(item.offer_key)}</Badge> : null}</div>
                      <p className="mt-1 text-sm font-medium text-foreground/80">{item.recommended_action || item.reasons[0]}</p>
                      {item.recommended_why ? <p className="mt-1 text-sm text-muted-foreground">{item.recommended_why}</p> : null}
                      <div className="mt-2 flex flex-wrap gap-1.5">{item.reasons.map((reason) => <span key={reason} className="rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground">{reason}</span>)}</div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
