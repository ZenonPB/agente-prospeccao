'use client';

import { use, useMemo, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Check, Loader2, Plus, Save, UserRound, X } from 'lucide-react';
import { toast } from 'sonner';

import {
  useCreateOpportunityTask,
  useOpportunity360,
  useUpdateOpportunity360,
  useUpdateOpportunityTask,
} from '@/hooks/use-opportunity-360';
import { useOrgMembership } from '@/hooks/use-api';
import { request } from '@/lib/api';
import { offerProfileLabel } from '@/lib/offers';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PageHeader } from '@/components/ui/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import type { Opportunity360Payload, Opportunity360Patch } from '@/types/opportunity-360';

const STATUS_OPTIONS = [
  ['NOVO', 'Novo'],
  ['QUALIFICADO', 'Apto para contato'],
  ['CONTATADO', 'Contato realizado'],
  ['RESPONDIDO', 'Cliente respondeu'],
  ['REUNIAO_MARCADA', 'Reunião agendada'],
  ['REUNIAO_FEITA', 'Reunião realizada'],
  ['PROPOSTA_ENVIADA', 'Proposta enviada'],
  ['PERDIDO', 'Perdido'],
] as const;

const STAGE_OPTIONS = [
  ['', 'Sem etapa interna'],
  ['RD', 'RD · Reunião de diagnóstico'],
  ['ORCAMENTO', 'Orçamento'],
  ['RP', 'RP · Reunião de proposta'],
] as const;

const LOST_REASON_OPTIONS = [
  ['PRECO', 'Preço'],
  ['PRAZO', 'Prazo'],
  ['NAO_RESPONDEU', 'Não respondeu'],
  ['CONCORRENTE', 'Concorrente'],
  ['OUTRO', 'Outro'],
] as const;

const SELECT_CLASS =
  'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-xs outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50';

type Member = {
  user_id: string;
  name: string | null;
  email: string | null;
  role: string | null;
  sales_role: string | null;
};

function toLocalInput(value: string | null | undefined) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function toIsoOrNull(value: string) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function mutationMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Não foi possível salvar a alteração.';
}

export default function EditOpportunity360Page(props: { params: Promise<{ opportunityId: string }> }) {
  const { opportunityId } = use(props.params);
  const query = useOpportunity360(opportunityId);

  if (query.isLoading) return <EditorSkeleton />;

  if (query.isError || !query.data) {
    return (
      <main className="space-y-6">
        <Link
          href="/oportunidades"
          className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Voltar para oportunidades
        </Link>
        <EmptyState
          title="Não foi possível editar esta oportunidade"
          description="Ela pode não existir neste workspace ou você pode não ter acesso a ela."
        />
      </main>
    );
  }

  return (
    <OpportunityEditor
      key={`${opportunityId}:${query.data.lead.updated_at ?? ''}`}
      opportunityId={opportunityId}
      data={query.data}
    />
  );
}

