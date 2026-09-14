'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, ArrowLeft, Bookmark, Download, ListTodo, Play, Tags } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { engagementApi } from '@/lib/engagement-api';
import { salesOperatingApi, type CrmOperatingFilters, type OperatingBulkPayload, type OperatingBulkPreview } from '@/lib/sales-operating-api';
import { useCampaigns, useOrgMembership } from '@/hooks/use-api';
import { useCreateSavedCommercialView, useDeleteSavedCommercialView, useSavedCommercialViews } from '@/hooks/use-sales-operating';

const PAGE_SIZE = 50;

function key() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `crm:${Date.now()}:${Math.random().toString(36).slice(2)}`;
}

export default function CrmOperationsPage() {
  const qc = useQueryClient();
  const membership = useOrgMembership();
  const campaigns = useCampaigns();
  const sequences = useQuery({ queryKey: ['engagement', 'sequences', 'crm-operations'], queryFn: engagementApi.sequences, staleTime: 60_000 });
  const views = useSavedCommercialViews('crm');
  const createView = useCreateSavedCommercialView('crm');
  const deleteView = useDeleteSavedCommercialView('crm');

  const [filters, setFilters] = useState<CrmOperatingFilters>({ archived: 'active' });
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [viewName, setViewName] = useState('');
  const [shared, setShared] = useState(false);
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
    onError: (error) => toast.error(error instanceof Error ? error.message : 'Não foi possível executar a operação.'),
  });

  const previewBulk = async (payload: OperatingBulkPayload) => {
    if (!selectedRows.length) return toast.info('Selecione ao menos uma oportunidade.');
    try {
      const result = await salesOperatingApi.previewBulk(payload);
      setPending({ kind: 'bulk', payload });
      setPreview(result);
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível validar a operação.'); }
  };

  const previewTask = async () => {
    if (!selectedRows.length) return toast.info('Selecione ao menos uma oportunidade.');
    if (!taskTitle.trim()) return toast.error('Informe o título da tarefa.');
    const payload = { lead_ids: selectedRows.map((item) => item.id), expected_updated_at: expected, title: taskTitle.trim(), description: taskDescription.trim() || undefined, due_at: taskDue ? new Date(taskDue).toISOString() : null, task_type: 'FOLLOW_UP' };
    try {
      const result = await salesOperatingApi.previewBulkTask(payload);
      setPending({ kind: 'task', payload });
      setPreview(result);
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível validar as tarefas.'); }
  };

  const basePayload = (operation: OperatingBulkPayload['operation']): OperatingBulkPayload => ({ operation, lead_ids: selectedRows.map((item) => item.id), expected_updated_at: expected });
  const setFilter = (patch: Partial<CrmOperatingFilters>) => { setFilters((current) => ({ ...current, ...patch })); setOffset(0); setSelected(new Set()); };
  const saveView = async () => {
    if (viewName.trim().length < 2) return toast.error('Dê um nome à visão.');
    try { await createView.mutateAsync({ name: viewName.trim(), view_kind: 'crm', filters, shared: canShare && shared }); setViewName(''); setShared(false); toast.success('Visão salva.'); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível salvar a visão.'); }
  };
  const exportRows = async () => {
    if (!selectedRows.length) return toast.info('Selecione ao menos uma oportunidade.');
    try {
      const blob = await salesOperatingApi.exportSelection(selectedRows.map((item) => item.id));
      const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'crm-export.csv'; anchor.click(); URL.revokeObjectURL(url);
      toast.success('Export gerado e auditado.');
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível exportar.'); }
  };

  return (
    <main className="space-y-6">
      <Link href="/crm" className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Voltar para a Central comercial</Link>
      <PageHeader eyebrow="CRM · operação" title="Operar carteira" description="Filtre, salve visões e execute ações em massa com preview, RBAC, versionamento otimista e auditoria." />

      <Card><CardHeader><CardTitle>Filtros e visões</CardTitle><CardDescription>Filtros são server-side. Visões não guardam paginação, apenas critérios comerciais.</CardDescription></CardHeader><CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Input placeholder="Buscar empresa..." value={filters.search ?? ''} onChange={(e) => setFilter({ search: e.target.value || undefined })} />
          <Select value={filters.status ?? 'ALL'} onValueChange={(v) => setFilter({ status: v === 'ALL' ? undefined : v })}><SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger><SelectContent><SelectItem value="ALL">Todos os status</SelectItem>{['NOVO','ANALISADO','QUALIFICADO','CONTATADO','RESPONDIDO','REUNIAO_MARCADA','REUNIAO_FEITA','PROPOSTA_ENVIADA','PERDIDO','DESQUALIFICADO'].map((v) => <SelectItem key={v} value={v}>{v.replaceAll('_',' ')}</SelectItem>)}</SelectContent></Select>
          <Select value={filters.priority ?? 'ALL'} onValueChange={(v) => setFilter({ priority: v === 'ALL' ? undefined : v })}><SelectTrigger><SelectValue placeholder="Prioridade" /></SelectTrigger><SelectContent><SelectItem value="ALL">Todas prioridades</SelectItem><SelectItem value="HOT">Quente</SelectItem><SelectItem value="WARM">Morna</SelectItem><SelectItem value="COLD">Fria</SelectItem></SelectContent></Select>
          <Input type="number" min={0} max={100} placeholder="Score mínimo" value={filters.min_score ?? ''} onChange={(e) => setFilter({ min_score: e.target.value || undefined })} />
          <Select value={filters.archived ?? 'active'} onValueChange={(v) => setFilter({ archived: v as 'active'|'archived'|'all' })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="active">Ativos</SelectItem><SelectItem value="archived">Arquivados</SelectItem><SelectItem value="all">Todos</SelectItem></SelectContent></Select>
          <Input placeholder="Tag exata" value={filters.tag ?? ''} onChange={(e) => setFilter({ tag: e.target.value || undefined })} />
        </div>
        <div className="flex flex-wrap gap-2">{views.data?.items.map((view) => <span key={view.id} className="inline-flex rounded-full border"><button className="px-3 py-1.5 text-xs" onClick={() => { setFilters({ archived: 'active', ...view.filters }); setOffset(0); setSelected(new Set()); }}>{view.name}{view.shared ? ' · equipe' : ''}</button>{view.editable ? <button className="border-l px-2 text-xs text-destructive" onClick={() => deleteView.mutate(view.id)}>×</button> : null}</span>)}</div>
        <div className="flex flex-wrap items-center gap-2"><Bookmark className="h-4 w-4" /><Input className="max-w-xs" placeholder="Nome da visão" value={viewName} onChange={(e) => setViewName(e.target.value)} />{canShare ? <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} />Equipe</label> : null}<Button variant="outline" onClick={() => void saveView()}>Salvar visão atual</Button></div>
      </CardContent></Card>

      <Card><CardHeader><div className="flex flex-wrap justify-between gap-3"><div><CardTitle>Carteira</CardTitle><CardDescription>{query.data?.total ?? 0} oportunidade(s) no filtro · {selected.size} selecionada(s)</CardDescription></div><div className="flex gap-2"><Button variant="outline" onClick={() => void exportRows()} disabled={!selected.size}><Download className="mr-2 h-4 w-4" />Exportar</Button><Button variant="outline" onClick={() => setSelected(new Set())} disabled={!selected.size}>Limpar seleção</Button></div></div></CardHeader><CardContent className="space-y-3">
        {query.isLoading ? <p className="text-sm text-muted-foreground">Carregando carteira...</p> : query.isError ? <p className="text-sm text-destructive">Não foi possível carregar a carteira.</p> : items.length === 0 ? <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">Nenhuma oportunidade neste filtro.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead><tr className="border-b text-left text-muted-foreground"><th className="p-2"><input aria-label="Selecionar página" type="checkbox" checked={items.length > 0 && items.every((i) => selected.has(i.id))} onChange={(e) => setSelected(e.target.checked ? new Set(items.slice(0,100).map((i) => i.id)) : new Set())} /></th><th>Empresa</th><th>Status</th><th>Estágio</th><th>Score</th><th>Tags</th><th>Próxima ação</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} className="border-b"><td className="p-2"><input aria-label={`Selecionar ${item.company_name}`} type="checkbox" checked={selected.has(item.id)} onChange={() => setSelected((current) => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else if (next.size < 100) next.add(item.id); return next; })} /></td><td className="py-3"><Link className="font-medium hover:underline" href={`/oportunidades/${item.id}`}>{item.company_name}</Link><p className="text-xs text-muted-foreground">{[item.city,item.state].filter(Boolean).join(' · ')}</p></td><td><Badge variant="outline">{item.status ?? '—'}</Badge></td><td>{item.negotiation_stage ?? '—'}</td><td>{item.qualification_score ?? '—'}</td><td><div className="flex flex-wrap gap-1">{item.tags.map((value) => <Badge key={value} variant="secondary">{value}</Badge>)}{item.archived_at ? <Badge variant="outline">arquivado</Badge> : null}</div></td><td>{item.next_action_at ? new Date(item.next_action_at).toLocaleDateString('pt-BR') : '—'}</td></tr>)}</tbody></table></div>}
        <div className="flex justify-end gap-2"><Button variant="outline" disabled={offset === 0} onClick={() => { setOffset(Math.max(0, offset-PAGE_SIZE)); setSelected(new Set()); }}>Anterior</Button><Button variant="outline" disabled={!query.data || offset + PAGE_SIZE >= query.data.total} onClick={() => { setOffset(offset+PAGE_SIZE); setSelected(new Set()); }}>Próxima</Button></div>
      </CardContent></Card>

      {canWrite ? <Card><CardHeader><CardTitle>Ações em massa</CardTitle><CardDescription>Todas as ações mutáveis exigem versão atual do lead e passam por preview antes da confirmação.</CardDescription></CardHeader><CardContent className="space-y-4">
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
          <div className="flex gap-2"><Select value={stage} onValueChange={setStage}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="RD">RD</SelectItem><SelectItem value="ORCAMENTO">Orçamento</SelectItem><SelectItem value="RP">RP</SelectItem></SelectContent></Select><Button onClick={() => void previewBulk({ ...basePayload('negotiation_stage'), negotiation_stage: stage })}>Mover estágio</Button></div>
          <div className="flex gap-2"><Select value={campaignId || 'NONE'} onValueChange={(v) => setCampaignId(v === 'NONE' ? '' : v)}><SelectTrigger><SelectValue placeholder="Campanha" /></SelectTrigger><SelectContent><SelectItem value="NONE">Escolha campanha</SelectItem>{campaigns.data?.campaigns?.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent></Select><Button disabled={!campaignId} onClick={() => void previewBulk({ ...basePayload('campaign'), campaign_id: campaignId })}>Aplicar</Button></div>
          <div className="flex gap-2"><Input placeholder="Tag" value={tag} onChange={(e) => setTag(e.target.value)} /><Button variant="outline" disabled={!tag.trim()} onClick={() => void previewBulk({ ...basePayload('add_tag'), tag })}><Tags className="h-4 w-4" /></Button><Button variant="outline" disabled={!tag.trim()} onClick={() => void previewBulk({ ...basePayload('remove_tag'), tag })}>−</Button></div>
          <div className="flex gap-2"><Button variant="outline" onClick={() => void previewBulk(basePayload('archive'))}><Archive className="mr-2 h-4 w-4" />Arquivar</Button><Button variant="outline" onClick={() => void previewBulk(basePayload('unarchive'))}>Restaurar</Button></div>
          <div className="flex gap-2 xl:col-span-2"><Select value={sequenceId || 'NONE'} onValueChange={(v) => setSequenceId(v === 'NONE' ? '' : v)}><SelectTrigger><SelectValue placeholder="Sequência" /></SelectTrigger><SelectContent><SelectItem value="NONE">Escolha sequência</SelectItem>{sequences.data?.items.filter((s) => s.enabled).map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent></Select><Button disabled={!sequenceId} onClick={() => void previewBulk({ ...basePayload('start_sequence'), sequence_id: sequenceId })}><Play className="mr-2 h-4 w-4" />Iniciar sequência</Button></div>
          <Button variant="outline" onClick={() => setTaskOpen(true)}><ListTodo className="mr-2 h-4 w-4" />Criar tarefa</Button>
        </div>
      </CardContent></Card> : <Card><CardContent className="pt-6 text-sm text-muted-foreground">Seu papel é somente leitura. Filtros, visões e export permanecem disponíveis; alterações comerciais estão bloqueadas.</CardContent></Card>}

      <Dialog open={taskOpen} onOpenChange={setTaskOpen}><DialogContent><DialogHeader><DialogTitle>Criar tarefa para a seleção</DialogTitle><DialogDescription>Uma tarefa canônica será criada para cada lead aceito.</DialogDescription></DialogHeader><div className="space-y-3"><Input placeholder="Título" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} /><Input placeholder="Descrição opcional" value={taskDescription} onChange={(e) => setTaskDescription(e.target.value)} /><label className="space-y-1"><span className="text-sm font-medium">Prazo</span><Input type="datetime-local" value={taskDue} onChange={(e) => setTaskDue(e.target.value)} /></label></div><DialogFooter><Button variant="ghost" onClick={() => setTaskOpen(false)}>Cancelar</Button><Button onClick={() => void previewTask()}>Revisar</Button></DialogFooter></DialogContent></Dialog>

      <Dialog open={Boolean(preview)} onOpenChange={(open) => { if (!open) { setPreview(null); setPending(null); } }}><DialogContent><DialogHeader><DialogTitle>Confirmar operação em massa</DialogTitle><DialogDescription>O preview é calculado no servidor com tenant, carteira e versões atuais.</DialogDescription></DialogHeader>{preview ? <div className="space-y-2 text-sm"><p><strong>{preview.accepted_ids.length}</strong> lead(s) aceitos de {preview.total_selected} selecionados.</p>{preview.rejected.length ? <div className="rounded-lg bg-muted p-3"><p className="font-medium">Não serão alterados:</p>{preview.rejected.slice(0,8).map((item) => <p key={item.id} className="text-muted-foreground">{item.id.slice(0,8)} · {item.reason}</p>)}</div> : null}</div> : null}<DialogFooter><Button variant="ghost" onClick={() => { setPreview(null); setPending(null); }}>Cancelar</Button><Button disabled={!preview?.accepted_ids.length || execute.isPending} onClick={() => execute.mutate()}>{execute.isPending ? 'Aplicando...' : 'Confirmar'}</Button></DialogFooter></DialogContent></Dialog>
    </main>
  );
}
