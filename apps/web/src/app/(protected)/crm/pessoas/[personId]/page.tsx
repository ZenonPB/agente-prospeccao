'use client';

import { use, type ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft, Building2, ExternalLink, Mail, Phone, ShieldCheck, UserRound } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import { CrmMetric, CrmOpportunities, CrmTasks, CrmTimeline, humanCrmKey, safeHref } from '@/components/crm/crm-360-shared';
import { usePerson360 } from '@/hooks/use-crm-360';

export default function Person360Page(props: { params: Promise<{ personId: string }> }) {
  const { personId } = use(props.params);
  const query = usePerson360(personId);

  if (query.isLoading) return <PersonSkeleton />;
  if (query.isError || !query.data) {
    return <div className="space-y-6"><Back /><EmptyState title="Não foi possível abrir esta pessoa" description="Ela pode não existir neste workspace ou não pertencer à sua carteira." /></div>;
  }

  const data = query.data;
  const person = data.person;
  const company = data.company;
  return (
    <main className="space-y-6">
      <Back companyId={company?.id} />
      <PageHeader
        eyebrow="CRM · Pessoa"
        title={person.name}
        description={[person.role_label || humanCrmKey(person.role), company?.company_name].filter(Boolean).join(' · ')}
        actions={<div className="flex flex-wrap gap-2"><Badge variant={person.routable ? 'secondary' : 'outline'}>{person.routable ? 'Contato acionável' : 'Contato a revisar'}</Badge>{person.email_verified && <Badge variant="outline">E-mail verificado</Badge>}</div>}
      />

      <section aria-label="Resumo do contato" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <CrmMetric label="Confiança da identidade" value={`${Math.round(person.identity_confidence ?? 0)}%`} />
        <CrmMetric label="Confiança do contato" value={`${Math.round(person.contact_confidence ?? 0)}%`} />
        <CrmMetric label="Oportunidades relacionadas" value={String(data.summary.opportunity_count)} hint={data.summary.best_opportunity_score == null ? 'Sem score disponível' : `Melhor score: ${data.summary.best_opportunity_score} pontos`} />
        <CrmMetric label="Tarefas abertas" value={String(data.summary.open_task_count)} />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]">
        <div className="space-y-6">
          <section className="grid gap-6 lg:grid-cols-2" aria-label="Contato e empresa">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2"><UserRound className="h-5 w-5" aria-hidden="true" /> Contato</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                <dl className="space-y-3">
                  <Info label="Cargo" value={person.role_label || humanCrmKey(person.role)} />
                  <Info label="E-mail" value={person.email} icon={<Mail className="h-4 w-4" />} />
                  <Info label="Telefone" value={person.phone} icon={<Phone className="h-4 w-4" />} />
                  <Info label="Verificação" value={humanCrmKey(person.verification_status)} icon={<ShieldCheck className="h-4 w-4" />} />
                  <Info label="Roteabilidade" value={humanCrmKey(person.routability_type)} />
                  <Info label="Fonte" value={person.source} />
                </dl>
                {person.linkedin_url && <a href={safeHref(person.linkedin_url)} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 rounded-md border px-3 font-medium outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">Abrir LinkedIn <ExternalLink className="h-4 w-4" aria-hidden="true" /></a>}
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2"><Building2 className="h-5 w-5" aria-hidden="true" /> Empresa</CardTitle></CardHeader>
              <CardContent>
                {company ? <div className="space-y-3 text-sm"><p className="text-lg font-semibold">{company.company_name}</p><p className="text-muted-foreground">{[company.category, company.city, company.state].filter(Boolean).join(' · ') || 'Sem classificação adicional'}</p><Link href={`/crm/empresas/${company.id}`} className="inline-flex min-h-11 items-center rounded-md border px-3 font-medium outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">Abrir visão da empresa</Link></div> : <p className="text-sm text-muted-foreground">Esta pessoa ainda não está vinculada a uma empresa canônica.</p>}
              </CardContent>
            </Card>
          </section>

          <CrmOpportunities opportunities={data.opportunities} />
          <CrmTasks tasks={data.tasks} />
        </div>
        <aside aria-label="Histórico da pessoa"><CrmTimeline items={data.timeline} /></aside>
      </div>
    </main>
  );
}

function Back({ companyId }: { companyId?: string }) {
  return <Link href={companyId ? `/crm/empresas/${companyId}` : '/oportunidades'} className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> {companyId ? 'Voltar para a empresa' : 'Voltar para oportunidades'}</Link>;
}

function Info({ label, value, icon }: { label: string; value: string | number | null | undefined; icon?: ReactNode }) {
  return <div className="flex items-start justify-between gap-4 border-b pb-2 last:border-b-0"><dt className="flex items-center gap-1.5 text-muted-foreground">{icon}{label}</dt><dd className="max-w-[62%] break-words text-right font-medium">{value ?? 'Não informado'}</dd></div>;
}

function PersonSkeleton() {
  return <div className="space-y-6" role="status" aria-label="Carregando pessoa"><Skeleton className="h-11 w-48" /><Skeleton className="h-24 w-full" /><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((item) => <Skeleton key={item} className="h-28" />)}</div><div className="grid gap-6 xl:grid-cols-2"><Skeleton className="h-[540px]" /><Skeleton className="h-[540px]" /></div><span className="sr-only">Carregando visão consolidada da pessoa.</span></div>;
}
