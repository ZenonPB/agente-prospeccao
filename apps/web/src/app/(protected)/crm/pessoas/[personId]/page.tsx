'use client';

import { use, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft, Building2, ExternalLink, Mail, Pencil, Phone, ShieldCheck, UserRound } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { CrmMetric, CrmOpportunities, CrmTasks, CrmTimeline, humanCrmKey, safeHref } from '@/components/crm/crm-360-shared';
import { usePerson360, useUpdatePerson360, useVerifyPerson360 } from '@/hooks/use-crm-360';
import { useOrgMembership } from '@/hooks/use-api';

type PersonForm = { name: string; role: string; role_label: string; email: string; phone: string; linkedin_url: string; routability_type: string; routability_reason: string; routable: boolean };
const emptyForm: PersonForm = { name: '', role: '', role_label: '', email: '', phone: '', linkedin_url: '', routability_type: 'UNKNOWN', routability_reason: '', routable: false };

const ROLE_LABELS: Record<string, string> = { NONE: 'Não definido', SOCIO: 'Sócio', ADMINISTRADOR: 'Administrador', CEO: 'CEO', DIRETOR: 'Diretor', OUTRO: 'Outro' };
const ROUTABILITY_LABELS: Record<string, string> = { UNKNOWN: 'Desconhecida', DIRECT: 'Direta', COMPANY: 'Via empresa', NONE: 'Sem rota' };