function OpportunityEditor({ opportunityId, data }: { opportunityId: string; data: Opportunity360Payload }) {
  const updateOpportunity = useUpdateOpportunity360(opportunityId);
  const createTask = useCreateOpportunityTask(opportunityId);
  const updateTask = useUpdateOpportunityTask(opportunityId);
  const membershipQ = useOrgMembership();

  const [status, setStatus] = useState(data.commercial.status ?? 'NOVO');
  const [stage, setStage] = useState(data.commercial.negotiation_stage ?? '');
  const [lostReason, setLostReason] = useState(data.commercial.lost_reason ?? '');
  const [value, setValue] = useState(data.commercial.value == null ? '' : String(data.commercial.value));
  const [expectedClose, setExpectedClose] = useState(toLocalInput(data.commercial.expected_close_date));
  const [nextActionAt, setNextActionAt] = useState(toLocalInput(data.lead.next_action_at));
  const [notes, setNotes] = useState(data.lead.notes ?? '');
  const [ownerUserId, setOwnerUserId] = useState(data.owner?.id ?? '');
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDescription, setTaskDescription] = useState('');
  const [taskDueAt, setTaskDueAt] = useState('');

  const membership = membershipQ.data;
  const salesRole = membership?.membership?.sales_role;
  const orgRole = membership?.membership?.role;
  const currentUserId = membership?.membership?.user_id;
  const orgId = membership?.organization?.id;
  const canEdit = orgRole === 'OWNER' || orgRole === 'ADMIN' || salesRole === 'MANAGER' || salesRole === 'CONSULTOR';
  const canManageOwners = orgRole === 'OWNER' || orgRole === 'ADMIN' || salesRole === 'MANAGER';

  const membersQ = useQuery({
    queryKey: ['orgs', orgId, 'members', 'opportunity-editor'],
    queryFn: () => request<{ members: Member[] }>(`/api/orgs/${orgId}/members`),
    enabled: Boolean(orgId && canManageOwners),
    staleTime: 60_000,
  });

  const openTasks = useMemo(
    () => data.tasks.filter((task) => !['COMPLETED', 'DISMISSED', 'CANCELLED'].includes(task.status)),
    [data.tasks],
  );

  async function saveCommercial() {
    if (!canEdit) return;
    if (status === 'PERDIDO' && !lostReason) {
      toast.error('Selecione o motivo da perda antes de salvar.');
      return;
    }
    const numericValue = value.trim() === '' ? null : Number(value.replace(',', '.'));
    if (numericValue !== null && (!Number.isFinite(numericValue) || numericValue < 0)) {
      toast.error('Informe um valor comercial válido.');
      return;
    }

    const payload: Opportunity360Patch = {
      status,
      negotiation_stage: stage || null,
      lost_reason: status === 'PERDIDO' ? lostReason : null,
      value: numericValue,
      expected_close_date: toIsoOrNull(expectedClose),
      next_action_at: toIsoOrNull(nextActionAt),
      notes: notes.trim() || null,
    };
    if (canManageOwners) payload.owner_user_id = ownerUserId || null;

    try {
      await updateOpportunity.mutateAsync(payload);
      toast.success('Oportunidade atualizada.');
    } catch (error) {
      toast.error(mutationMessage(error));
    }
  }

  async function assignSelf() {
    if (!currentUserId) return;
    try {
      await updateOpportunity.mutateAsync({ owner_user_id: currentUserId });
      setOwnerUserId(currentUserId);
      toast.success('Oportunidade atribuída a você.');
    } catch (error) {
      toast.error(mutationMessage(error));
    }
  }

  async function submitTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = taskTitle.trim();
    if (!title) return;
    const requestId = typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

    try {
      await createTask.mutateAsync({
        client_request_id: requestId,
        title,
        description: taskDescription.trim() || null,
        task_type: 'FOLLOW_UP',
        due_at: toIsoOrNull(taskDueAt),
      });
      setTaskTitle('');
      setTaskDescription('');
      setTaskDueAt('');
      toast.success('Tarefa criada.');
    } catch (error) {
      toast.error(mutationMessage(error));
    }
  }

  async function setTaskStatus(taskId: string, taskStatus: 'COMPLETED' | 'DISMISSED') {
    try {
      await updateTask.mutateAsync({ taskId, payload: { status: taskStatus } });
      toast.success(taskStatus === 'COMPLETED' ? 'Tarefa concluída.' : 'Tarefa dispensada.');
    } catch (error) {
      toast.error(mutationMessage(error));
    }
  }

  return (
    <main className="space-y-6">
      <Link
        href={`/oportunidades/360/${opportunityId}`}
        className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Voltar para a visão 360
      </Link>

      <PageHeader
        eyebrow="CRM · Oportunidade"
        title={`Gerenciar ${data.company.name || data.lead.company_name}`}
        description={`${offerProfileLabel(data.opportunity.offer_key)} · ${data.opportunity.score} pontos`}
        actions={<Badge variant={canEdit ? 'secondary' : 'outline'}>{canEdit ? 'Edição habilitada' : 'Somente leitura'}</Badge>}
      />

      {!canEdit && (
        <div role="status" className="rounded-lg border bg-muted/40 p-4 text-sm text-muted-foreground">
          Seu papel permite consultar esta oportunidade, mas não alterar o estado comercial.
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Estado comercial</CardTitle>
            <CardDescription>Atualize somente informações confirmadas durante o trabalho comercial.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <fieldset disabled={!canEdit || updateOpportunity.isPending} className="grid gap-4 sm:grid-cols-2 disabled:opacity-70">
              <div className="space-y-2">
                <Label htmlFor="opportunity-status">Status</Label>
                <select id="opportunity-status" className={SELECT_CLASS} value={status} onChange={(event) => setStatus(event.target.value)}>
                  {STATUS_OPTIONS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="opportunity-stage">Etapa de negociação</Label>
                <select id="opportunity-stage" className={SELECT_CLASS} value={stage} onChange={(event) => setStage(event.target.value)}>
                  {STAGE_OPTIONS.map(([key, label]) => <option key={key || 'none'} value={key}>{label}</option>)}
                </select>
              </div>

              {status === 'PERDIDO' && (
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="lost-reason">Motivo da perda</Label>
                  <select id="lost-reason" required className={SELECT_CLASS} value={lostReason} onChange={(event) => setLostReason(event.target.value)}>
                    <option value="">Selecione um motivo</option>
                    {LOST_REASON_OPTIONS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                  </select>
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="opportunity-value">Valor estimado (R$)</Label>
                <Input id="opportunity-value" inputMode="decimal" min="0" type="number" step="0.01" value={value} onChange={(event) => setValue(event.target.value)} placeholder="0,00" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="expected-close">Previsão de fechamento</Label>
                <Input id="expected-close" type="datetime-local" value={expectedClose} onChange={(event) => setExpectedClose(event.target.value)} />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="next-action-at">Próxima ação em</Label>
                <Input id="next-action-at" type="datetime-local" value={nextActionAt} onChange={(event) => setNextActionAt(event.target.value)} />
              </div>

              {canManageOwners ? (
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="opportunity-owner">Responsável</Label>
                  <select
                    id="opportunity-owner"
                    className={SELECT_CLASS}
                    value={ownerUserId}
                    disabled={membersQ.isLoading}
                    onChange={(event) => setOwnerUserId(event.target.value)}
                  >
                    <option value="">Não atribuído</option>
                    {(membersQ.data?.members ?? []).map((member) => (
                      <option key={member.user_id} value={member.user_id}>{member.name || member.email || member.user_id}</option>
                    ))}
                  </select>
                  {membersQ.isError && <p className="text-xs text-destructive">Não foi possível carregar os membros do workspace.</p>}
                </div>
              ) : !data.owner && currentUserId ? (
                <div className="sm:col-span-2">
                  <Button type="button" variant="outline" onClick={assignSelf} disabled={updateOpportunity.isPending}>
                    <UserRound className="h-4 w-4" aria-hidden="true" />
                    Assumir esta oportunidade
                  </Button>
                </div>
              ) : null}

              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="opportunity-notes">Notas comerciais</Label>
                <Textarea
                  id="opportunity-notes"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  maxLength={10_000}
                  rows={6}
                  placeholder="Contexto útil para o próximo contato, objeções, acordos e próximos passos…"
                />
                <p className="text-right text-xs text-muted-foreground">{notes.length.toLocaleString('pt-BR')} / 10.000</p>
              </div>
            </fieldset>

            {canEdit && (
              <div className="flex justify-end border-t pt-4">
                <Button onClick={saveCommercial} disabled={updateOpportunity.isPending}>
                  {updateOpportunity.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Save className="h-4 w-4" aria-hidden="true" />}
                  Salvar alterações
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Nova tarefa</CardTitle>
              <CardDescription>Registre o próximo trabalho sem sair da oportunidade.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={submitTask} className="space-y-4">
                <fieldset disabled={!canEdit || createTask.isPending} className="space-y-4 disabled:opacity-70">
                  <div className="space-y-2">
                    <Label htmlFor="task-title">Título</Label>
                    <Input id="task-title" value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} maxLength={180} required placeholder="Ex.: preparar proposta técnica" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="task-due">Prazo</Label>
                    <Input id="task-due" type="datetime-local" value={taskDueAt} onChange={(event) => setTaskDueAt(event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="task-description">Detalhes</Label>
                    <Textarea id="task-description" value={taskDescription} onChange={(event) => setTaskDescription(event.target.value)} maxLength={4000} rows={3} />
                  </div>
                </fieldset>
                {canEdit && (
                  <Button type="submit" className="w-full" disabled={createTask.isPending || !taskTitle.trim()}>
                    {createTask.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Plus className="h-4 w-4" aria-hidden="true" />}
                    Adicionar tarefa
                  </Button>
                )}
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Tarefas abertas</CardTitle>
              <CardDescription>{openTasks.length} item(ns) pendente(s) nesta oportunidade.</CardDescription>
            </CardHeader>
            <CardContent>
              {openTasks.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhuma tarefa aberta.</p>
              ) : (
                <ul className="space-y-3">
                  {openTasks.map((task) => (
                    <li key={task.id} className="rounded-lg border p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-medium">{task.title}</p>
                          {task.description && <p className="mt-1 text-sm text-muted-foreground">{task.description}</p>}
                          <p className="mt-2 text-xs text-muted-foreground">
                            {task.due_at ? new Date(task.due_at).toLocaleString('pt-BR') : 'Sem prazo definido'}
                          </p>
                        </div>
                        {canEdit && (
                          <div className="flex shrink-0 gap-1" aria-label={`Ações da tarefa ${task.title}`}>
                            <Button type="button" variant="ghost" size="icon" onClick={() => setTaskStatus(task.id, 'COMPLETED')} disabled={updateTask.isPending} aria-label={`Concluir ${task.title}`} title="Concluir tarefa">
                              <Check className="h-4 w-4" aria-hidden="true" />
                            </Button>
                            <Button type="button" variant="ghost" size="icon" onClick={() => setTaskStatus(task.id, 'DISMISSED')} disabled={updateTask.isPending} aria-label={`Dispensar ${task.title}`} title="Dispensar tarefa">
                              <X className="h-4 w-4" aria-hidden="true" />
                            </Button>
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}

function EditorSkeleton() {
  return (
    <main className="space-y-6" aria-busy="true" aria-label="Carregando editor da oportunidade">
      <Skeleton className="h-10 w-48" />
      <div className="space-y-2">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-10 w-2/3" />
      </div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <Skeleton className="h-[620px] rounded-xl" />
        <Skeleton className="h-[420px] rounded-xl" />
      </div>
    </main>
  );
}
