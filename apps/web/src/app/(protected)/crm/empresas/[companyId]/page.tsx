'use client';

import { use, type ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft, Building2, ExternalLink, MapPin, Phone, Star, UserRound } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import { CrmMetric, CrmOpportunities, CrmTasks, CrmTimeline, humanCrmKey, safeHref } from '@/components/crm/crm-360-shared';
import { useCompany360 } from '@/hooks/use-crm-360';

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

export default function Company360Page(props: { params: Promise<{ companyId: string }> }) {
  const { companyId } = use(props.params);
  const query = useCompany360(companyId);

  if (query.isLoading) return <CompanySkeleton />;
  if (query.isError || !query.data) {
    return <div className="space-y-6"><Back /><EmptyState title="Não foi possível abrir esta empresa" description="Ela pode não existir neste workspace ou não pertencer à sua carteira." /></div>;
  }

  const data = query.data;
  const company = data.company;
  return (
    <main className="space-y-6">
      <Back />
      <PageHeader
        eyebrow="CRM · Empresa"
        title={company.company_name}
        description={[company.category, company.city, company.state].filter(Boolean).join(' · ') || 'Conta consolidada do workspace'}
        actions={<Badge variant="secondary" className="px-3 py-1.5">{data.summary.opportunity_count} oportunidade(s)</Badge>}
      />

      <section aria-label="Resumo da conta" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <CrmMetric label="Pessoas conhecidas" value={String(data.summary.person_count)} hint="Decisores e contatos canônicos" />
        <CrmMetric label="Oportunidades" value={String(data.summary.opportunity_count)} hint={data.summary.best_opportunity_score == null ? 'Ainda sem avaliação' : `Melhor score: ${data.summary.best_opportunity_score} pontos`} />
        <CrmMetric label="Tarefas abertas" value={String(data.summary.open_task_count)} hint="Itens comerciais pendentes" />
        <CrmMetric label="Receita ganha" value={money.format(data.summary.won_value)} hint="Outcomes WON atribuídos à conta" />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]">
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><Building2 className="h-5 w-5" aria-hidden="true" /> Dados da empresa</CardTitle></CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <dl className="space-y-3 text-sm">
                <Info label="CNPJ" value={company.cnpj} />
                <Info label="Segmento" value={company.category} />
                <Info label="Localização" value={[company.city, company.state, company.country].filter(Boolean).join(', ') || null} icon={<MapPin className="h-4 w-4" />} />
                <Info label="Telefone" value={company.phone} icon={<Phone className="h-4 w-4" />} />
                <Info label="Avaliação Google" value={company.google_rating == null ? null : `${company.google_rating.toFixed(1)} · ${company.google_rating_count ?? 0} avaliações`} icon={<Star className="h-4 w-4" />} />
              </dl>
              <div className="flex flex-wrap content-start gap-2">
                {company.website && <ExternalLinkButton href={company.website}>Site</ExternalLinkButton>}
                {company.linkedin_url && <ExternalLinkButton href={company.linkedin_url}>LinkedIn</ExternalLinkButton>}
                {company.instagram_url && <ExternalLinkButton href={company.instagram_url}>Instagram</ExternalLinkButton>}
                {company.google_maps_uri && <ExternalLinkButton href={company.google_maps_uri}>Google Maps</ExternalLinkButton>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><UserRound className="h-5 w-5" aria-hidden="true" /> Pessoas</CardTitle></CardHeader>
            <CardContent>
              {data.persons.length === 0 ? <p className="text-sm text-muted-foreground">Nenhuma pessoa canônica vinculada a esta empresa.</p> : (
                <ul className="grid gap-3 md:grid-cols-2">
                  {data.persons.map((person) => (
                    <li key={person.id}>
                      <Link href={`/crm/pessoas/${person.id}`} className="block rounded-lg border p-3 outline-none transition-colors hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring">
                        <div className="flex items-start justify-between gap-3"><div><p className="font-medium">{person.name}</p><p className="text-sm text-muted-foreground">{person.role_label || humanCrmKey(person.role)}</p></div>{person.routable && <Badge variant="secondary">Acionável</Badge>}</div>
                        <p className="mt-2 text-xs text-muted-foreground">Confiança do contato: {Math.round(person.contact_confidence ?? 0)}%</p>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <CrmOpportunities opportunities={data.opportunities} />
          <CrmTasks tasks={data.tasks} />
        </div>
        <aside aria-label="Histórico da empresa"><CrmTimeline items={data.timeline} /></aside>
      </div>
    </main>
  );
}

function Back() {
  return <Link href="/oportunidades" className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Voltar para oportunidades</Link>;
}

function Info({ label, value, icon }: { label: string; value: string | number | null | undefined; icon?: ReactNode }) {
  return <div className="flex items-start justify-between gap-4 border-b pb-2 last:border-b-0"><dt className="flex items-center gap-1.5 text-muted-foreground">{icon}{label}</dt><dd className="max-w-[62%] break-words text-right font-medium">{value ?? 'Não informado'}</dd></div>;
}

function ExternalLinkButton({ href, children }: { href: string; children: ReactNode }) {
  return <a href={safeHref(href)} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 rounded-md border px-3 text-sm font-medium outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">{children}<ExternalLink className="h-4 w-4" aria-hidden="true" /></a>;
}

function CompanySkeleton() {
  return <div className="space-y-6" role="status" aria-label="Carregando empresa"><Skeleton className="h-11 w-48" /><Skeleton className="h-24 w-full" /><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((item) => <Skeleton key={item} className="h-28" />)}</div><div className="grid gap-6 xl:grid-cols-2"><Skeleton className="h-[620px]" /><Skeleton className="h-[620px]" /></div><span className="sr-only">Carregando visão consolidada da empresa.</span></div>;
}
