'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, ArrowLeft, Bookmark, Download, ListTodo, Play, SlidersHorizontal, Tags } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { engagementApi } from '@/lib/engagement-api';
import { LEAD_STATUS_LABELS } from '@/lib/constants';
import { salesOperatingApi, type CrmOperatingFilters, type OperatingBulkPayload, type OperatingBulkPreview } from '@/lib/sales-operating-api';
import { useCampaigns, useOrgMembers, useOrgMembership } from '@/hooks/use-api';
import { useCreateSavedCommercialView, useDeleteSavedCommercialView, useSavedCommercialViews } from '@/hooks/use-sales-operating';

const PAGE_SIZE = 50;

const PRIORITY_LABELS: Record<string, string> = { HOT: 'Quente', WARM: 'Morna', COLD: 'Fria' };
const ARCHIVED_LABELS: Record<string, string> = { active: 'Ativas', archived: 'Arquivadas', all: 'Todas' };
const NEGOTIATION_STAGE_LABELS: Record<string, string> = { RD: 'RD', ORCAMENTO: 'Orçamento', RP: 'RP' };

function key() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `crm:${Date.now()}:${Math.random().toString(36).slice(2)}`;
}

function formatDay(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString('pt-BR');
}

function isOverdue(value?: string | null): boolean {
  if (!value) return false;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return date < today;
}

function executionErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : '';
  if (/409|conflito|concorr[eê]ncia|atualizada por outra/i.test(message)) {
    return 'Uma ou mais oportunidades foram atualizadas por outra pessoa enquanto você trabalhava. Recarregue a lista e tente novamente.';
  }
  return message || 'Não foi possível aplicar a alteração.';
}

