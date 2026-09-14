'use client';

import { use, useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft, Building2, ExternalLink, MapPin, Pencil, Phone, Star, UserRound } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import { CrmMetric, CrmOpportunities, CrmTasks, CrmTimeline, humanCrmKey, safeHref } from '@/components/crm/crm-360-shared';
import { useCompany360, useUpdateCompany360 } from '@/hooks/use-crm-360';
import { useOrgMembership } from '@/hooks/use-api';

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

type FormState = {
  company_name: string; name: string; category: string; website: string; phone: string;
  address: string; city: string; state: string; country: string; company_linkedin_url: string; instagram_url: string;
};

const emptyForm: FormState = { company_name: '', name: '', category: '', website: '', phone: '', address: '', city: '', state: '', country: '', company_linkedin_url: '', instagram_url: '' };

export default function Company360Page(props: { params: Promise<{ companyId: string }> }) {
  const { companyId } = use(props.params);
  const query = useCompany360(companyId);
  const update = useUpdateCompany360(companyId);
  const membership = useOrgMembership();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);

  const canEdit = membership.data?.membership?.sales_role !== 'ANALYST';
  const company = query.data?.company;
  useEffect(() => {
    if (!company || !editing) return;
    setForm({
      company_name: company.company_name ?? '', name: company.name ?? '', category: company.category ?? '',
      website: company.website ?? '', phone: company.phone ?? '', address: company.address ?? '', city: company.city ?? '',
      state: company.state ?? '', country: company.country ?? '', company_linkedin_url: company.linkedin_url ?? '', instagram_url: company.instagram_url ?? '',
    });
  }, [company, editing]);

  if (query.isLoading) return <CompanySkeleton />;
  if (query.isError || !query.data) return <div className="space-y-6"><Back /><EmptyState title="Não foi possível abrir esta empresa" description="Ela pode não existir neste workspace ou não pertencer à sua carteira." /></div>;

  const data = query.data;
  const current = data.company;
  const save = async () => {
    if (!current.updated_at) return toast.error('Recarregue a empresa antes de editar.');
    if (!form.company_name.trim()) return toast.error('O nome da empresa é obrigatório.');
    try {
      await update.mutateAsync({ expected_updated_at: current.updated_at, ...form });
      setEditing(false);
      toast.success('Empresa atualizada.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar a empresa.');
    }
  };

  return (
    <main className="space-y-6">
      <Back />
      <PageHeader
        eyebrow="CRM · Empresa"
        title={current.company_name}
        description={[current.category, current.city, current.state].filter(Boolean).join(' · ') || 'Conta consolidada do workspace'}
        actions={<div className="flex flex-wrap gap-2">{canEdit ? <Button variant="outline" onClick={() => setEditing(true)}><Pencil className="mr-2 h-4 w-4" />Editar empresa</Button> : null}<Badge variant="secondary" className="px-3 py-1.5">{data.summary.opportunity_count} oportunidade(s)</Badge></div>}
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
                <Info label="CNPJ" value={current.cnpj} />
                <Info label="Segmento" value={current.category} />
                <Info label="Localização" value={[current.city, current.state, current.country].filter(Boolean).join(', ') || null} icon={<MapPin className="h-4 w-4" />} />
                <Info label="Telefone" value={current.phone} icon={<Phone className="h-4 w-4" />} />
                <Info label="Avaliação Google" value={current.google_rating == null ? null : `${current.google_rating.toFixed(1)} · ${current.google_rating_count ?? 0} avaliações`} icon={<Star className="h-4 w-4" />} />
              </dl>
              <div className="flex flex-wrap content-start gap-2">
                {current.website && <ExternalLinkButton href={current.website}>Site</ExternalLinkButton>}
                {current.linkedin_url && <ExternalLinkButton href={current.linkedin_url}>LinkedIn</ExternalLinkButton>}
                {current.instagram_url && <ExternalLinkButton href={current.instagram_url}>Instagram</ExternalLinkButton>}
                {current.google_maps_uri && <ExternalLinkButton href={current.google_maps_uri}>Google Maps</ExternalLinkButton>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><UserRound className="h-5 w-5" aria-hidden="true" /> Pessoas</CardTitle></CardHeader>
            <CardContent>
              {data.persons.length === 0 ? <p className="text-sm text-muted-foreground">Nenhuma pessoa canônica vinculada a esta empresa.</p> : (
                <ul className="grid gap-3 md:grid-cols-2">{data.persons.map((person) => <li key={person.id}><Link href={`/crm/pessoas/${person.id}`} className="block rounded-lg border p-3 outline-none transition-colors hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring"><div className="flex items-start justify-between gap-3"><div><p className="font-medium">{person.name}</p><p className="text-sm text-muted-foreground">{person.role_label || humanCrmKey(person.role)}</p></div>{person.routable && <Badge variant="secondary">Acionável</Badge>}</div><p className="mt-2 text-xs text-muted-foreground">Confiança do contato: {Math.round(person.contact_confidence ?? 0)}%</p></Link></li>)}</ul>
              )}
            </CardContent>
          </Card>
          <CrmOpportunities opportunities={data.opportunities} />
          <CrmTasks tasks={data.tasks} />
        </div>
        <aside aria-label="Histórico da empresa"><CrmTimeline items={data.timeline} /></aside>
      </div>

      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader><DialogTitle>Editar empresa canônica</DialogTitle><DialogDescription>CNPJ permanece protegido como chave forte de identidade. As alterações são auditadas e usam concorrência otimista.</DialogDescription></DialogHeader>
          <div className="grid gap-3 sm:grid-cols-2">
            {([
              ['company_name', 'Nome da empresa'], ['name', 'Nome fantasia'], ['category', 'Segmento'], ['website', 'Site'], ['phone', 'Telefone'],
              ['address', 'Endereço'], ['city', 'Cidade'], ['state', 'Estado'], ['country', 'País'], ['company_linkedin_url', 'LinkedIn'], ['instagram_url', 'Instagram'],
            ] as Array<[keyof FormState, string]>).map(([key, label]) => <label key={key} className={key === 'address' ? 'space-y-1 sm:col-span-2' : 'space-y-1'}><span className="text-sm font-medium">{label}</span><Input value={form[key]} onChange={(event) => setForm((value) => ({ ...value, [key]: event.target.value }))} /></label>)}
          </div>
          <DialogFooter><Button variant="ghost" onClick={() => setEditing(false)}>Cancelar</Button><Button onClick={() => void save()} disabled={update.isPending}>{update.isPending ? 'Salvando...' : 'Salvar alterações'}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function Back() { return <Link href="/crm" className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Voltar para o CRM</Link>; }
function Info({ label, value, icon }: { label: string; value: string | number | null | undefined; icon?: ReactNode }) { return <div className="flex items-start justify-between gap-4 border-b pb-2 last:border-b-0"><dt className="flex items-center gap-1.5 text-muted-foreground">{icon}{label}</dt><dd className="max-w-[62%] break-words text-right font-medium">{value ?? 'Não informado'}</dd></div>; }
function ExternalLinkButton({ href, children }: { href: string; children: ReactNode }) { return <a href={safeHref(href)} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 rounded-md border px-3 text-sm font-medium outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">{children}<ExternalLink className="h-4 w-4" aria-hidden="true" /></a>; }
function CompanySkeleton() { return <div className="space-y-6" role="status" aria-label="Carregando empresa"><Skeleton className="h-11 w-48" /><Skeleton className="h-24 w-full" /><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((item) => <Skeleton key={item} className="h-28" />)}</div><div className="grid gap-6 xl:grid-cols-2"><Skeleton className="h-[620px]" /><Skeleton className="h-[620px]" /></div><span className="sr-only">Carregando visão consolidada da empresa.</span></div>; }