export default function Person360Page(props: { params: Promise<{ personId: string }> }) {
  const { personId } = use(props.params);
  const query = usePerson360(personId);
  const update = useUpdatePerson360(personId);
  const verify = useVerifyPerson360(personId);
  const membership = useOrgMembership();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<PersonForm>(emptyForm);
  const canEdit = membership.data?.membership?.sales_role !== 'ANALYST';

  if (query.isLoading) return <PersonSkeleton />;
  if (query.isError || !query.data) return <div className="space-y-6"><Back /><EmptyState title="Não foi possível abrir esta pessoa" description="Ela pode não existir neste workspace ou não pertencer à sua carteira." /></div>;

  const data = query.data;
  const current = data.person;
  const company = data.company;
  const beginEditing = () => {
    setForm({
      name: current.name ?? '', role: current.role ?? '', role_label: current.role_label ?? '',
      email: current.email ?? '', phone: current.phone ?? '', linkedin_url: current.linkedin_url ?? '',
      routability_type: current.routability_type ?? 'UNKNOWN', routability_reason: current.routability_reason ?? '', routable: current.routable,
    });
    setEditing(true);
  };
  const save = async () => {
    const version = current.updated_at || current.created_at;
    if (!version) return toast.error('Recarregue a pessoa antes de editar.');
    if (!form.name.trim()) return toast.error('O nome é obrigatório.');
    try {
      await update.mutateAsync({ expected_updated_at: version, name: form.name, role: form.role || null, role_label: form.role_label || null, email: form.email || null, phone: form.phone || null, linkedin_url: form.linkedin_url || null, routability_type: form.routability_type || 'UNKNOWN', routability_reason: form.routability_reason || null, routable: form.routable });
      setEditing(false);
      toast.success('Pessoa atualizada.');
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar a pessoa.'); }
  };
  const humanVerify = async () => {
    const version = current.updated_at || current.created_at;
    if (!version) return toast.error('Recarregue a pessoa antes de validar.');
    try { await verify.mutateAsync(version); toast.success('Identidade marcada como validada por humano.'); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível validar a pessoa.'); }
  };

  return (
    <main className="space-y-6">
      <Back companyId={company?.id} />
      <PageHeader
        eyebrow="CRM · Pessoa"
        title={current.name}
        description={[current.role_label || humanCrmKey(current.role), company?.company_name].filter(Boolean).join(' · ')}
        actions={<div className="flex flex-wrap gap-2">{canEdit ? <><Button variant="outline" onClick={beginEditing}><Pencil className="mr-2 h-4 w-4" />Editar</Button><Button variant="outline" onClick={() => void humanVerify()} disabled={verify.isPending || current.verification_status === 'human_verified'}><ShieldCheck className="mr-2 h-4 w-4" />{current.verification_status === 'human_verified' ? 'Validado' : 'Validar identidade'}</Button></> : null}<Badge variant={current.routable ? 'secondary' : 'outline'}>{current.routable ? 'Contato acionável' : 'Contato a revisar'}</Badge>{current.email_verified && <Badge variant="outline">E-mail verificado</Badge>}</div>}
      />

      <section aria-label="Resumo do contato" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <CrmMetric label="Confiança da identidade" value={`${Math.round(current.identity_confidence ?? 0)}%`} />
        <CrmMetric label="Confiança do contato" value={`${Math.round(current.contact_confidence ?? 0)}%`} />
        <CrmMetric label="Oportunidades relacionadas" value={String(data.summary.opportunity_count)} hint={data.summary.best_opportunity_score == null ? 'Sem score disponível' : `Melhor score: ${data.summary.best_opportunity_score} pontos`} />
        <CrmMetric label="Tarefas abertas" value={String(data.summary.open_task_count)} />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]">
        <div className="space-y-6">
          <section className="grid gap-6 lg:grid-cols-2" aria-label="Contato e empresa">
            <Card><CardHeader><CardTitle className="flex items-center gap-2"><UserRound className="h-5 w-5" aria-hidden="true" /> Contato</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><dl className="space-y-3"><Info label="Cargo" value={current.role_label || humanCrmKey(current.role)} /><Info label="E-mail" value={current.email} icon={<Mail className="h-4 w-4" />} /><Info label="Telefone" value={current.phone} icon={<Phone className="h-4 w-4" />} /><Info label="Verificação" value={humanCrmKey(current.verification_status)} icon={<ShieldCheck className="h-4 w-4" />} /><Info label="Roteabilidade" value={humanCrmKey(current.routability_type)} /><Info label="Fonte" value={current.source} /></dl>{current.linkedin_url && <a href={safeHref(current.linkedin_url)} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 rounded-md border px-3 font-medium outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">Abrir LinkedIn <ExternalLink className="h-4 w-4" aria-hidden="true" /></a>}</CardContent></Card>
            <Card><CardHeader><CardTitle className="flex items-center gap-2"><Building2 className="h-5 w-5" aria-hidden="true" /> Empresa</CardTitle></CardHeader><CardContent>{company ? <div className="space-y-3 text-sm"><p className="text-lg font-semibold">{company.company_name}</p><p className="text-muted-foreground">{[company.category, company.city, company.state].filter(Boolean).join(' · ') || 'Sem classificação adicional'}</p><Link href={`/crm/empresas/${company.id}`} className="inline-flex min-h-11 items-center rounded-md border px-3 font-medium outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">Abrir visão da empresa</Link></div> : <p className="text-sm text-muted-foreground">Esta pessoa ainda não está vinculada a uma empresa canônica.</p>}</CardContent></Card>
          </section>
          <CrmOpportunities opportunities={data.opportunities} />
          <CrmTasks tasks={data.tasks} />
        </div>
        <aside aria-label="Histórico da pessoa"><CrmTimeline items={data.timeline} /></aside>
      </div>

      <Dialog open={editing} onOpenChange={(open) => { if (!open) setEditing(false); }}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader><DialogTitle>Editar pessoa canônica</DialogTitle><DialogDescription>CPF e vínculo de empresa permanecem protegidos como identidade. A alteração é auditada e rejeita versões desatualizadas.</DialogDescription></DialogHeader>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Nome"><Input value={form.name} onChange={(e) => setForm((v) => ({ ...v, name: e.target.value }))} /></Field>
            <Field label="Papel"><Select value={form.role || 'NONE'} onValueChange={(value) => setForm((v) => ({ ...v, role: value === 'NONE' ? '' : (value ?? '') }))}><SelectTrigger><SelectValue>{(value) => ROLE_LABELS[value as string] ?? (value as string)}</SelectValue></SelectTrigger><SelectContent><SelectItem value="NONE">Não definido</SelectItem><SelectItem value="SOCIO">Sócio</SelectItem><SelectItem value="ADMINISTRADOR">Administrador</SelectItem><SelectItem value="CEO">CEO</SelectItem><SelectItem value="DIRETOR">Diretor</SelectItem><SelectItem value="OUTRO">Outro</SelectItem></SelectContent></Select></Field>
            <Field label="Cargo"><Input value={form.role_label} onChange={(e) => setForm((v) => ({ ...v, role_label: e.target.value }))} /></Field>
            <Field label="E-mail"><Input type="email" value={form.email} onChange={(e) => setForm((v) => ({ ...v, email: e.target.value }))} /></Field>
            <Field label="Telefone"><Input value={form.phone} onChange={(e) => setForm((v) => ({ ...v, phone: e.target.value }))} /></Field>
            <Field label="LinkedIn"><Input value={form.linkedin_url} onChange={(e) => setForm((v) => ({ ...v, linkedin_url: e.target.value }))} /></Field>
            <Field label="Roteabilidade"><Select value={form.routability_type} onValueChange={(value) => setForm((v) => ({ ...v, routability_type: value ?? 'UNKNOWN' }))}><SelectTrigger><SelectValue>{(value) => ROUTABILITY_LABELS[value as string] ?? (value as string)}</SelectValue></SelectTrigger><SelectContent><SelectItem value="UNKNOWN">Desconhecida</SelectItem><SelectItem value="DIRECT">Direta</SelectItem><SelectItem value="COMPANY">Via empresa</SelectItem><SelectItem value="NONE">Sem rota</SelectItem></SelectContent></Select></Field>
            <Field label="Motivo da roteabilidade"><Input value={form.routability_reason} onChange={(e) => setForm((v) => ({ ...v, routability_reason: e.target.value }))} /></Field>
            <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={form.routable} onChange={(e) => setForm((v) => ({ ...v, routable: e.target.checked }))} />Contato pode ser acionado comercialmente</label>
          </div>
          <DialogFooter><Button variant="ghost" onClick={() => setEditing(false)}>Cancelar</Button><Button onClick={() => void save()} disabled={update.isPending}>{update.isPending ? 'Salvando...' : 'Salvar alterações'}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="space-y-1"><span className="text-sm font-medium">{label}</span>{children}</label>; }
function Back({ companyId }: { companyId?: string }) { return <Link href={companyId ? `/crm/empresas/${companyId}` : '/crm'} className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> {companyId ? 'Voltar para a empresa' : 'Voltar para o CRM'}</Link>; }
function Info({ label, value, icon }: { label: string; value: string | number | null | undefined; icon?: ReactNode }) { return <div className="flex items-start justify-between gap-4 border-b pb-2 last:border-b-0"><dt className="flex items-center gap-1.5 text-muted-foreground">{icon}{label}</dt><dd className="max-w-[62%] break-words text-right font-medium">{value ?? 'Não informado'}</dd></div>; }
function PersonSkeleton() { return <div className="space-y-6" role="status" aria-label="Carregando pessoa"><Skeleton className="h-11 w-48" /><Skeleton className="h-24 w-full" /><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((item) => <Skeleton key={item} className="h-28" />)}</div><div className="grid gap-6 xl:grid-cols-2"><Skeleton className="h-[540px]" /><Skeleton className="h-[540px]" /></div><span className="sr-only">Carregando visão consolidada da pessoa.</span></div>; }