export default function OportunidadesPage() {
  const qc = useQueryClient();
  const membership = useOrgMembership();
  const orgId = membership.data?.organization?.id;
  const campaigns = useCampaigns();
  const members = useOrgMembers(orgId);
  const sequences = useQuery({ queryKey: ['engagement', 'sequences', 'crm-operations'], queryFn: engagementApi.sequences, staleTime: 60_000 });
  const views = useSavedCommercialViews('crm');
  const createView = useCreateSavedCommercialView('crm');
  const deleteView = useDeleteSavedCommercialView('crm');

  const [filters, setFilters] = useState<CrmOperatingFilters>({ archived: 'active' });
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [viewName, setViewName] = useState('');
  const [shared, setShared] = useState(false);
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [stage, setStage] = useState('RD');
  const [campaignId, setCampaignId] = useState('');
  const [tag, setTag] = useState('');
  const [sequenceId, setSequenceId] = useState('');
  const [taskOpen, setTaskOpen] = useState(false);
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDescription, setTaskDescription] = useState('');
  const [taskDue, setTaskDue] = useState('');
  const [preview, setPreview] = useState<OperatingBulkPreview | null>(null);
  const [pending, setPending] = useState<{ kind: 'bulk'; payload: OperatingBulkPayload } | { kind: 'task'; payload: { lead_ids: string[]; expected_updated_at: Record<string, string>; title: string; description?: string; due_at?: string | null; task_type?: string } } | null>(null);

  const query = useQuery({
    queryKey: ['sales-operating', 'leads', filters, offset],
    queryFn: () => salesOperatingApi.leads({ ...filters, limit: PAGE_SIZE, offset }),
    staleTime: 15_000,
  });
  const canWrite = membership.data?.membership?.sales_role !== 'ANALYST';
  const canShare = ['OWNER', 'ADMIN'].includes(membership.data?.membership?.role ?? '') || membership.data?.membership?.sales_role === 'MANAGER';
  const items = query.data?.items ?? [];
  const selectedRows = items.filter((item) => selected.has(item.id));
  const expected = useMemo(() => Object.fromEntries(selectedRows.map((item) => [item.id, item.updated_at])), [selectedRows]);
  const ownerNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const member of members.data?.members ?? []) {
      map.set(member.user_id, member.name || member.email || 'Sem nome');
    }
    return map;
  }, [members.data]);

  const hasFilters = Boolean(
    filters.search || filters.status || filters.priority || filters.campaign_id
    || filters.assigned || filters.min_score || (filters.archived && filters.archived !== 'active') || filters.tag,
  );

  const clearAfterMutation = () => {
    setSelected(new Set());
    setPreview(null);
    setPending(null);
    void qc.invalidateQueries({ queryKey: ['sales-operating'] });
  };

  const execute = useMutation({
    mutationFn: async () => {
      if (!pending) throw new Error('Nenhuma operação pendente');
      if (pending.kind === 'bulk') return salesOperatingApi.executeBulk({ ...pending.payload, idempotency_key: key() });
      return salesOperatingApi.createBulkTask({ ...pending.payload, idempotency_key: key() });
    },
    onSuccess: (result) => {
      toast.success(`${result.summary.accepted} alteração(ões) aplicada(s). ${result.summary.rejected + result.summary.failed} não aplicada(s).`);
      clearAfterMutation();
      setTaskOpen(false);
      setTaskTitle(''); setTaskDescription(''); setTaskDue('');
    },
    onError: (error) => toast.error(executionErrorMessage(error)),
  });

  const previewBulk = async (payload: OperatingBulkPayload) => {
    if (!selectedRows.length) return toast.info('Selecione ao menos uma oportunidade.');
    try {
      const result = await salesOperatingApi.previewBulk(payload);
      setPending({ kind: 'bulk', payload });
      setPreview(result);
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível revisar a alteração.'); }
  };

  const previewTask = async () => {
    if (!selectedRows.length) return toast.info('Selecione ao menos uma oportunidade.');
    if (!taskTitle.trim()) return toast.error('Informe o título da tarefa.');
    const payload = { lead_ids: selectedRows.map((item) => item.id), expected_updated_at: expected, title: taskTitle.trim(), description: taskDescription.trim() || undefined, due_at: taskDue ? new Date(taskDue).toISOString() : null, task_type: 'FOLLOW_UP' };
    try {
      const result = await salesOperatingApi.previewBulkTask(payload);
      setPending({ kind: 'task', payload });
      setPreview(result);
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível revisar as tarefas.'); }
  };

  const basePayload = (operation: OperatingBulkPayload['operation']): OperatingBulkPayload => ({ operation, lead_ids: selectedRows.map((item) => item.id), expected_updated_at: expected });
  const setFilter = (patch: Partial<CrmOperatingFilters>) => { setFilters((current) => ({ ...current, ...patch })); setOffset(0); setSelected(new Set()); };
  const clearFilters = () => { setFilters({ archived: 'active' }); setOffset(0); setSelected(new Set()); };
  const saveView = async () => {
    if (viewName.trim().length < 2) return toast.error('Dê um nome à visão.');
    try { await createView.mutateAsync({ name: viewName.trim(), view_kind: 'crm', filters, shared: canShare && shared }); setViewName(''); setShared(false); toast.success('Visão salva.'); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível salvar a visão.'); }
  };
  const exportRows = async () => {
    if (!selectedRows.length) return toast.info('Selecione ao menos uma oportunidade.');
    try {
      const blob = await salesOperatingApi.exportSelection(selectedRows.map((item) => item.id));
      const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'oportunidades.csv'; anchor.click(); URL.revokeObjectURL(url);
      toast.success('Arquivo gerado.');
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível exportar.'); }
  };

  return (
    <main className="space-y-6">
      <Link href="/crm" className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Voltar para a Central comercial</Link>
      <PageHeader eyebrow="Comercial" title="Oportunidades" description="Organize e acompanhe as oportunidades da sua equipe. Filtre por etapa, prioridade ou responsável e mantenha o trabalho comercial em dia." />

      <Card><CardHeader><CardTitle>Encontrar oportunidades</CardTitle><CardDescription>Busca e filtros aplicados na hora, direto no servidor.</CardDescription></CardHeader><CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Input placeholder="Buscar empresa..." aria-label="Buscar oportunidade por empresa" value={filters.search ?? ''} onChange={(e) => setFilter({ search: e.target.value || undefined })} />
          <Select value={filters.status ?? 'ALL'} onValueChange={(v) => setFilter({ status: !v || v === 'ALL' ? undefined : v })}><SelectTrigger aria-label="Filtrar por etapa"><SelectValue placeholder="Etapa">{(value) => (value === 'ALL' ? 'Todas as etapas' : (LEAD_STATUS_LABELS[value as string] ?? (value as string)))}</SelectValue></SelectTrigger><SelectContent><SelectItem value="ALL">Todas as etapas</SelectItem>{['NOVO','ANALISADO','QUALIFICADO','CONTATADO','RESPONDIDO','REUNIAO_MARCADA','REUNIAO_FEITA','PROPOSTA_ENVIADA','PERDIDO','DESQUALIFICADO'].map((v) => <SelectItem key={v} value={v}>{LEAD_STATUS_LABELS[v] ?? v}</SelectItem>)}</SelectContent></Select>
          <Select value={filters.assigned ?? 'all'} onValueChange={(v) => setFilter({ assigned: !v || v === 'all' ? undefined : v })}><SelectTrigger aria-label="Filtrar por responsável"><SelectValue placeholder="Responsável">{(value) => (value === 'all' ? 'Todos os responsáveis' : value === 'me' ? 'Minhas oportunidades' : (ownerNames.get(value as string) ?? 'Responsável'))}</SelectValue></SelectTrigger><SelectContent><SelectItem value="all">Todos os responsáveis</SelectItem><SelectItem value="me">Minhas oportunidades</SelectItem>{(members.data?.members ?? []).map((m) => <SelectItem key={m.user_id} value={m.user_id}>{m.name || m.email || 'Sem nome'}</SelectItem>)}</SelectContent></Select>
          <Select value={filters.campaign_id ?? 'all'} onValueChange={(v) => setFilter({ campaign_id: !v || v === 'all' ? undefined : v })}><SelectTrigger aria-label="Filtrar por campanha"><SelectValue placeholder="Campanha">{(value) => (value === 'all' ? 'Todas as campanhas' : (campaigns.data?.campaigns?.find((c) => c.id === value)?.name ?? 'Campanha'))}</SelectValue></SelectTrigger><SelectContent><SelectItem value="all">Todas as campanhas</SelectItem>{campaigns.data?.campaigns?.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent></Select>
          <Select value={filters.priority ?? 'ALL'} onValueChange={(v) => setFilter({ priority: !v || v === 'ALL' ? undefined : v })}><SelectTrigger aria-label="Filtrar por prioridade"><SelectValue placeholder="Prioridade">{(value) => (value === 'ALL' ? 'Todas as prioridades' : (PRIORITY_LABELS[value as string] ?? (value as string)))}</SelectValue></SelectTrigger><SelectContent><SelectItem value="ALL">Todas as prioridades</SelectItem><SelectItem value="HOT">Quente</SelectItem><SelectItem value="WARM">Morna</SelectItem><SelectItem value="COLD">Fria</SelectItem></SelectContent></Select>
          <Input type="number" min={0} max={100} placeholder="Score mínimo" aria-label="Score mínimo" value={filters.min_score ?? ''} onChange={(e) => setFilter({ min_score: e.target.value || undefined })} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant={filters.assigned === undefined && filters.priority === undefined && filters.status === undefined ? 'default' : 'outline'} size="sm" onClick={clearFilters}>Todas</Button>
          <Button variant={filters.assigned === 'me' ? 'default' : 'outline'} size="sm" onClick={() => setFilter({ assigned: 'me' })}>Minhas oportunidades</Button>
          <Button variant={filters.priority === 'HOT' ? 'default' : 'outline'} size="sm" onClick={() => setFilter({ priority: 'HOT' })}>Alta prioridade</Button>
          <Button variant="ghost" size="sm" onClick={() => setShowMoreFilters((v) => !v)} aria-expanded={showMoreFilters}><SlidersHorizontal className="mr-1.5 h-3.5 w-3.5" />{showMoreFilters ? 'Menos filtros' : 'Mais filtros'}</Button>
          {hasFilters ? <Button variant="ghost" size="sm" onClick={clearFilters}>Limpar filtros</Button> : null}
        </div>
        {showMoreFilters ? (
          <div className="grid gap-3 md:grid-cols-3">
            <Select value={filters.archived ?? 'active'} onValueChange={(v) => { if (v === 'active' || v === 'archived' || v === 'all') setFilter({ archived: v }); }}><SelectTrigger aria-label="Filtrar por situação"><SelectValue>{(value) => ARCHIVED_LABELS[value as string] ?? (value as string)}</SelectValue></SelectTrigger><SelectContent><SelectItem value="active">Ativas</SelectItem><SelectItem value="archived">Arquivadas</SelectItem><SelectItem value="all">Todas</SelectItem></SelectContent></Select>
            <Input placeholder="Tag exata" aria-label="Filtrar por etiqueta" value={filters.tag ?? ''} onChange={(e) => setFilter({ tag: e.target.value || undefined })} />
          </div>
        ) : null}
      </CardContent></Card>

      <Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle className="flex items-center gap-2"><Bookmark className="h-4 w-4 text-muted-foreground" aria-hidden="true" />Visões</CardTitle><CardDescription>Salve combinações de filtros que você usa com frequência.</CardDescription></div></div></CardHeader><CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">{views.data?.items.length ? views.data.items.map((view) => <span key={view.id} className="inline-flex items-center rounded-full border"><button className="px-3 py-1.5 text-xs" onClick={() => { setFilters({ archived: 'active', ...view.filters }); setOffset(0); setSelected(new Set()); }}>{view.name}{view.shared ? ' · equipe' : ''}</button>{view.editable ? <button className="border-l px-2 text-xs text-destructive" aria-label={`Excluir visão ${view.name}`} onClick={() => deleteView.mutate(view.id)}>×</button> : null}</span>) : <p className="text-sm text-muted-foreground">Nenhuma visão salva ainda.</p>}</div>
        <div className="flex flex-wrap items-center gap-2"><Input className="max-w-xs" placeholder="Nome da visão" aria-label="Nome da nova visão" value={viewName} onChange={(e) => setViewName(e.target.value)} />{canShare ? <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} />Equipe</label> : null}<Button variant="outline" onClick={() => void saveView()}>Salvar visão atual</Button></div>
      </CardContent></Card>

      <Card><CardHeader><div className="flex flex-wrap justify-between gap-3"><div><CardTitle>Oportunidades</CardTitle><CardDescription>{query.data?.total ?? 0} oportunidade(s) no filtro{selected.size > 0 ? ` · ${selected.size} selecionada(s)` : ''}</CardDescription></div>{selected.size > 0 ? <div className="flex gap-2"><Button variant="outline" onClick={() => void exportRows()}><Download className="mr-2 h-4 w-4" />Exportar</Button><Button variant="outline" onClick={() => setSelected(new Set())}>Limpar seleção</Button></div> : null}</div></CardHeader><CardContent className="space-y-3">
        {query.isLoading ? <p className="text-sm text-muted-foreground">Carregando oportunidades...</p> : query.isError ? <div className="space-y-2"><p className="text-sm text-destructive">Não foi possível carregar as oportunidades.</p><Button variant="outline" size="sm" onClick={() => void query.refetch()}>Tentar novamente</Button></div> : items.length === 0 ? <div className="rounded-lg border border-dashed p-8 text-center"><p className="font-medium">{hasFilters ? 'Nenhuma oportunidade corresponde aos filtros' : 'Ainda não há oportunidades para acompanhar'}</p><p className="mt-1 text-sm text-muted-foreground">{hasFilters ? 'Ajuste os filtros ou limpe para ver tudo.' : 'Elas aparecem aqui quando entram no trabalho da equipe.'}</p>{hasFilters ? <Button variant="outline" size="sm" className="mt-3" onClick={clearFilters}>Limpar filtros</Button> : null}</div> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead><tr className="border-b text-left text-muted-foreground"><th className="p-2"><input aria-label="Selecionar página" type="checkbox" checked={items.length > 0 && items.every((i) => selected.has(i.id))} onChange={(e) => setSelected(e.target.checked ? new Set(items.slice(0,100).map((i) => i.id)) : new Set())} /></th><th>Empresa</th><th>Etapa</th><th>Score</th><th>Prioridade</th><th>Responsável</th><th>Próxima ação</th></tr></thead><tbody>{items.map((item) => {
          const nextAction = formatDay(item.next_action_at);
          const overdue = isOverdue(item.next_action_at);
          return <tr key={item.id} className="border-b"><td className="p-2"><input aria-label={`Selecionar ${item.company_name}`} type="checkbox" checked={selected.has(item.id)} onChange={() => setSelected((current) => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else if (next.size < 100) next.add(item.id); return next; })} /></td><td className="py-3"><Link className="font-medium hover:underline" href={`/oportunidades/${item.id}`}>{item.company_name}</Link><p className="text-xs text-muted-foreground">{[item.city,item.state].filter(Boolean).join(' · ') || 'Local não informado'}</p>{item.archived_at ? <Badge variant="outline" className="mt-1">Arquivada</Badge> : null}</td><td><Badge variant="outline">{LEAD_STATUS_LABELS[item.status ?? ''] ?? item.status ?? '—'}</Badge>{item.negotiation_stage ? <p className="mt-1 text-xs text-muted-foreground">{NEGOTIATION_STAGE_LABELS[item.negotiation_stage] ?? item.negotiation_stage}</p> : null}</td><td>{item.qualification_score ?? '—'}</td><td>{item.priority ? <Badge variant="secondary">{PRIORITY_LABELS[item.priority] ?? item.priority}</Badge> : '—'}</td><td>{item.assigned_to_id ? (ownerNames.get(item.assigned_to_id) ?? 'Responsável definido') : <span className="text-muted-foreground">Sem responsável</span>}</td><td>{nextAction ? <span className={overdue ? 'font-medium text-amber-700 dark:text-amber-400' : undefined}>{overdue ? `Vencida em ${nextAction}` : nextAction}</span> : <span className="text-muted-foreground">Sem próxima ação</span>}</td></tr>;
        })}</tbody></table></div>}
        <div className="flex justify-end gap-2"><Button variant="outline" disabled={offset === 0} onClick={() => { setOffset(Math.max(0, offset-PAGE_SIZE)); setSelected(new Set()); }}>Anterior</Button><Button variant="outline" disabled={!query.data || offset + PAGE_SIZE >= query.data.total} onClick={() => { setOffset(offset+PAGE_SIZE); setSelected(new Set()); }}>Próxima</Button></div>
      </CardContent></Card>

      {canWrite && selected.size > 0 ? <Card><CardHeader><CardTitle>Atualizar {selected.size} selecionada(s)</CardTitle><CardDescription>As alterações passam por revisão antes de serem aplicadas.</CardDescription></CardHeader><CardContent className="space-y-4">
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
          <div className="flex gap-2"><Select value={stage} onValueChange={(v) => setStage(v ?? 'RD')}><SelectTrigger aria-label="Nova etapa"><SelectValue>{(value) => NEGOTIATION_STAGE_LABELS[value as string] ?? (value as string)}</SelectValue></SelectTrigger><SelectContent><SelectItem value="RD">RD</SelectItem><SelectItem value="ORCAMENTO">Orçamento</SelectItem><SelectItem value="RP">RP</SelectItem></SelectContent></Select><Button onClick={() => void previewBulk({ ...basePayload('negotiation_stage'), negotiation_stage: stage })}>Mover etapa</Button></div>
          <div className="flex gap-2"><Select value={campaignId || 'NONE'} onValueChange={(v) => setCampaignId(!v || v === 'NONE' ? '' : v)}><SelectTrigger aria-label="Nova campanha"><SelectValue placeholder="Campanha">{(value) => (value === 'NONE' ? 'Escolher campanha' : (campaigns.data?.campaigns?.find((c) => c.id === value)?.name ?? 'Escolher campanha'))}</SelectValue></SelectTrigger><SelectContent><SelectItem value="NONE">Escolher campanha</SelectItem>{campaigns.data?.campaigns?.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent></Select><Button disabled={!campaignId} onClick={() => void previewBulk({ ...basePayload('campaign'), campaign_id: campaignId })}>Aplicar</Button></div>
          <div className="flex gap-2"><Input placeholder="Etiqueta" aria-label="Etiqueta" value={tag} onChange={(e) => setTag(e.target.value)} /><Button variant="outline" disabled={!tag.trim()} onClick={() => void previewBulk({ ...basePayload('add_tag'), tag })}><Tags className="h-4 w-4" /></Button><Button variant="outline" disabled={!tag.trim()} onClick={() => void previewBulk({ ...basePayload('remove_tag'), tag })}>−</Button></div>
          <div className="flex gap-2"><Button variant="outline" onClick={() => void previewBulk(basePayload('archive'))}><Archive className="mr-2 h-4 w-4" />Arquivar</Button><Button variant="outline" onClick={() => void previewBulk(basePayload('unarchive'))}>Restaurar</Button></div>
          <div className="flex gap-2 xl:col-span-2"><Select value={sequenceId || 'NONE'} onValueChange={(v) => setSequenceId(!v || v === 'NONE' ? '' : v)}><SelectTrigger aria-label="Sequência de acompanhamento"><SelectValue placeholder="Sequência">{(value) => (value === 'NONE' ? 'Escolher sequência' : (sequences.data?.items.find((s) => s.id === value)?.name ?? 'Escolher sequência'))}</SelectValue></SelectTrigger><SelectContent><SelectItem value="NONE">Escolher sequência</SelectItem>{sequences.data?.items.filter((s) => s.enabled).map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent></Select><Button disabled={!sequenceId} onClick={() => void previewBulk({ ...basePayload('start_sequence'), sequence_id: sequenceId })}><Play className="mr-2 h-4 w-4" />Iniciar acompanhamento</Button></div>
          <Button variant="outline" onClick={() => setTaskOpen(true)}><ListTodo className="mr-2 h-4 w-4" />Criar tarefa</Button>
        </div>
      </CardContent></Card> : (!canWrite ? <Card><CardContent className="pt-6 text-sm text-muted-foreground">Seu papel é somente leitura. Filtros, visões e export permanecem disponíveis; alterações comerciais estão bloqueadas.</CardContent></Card> : null)}

      <Dialog open={taskOpen} onOpenChange={setTaskOpen}><DialogContent><DialogHeader><DialogTitle>Criar tarefa para a seleção</DialogTitle><DialogDescription>Uma tarefa será criada para cada oportunidade aceita.</DialogDescription></DialogHeader><div className="space-y-3"><Input placeholder="Título" aria-label="Título da tarefa" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} /><Input placeholder="Descrição opcional" aria-label="Descrição da tarefa" value={taskDescription} onChange={(e) => setTaskDescription(e.target.value)} /><label className="space-y-1"><span className="text-sm font-medium">Prazo</span><Input type="datetime-local" value={taskDue} onChange={(e) => setTaskDue(e.target.value)} /></label></div><DialogFooter><Button variant="ghost" onClick={() => setTaskOpen(false)}>Cancelar</Button><Button onClick={() => void previewTask()}>Revisar</Button></DialogFooter></DialogContent></Dialog>

      <Dialog open={Boolean(preview)} onOpenChange={(open) => { if (!open) { setPreview(null); setPending(null); } }}><DialogContent><DialogHeader><DialogTitle>Confirmar alteração</DialogTitle><DialogDescription>Revise antes de aplicar. Nada muda até você confirmar.</DialogDescription></DialogHeader>{preview ? <div className="space-y-2 text-sm"><p><strong>{preview.accepted_ids.length}</strong> de {preview.total_selected} selecionadas serão atualizadas.</p>{preview.rejected.length ? <div className="rounded-lg bg-muted p-3"><p className="font-medium">Não serão alteradas:</p>{preview.rejected.slice(0,8).map((item) => <p key={item.id} className="text-muted-foreground">{item.id.slice(0,8)} · {item.reason}</p>)}</div> : null}</div> : null}<DialogFooter><Button variant="ghost" onClick={() => { setPreview(null); setPending(null); }}>Cancelar</Button><Button disabled={!preview?.accepted_ids.length || execute.isPending} onClick={() => execute.mutate()}>{execute.isPending ? 'Aplicando...' : 'Confirmar'}</Button></DialogFooter></DialogContent></Dialog>
    </main>
  );
}
