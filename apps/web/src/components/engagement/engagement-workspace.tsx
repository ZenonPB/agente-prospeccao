'use client';

import { FormEvent, useMemo, useState } from 'react';
import { Check, Clock3, Loader2, ListChecks, PauseCircle, Plus, RefreshCw, Route, Workflow } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import {
  useCommercialTasks,
  useCreateSequence,
  useCreateWorkflow,
  useDisableWorkflow,
  useEnrollments,
  usePatchCommercialTask,
  useProcessSequences,
  useSequences,
  useWorkflowRuns,
  useWorkflows,
} from '@/hooks/use-engagement';
import type { SequenceStep, SequenceStepType } from '@/lib/engagement-api';

const STEP_LABELS: Record<SequenceStepType, string> = {
  EMAIL: 'E-mail',
  CALL: 'Ligação',
  LINKEDIN: 'LinkedIn',
  WHATSAPP: 'WhatsApp',
  RESEARCH: 'Pesquisa',
  WAIT: 'Espera',
  CONDITION: 'Condição',
};

const TRIGGER_LABELS: Record<string, string> = {
  LEAD_CREATED: 'Lead criado',
  LEAD_SCORED: 'Lead avaliado',
  INTENT_DETECTED: 'Sinal de intenção detectado',
  EVENT_DETECTED: 'Evento detectado',
  CONTACT_FOUND: 'Contato encontrado',
  EMAIL_VERIFIED: 'E-mail confirmado',
  REPLY_RECEIVED: 'Resposta recebida',
  MEETING_SCHEDULED: 'Reunião marcada',
  WON: 'Venda ganha',
  DATA_STALE: 'Dados desatualizados',
  SAVED_SEARCH_MATCH: 'Novo resultado de busca salva',
};

const ACTION_LABELS: Record<string, string> = {
  CREATE_TASK: 'Criar tarefa',
  ENROLL_SEQUENCE: 'Entrar em sequência',
  NOTIFY: 'Gerar alerta',
  ENRICH: 'Atualizar dados',
  RERANK: 'Reavaliar prioridade',
  WEBHOOK: 'Enviar webhook',
  CRM_SYNC: 'Sincronizar com CRM',
};

const CONDITION_FIELD_LABELS: Record<string, string> = {
  'lead.status': 'Status do lead',
  'lead.score': 'Pontuação',
  'lead.opt_out': 'Opt-out',
};

const CONDITION_FALSE_LABELS: Record<string, string> = {
  skip: 'Pular etapa',
  stop: 'Encerrar sequência',
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function formatDate(value?: string | null) {
  if (!value) return 'Sem data definida';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Data indisponível' : date.toLocaleString('pt-BR');
}

function defaultStep(type: SequenceStepType): SequenceStep {
  return { type, delay_minutes: 0, title: '' };
}

export function EngagementWorkspace() {
  const sequences = useSequences();
  const enrollments = useEnrollments();
  const tasks = useCommercialTasks();
  const workflows = useWorkflows();
  const workflowRuns = useWorkflowRuns();
  const processSequences = useProcessSequences();
  const patchTask = usePatchCommercialTask();

  const activeEnrollments = useMemo(
    () => enrollments.data?.items.filter((item) => item.status === 'ACTIVE').length ?? 0,
    [enrollments.data],
  );
  const openTasks = tasks.data?.items.length ?? 0;
  const enabledWorkflows = workflows.data?.items.filter((item) => item.enabled).length ?? 0;

  async function processNow() {
    try {
      const result = await processSequences.mutateAsync();
      toast.success(`${result.processed} inscrição(ões) revisadas; ${result.tasks_created} tarefa(s) criada(s).`);
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível revisar as sequências.'));
    }
  }

  const loading = sequences.isLoading || enrollments.isLoading || tasks.isLoading || workflows.isLoading;
  const failed = sequences.isError || enrollments.isError || tasks.isError || workflows.isError;

  if (loading) {
    return <div className="flex min-h-48 items-center justify-center text-muted-foreground" role="status"><Loader2 className="mr-2 size-5 animate-spin" aria-hidden="true" />Carregando automações comerciais...</div>;
  }

  if (failed) {
    return <EmptyState title="Não foi possível carregar as automações" description="Atualize a página ou tente novamente em alguns instantes." />;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-3 sm:grid-cols-3" aria-label="Resumo do acompanhamento">
        <MetricCard icon={<Route className="size-4" aria-hidden="true" />} label="Inscrições ativas" value={activeEnrollments} />
        <MetricCard icon={<ListChecks className="size-4" aria-hidden="true" />} label="Tarefas abertas" value={openTasks} />
        <MetricCard icon={<Workflow className="size-4" aria-hidden="true" />} label="Fluxos ativos" value={enabledWorkflows} />
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-muted/20 p-4">
        <div>
          <p className="font-medium">Execução segura</p>
          <p className="text-sm text-muted-foreground">As etapas externas viram tarefas para o consultor. Esperas e condições avançam automaticamente sem disparar mensagens por um caminho paralelo.</p>
        </div>
        <Button variant="outline" onClick={() => void processNow()} disabled={processSequences.isPending}>
          {processSequences.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
          Revisar agora
        </Button>
      </div>

      <Tabs defaultValue="sequences">
        <TabsList className="flex h-auto flex-wrap">
          <TabsTrigger value="sequences">Sequências</TabsTrigger>
          <TabsTrigger value="tasks">Tarefas</TabsTrigger>
          <TabsTrigger value="workflows">Fluxos</TabsTrigger>
          <TabsTrigger value="runs">Histórico</TabsTrigger>
        </TabsList>
        <TabsContent value="sequences" className="pt-4"><SequenceSection /></TabsContent>
        <TabsContent value="tasks" className="pt-4"><TaskSection onPatch={async (id, status) => {
          try {
            await patchTask.mutateAsync({ id, status });
            toast.success(status === 'COMPLETED' ? 'Tarefa concluída.' : 'Tarefa arquivada.');
          } catch (error) {
            toast.error(errorMessage(error, 'Não foi possível atualizar a tarefa.'));
          }
        }} /></TabsContent>
        <TabsContent value="workflows" className="pt-4"><WorkflowSection /></TabsContent>
        <TabsContent value="runs" className="pt-4"><RunSection loading={workflowRuns.isLoading} items={workflowRuns.data?.items ?? []} /></TabsContent>
      </Tabs>
    </div>
  );
}

function MetricCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return <div className="rounded-xl border bg-card p-4"><div className="flex items-center gap-2 text-sm text-muted-foreground">{icon}{label}</div><p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p></div>;
}

function SequenceSection() {
  const sequences = useSequences();
  const createSequence = useCreateSequence();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [stepType, setStepType] = useState<SequenceStepType>('EMAIL');
  const [steps, setSteps] = useState<SequenceStep[]>([defaultStep('EMAIL')]);

  function addStep() {
    setSteps((current) => [...current, defaultStep(stepType)]);
  }

  function updateStep(index: number, patch: Partial<SequenceStep>) {
    setSteps((current) => current.map((step, position) => position === index ? { ...step, ...patch } : step));
  }

  function removeStep(index: number) {
    setSteps((current) => current.filter((_, position) => position !== index));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await createSequence.mutateAsync({ name: name.trim(), description: description.trim() || undefined, steps });
      setName('');
      setDescription('');
      setSteps([defaultStep('EMAIL')]);
      toast.success('Sequência criada.');
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível criar a sequência.'));
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1.15fr_1fr]">
      <Card>
        <CardHeader><CardTitle>Nova sequência</CardTitle><CardDescription>Monte uma rotina de abordagem. Cada atraso é relativo à etapa anterior.</CardDescription></CardHeader>
        <CardContent>
          <form className="space-y-5" onSubmit={submit}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2"><Label htmlFor="sequence-name">Nome</Label><Input id="sequence-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={160} required placeholder="Ex.: Evento MEJ — abordagem inicial" /></div>
              <div className="space-y-2"><Label htmlFor="sequence-description">Descrição</Label><Input id="sequence-description" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Quando usar esta sequência" /></div>
            </div>

            <div className="space-y-3">
              {steps.map((step, index) => (
                <div key={`${index}-${step.type}`} className="space-y-3 rounded-xl border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2"><Badge variant="secondary">{index + 1}</Badge><span className="font-medium">{STEP_LABELS[step.type]}</span></div>
                    {steps.length > 1 ? <Button type="button" variant="ghost" size="sm" onClick={() => removeStep(index)}>Remover</Button> : null}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2"><Label htmlFor={`delay-${index}`}>Aguardar após etapa anterior (min)</Label><Input id={`delay-${index}`} type="number" min={0} max={525600} value={step.delay_minutes} onChange={(event) => updateStep(index, { delay_minutes: Number(event.target.value) || 0 })} /></div>
                    <div className="space-y-2"><Label htmlFor={`title-${index}`}>Título interno</Label><Input id={`title-${index}`} value={step.title ?? ''} onChange={(event) => updateStep(index, { title: event.target.value })} placeholder="Ex.: Ligar para decisor" /></div>
                  </div>
                  {step.type === 'EMAIL' ? <div className="grid gap-3"><div className="space-y-2"><Label htmlFor={`subject-${index}`}>Assunto sugerido</Label><Input id={`subject-${index}`} value={step.subject ?? ''} onChange={(event) => updateStep(index, { subject: event.target.value })} /></div><div className="space-y-2"><Label htmlFor={`content-${index}`}>Mensagem sugerida</Label><Textarea id={`content-${index}`} value={step.content ?? ''} onChange={(event) => updateStep(index, { content: event.target.value })} rows={4} /></div></div> : null}
                  {step.type === 'CONDITION' ? <ConditionEditor value={step.config ?? {}} onChange={(config) => updateStep(index, { config })} index={index} /> : null}
                </div>
              ))}
            </div>

            <div className="flex flex-wrap items-end gap-2 rounded-lg border bg-muted/20 p-3">
              <div className="min-w-52 flex-1 space-y-2"><Label>Adicionar etapa</Label><Select value={stepType} onValueChange={(value) => { if (value) setStepType(value as SequenceStepType); }}><SelectTrigger className="w-full"><SelectValue>{(value) => STEP_LABELS[value as SequenceStepType] ?? (value as string)}</SelectValue></SelectTrigger><SelectContent>{Object.entries(STEP_LABELS).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div>
              <Button type="button" variant="outline" onClick={addStep}><Plus className="size-4" aria-hidden="true" />Adicionar</Button>
            </div>

            <Button type="submit" disabled={!name.trim() || createSequence.isPending}>{createSequence.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Route className="size-4" aria-hidden="true" />}Criar sequência</Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Sequências disponíveis</CardTitle><CardDescription>Versões novas não alteram inscrições que já estão em andamento.</CardDescription></CardHeader>
        <CardContent className="space-y-3">
          {(sequences.data?.items.length ?? 0) === 0 ? <EmptyState title="Nenhuma sequência criada" description="Crie uma sequência para padronizar a próxima abordagem sem automatizar canais indevidamente." /> : sequences.data?.items.map((sequence) => (
            <article key={sequence.id} className="rounded-xl border p-4">
              <div className="flex items-start justify-between gap-3"><div><h3 className="font-medium">{sequence.name}</h3><p className="mt-1 text-sm text-muted-foreground">{sequence.description || 'Sem descrição.'}</p></div><Badge variant="outline">v{sequence.version}</Badge></div>
              <div className="mt-3 flex flex-wrap gap-1.5">{sequence.steps.map((step, index) => <Badge key={`${sequence.id}-${index}`} variant="secondary">{index + 1}. {STEP_LABELS[step.type]}</Badge>)}</div>
            </article>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ConditionEditor({ value, onChange, index }: { value: Record<string, unknown>; onChange: (value: Record<string, unknown>) => void; index: number }) {
  const field = String(value.field ?? 'lead.status');
  const operator = String(value.operator ?? 'eq');
  const onFalse = String(value.on_false ?? 'skip');
  return <div className="grid gap-3 sm:grid-cols-3"><div className="space-y-2"><Label htmlFor={`condition-field-${index}`}>Dado</Label><Select value={field} onValueChange={(next) => { if (next) onChange({ ...value, field: next }); }}><SelectTrigger id={`condition-field-${index}`} className="w-full"><SelectValue>{(value) => CONDITION_FIELD_LABELS[value as string] ?? (value as string)}</SelectValue></SelectTrigger><SelectContent><SelectItem value="lead.status">Status do lead</SelectItem><SelectItem value="lead.score">Pontuação</SelectItem><SelectItem value="lead.opt_out">Opt-out</SelectItem></SelectContent></Select></div><div className="space-y-2"><Label htmlFor={`condition-value-${index}`}>Valor esperado</Label><Input id={`condition-value-${index}`} value={String(value.value ?? '')} onChange={(event) => onChange({ ...value, value: event.target.value, operator })} /></div><div className="space-y-2"><Label>Se não atender</Label><Select value={onFalse} onValueChange={(next) => { if (next) onChange({ ...value, on_false: next, operator }); }}><SelectTrigger className="w-full"><SelectValue>{(value) => CONDITION_FALSE_LABELS[value as string] ?? (value as string)}</SelectValue></SelectTrigger><SelectContent><SelectItem value="skip">Pular etapa</SelectItem><SelectItem value="stop">Encerrar sequência</SelectItem></SelectContent></Select></div></div>;
}

function TaskSection({ onPatch }: { onPatch: (id: string, status: 'COMPLETED' | 'DISMISSED') => Promise<void> }) {
  const tasks = useCommercialTasks();
  if ((tasks.data?.items.length ?? 0) === 0) return <EmptyState title="Nenhuma tarefa aberta" description="Quando uma etapa de contato estiver pronta, ela aparecerá aqui para o consultor executar." />;
  return <div className="grid gap-3 lg:grid-cols-2">{tasks.data?.items.map((task) => <article key={task.id} className="rounded-xl border bg-card p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{STEP_LABELS[task.task_type as SequenceStepType] ?? task.task_type}</p><h3 className="mt-1 font-medium">{task.title}</h3><p className="mt-1 text-sm text-muted-foreground">{task.description || 'Sem observações adicionais.'}</p></div><Clock3 className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" /></div><p className="mt-3 text-xs text-muted-foreground">Prazo: {formatDate(task.due_at)}</p><div className="mt-4 flex gap-2"><Button size="sm" onClick={() => void onPatch(task.id, 'COMPLETED')}><Check className="size-4" aria-hidden="true" />Concluir</Button><Button size="sm" variant="outline" onClick={() => void onPatch(task.id, 'DISMISSED')}><PauseCircle className="size-4" aria-hidden="true" />Arquivar</Button></div></article>)}</div>;
}

function WorkflowSection() {
  const workflows = useWorkflows();
  const sequences = useSequences();
  const createWorkflow = useCreateWorkflow();
  const disableWorkflow = useDisableWorkflow();
  const [name, setName] = useState('');
  const [trigger, setTrigger] = useState('LEAD_SCORED');
  const [action, setAction] = useState('CREATE_TASK');
  const [sequenceId, setSequenceId] = useState('');
  const [minScore, setMinScore] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const numericScore = Number(minScore);
    const conditions = minScore.trim() && Number.isFinite(numericScore) ? [{ field: 'score', operator: 'gte', value: numericScore }] : [];
    const config = action === 'CREATE_TASK'
      ? { title: 'Revisar oportunidade acionada pelo workflow', task_type: 'RESEARCH' }
      : action === 'NOTIFY'
        ? { title: 'Nova oportunidade requer atenção' }
        : action === 'ENROLL_SEQUENCE'
          ? { sequence_id: sequenceId }
          : {};
    try {
      await createWorkflow.mutateAsync({ name: name.trim(), trigger_type: trigger, conditions, actions: [{ type: action, config }] });
      setName('');
      setMinScore('');
      toast.success('Fluxo criado.');
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível criar o fluxo.'));
    }
  }

  const requiresSequence = action === 'ENROLL_SEQUENCE';
  return <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]"><Card><CardHeader><CardTitle>Novo fluxo</CardTitle><CardDescription>Automatize decisões previsíveis mantendo ações externas sensíveis sob controle.</CardDescription></CardHeader><CardContent><form className="space-y-4" onSubmit={submit}><div className="space-y-2"><Label htmlFor="workflow-name">Nome</Label><Input id="workflow-name" value={name} onChange={(event) => setName(event.target.value)} required maxLength={160} placeholder="Ex.: Lead quente — criar tarefa" /></div><div className="space-y-2"><Label>Quando</Label><Select value={trigger} onValueChange={(value) => { if (value) setTrigger(value); }}><SelectTrigger className="w-full"><SelectValue>{(value) => TRIGGER_LABELS[value as string] ?? (value as string)}</SelectValue></SelectTrigger><SelectContent>{(workflows.data?.triggers ?? Object.keys(TRIGGER_LABELS)).map((item) => <SelectItem key={item} value={item}>{TRIGGER_LABELS[item] ?? item}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label htmlFor="workflow-score">Pontuação mínima (opcional)</Label><Input id="workflow-score" type="number" min={0} max={100} value={minScore} onChange={(event) => setMinScore(event.target.value)} placeholder="Ex.: 80" /></div><div className="space-y-2"><Label>Ação</Label><Select value={action} onValueChange={(value) => { if (value) setAction(value); }}><SelectTrigger className="w-full"><SelectValue>{(value) => ACTION_LABELS[value as string] ?? (value as string)}</SelectValue></SelectTrigger><SelectContent>{Object.entries(ACTION_LABELS).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div>{requiresSequence ? <div className="space-y-2"><Label>Sequência</Label><Select value={sequenceId || null} onValueChange={(value) => setSequenceId(value ?? '')}><SelectTrigger className="w-full"><SelectValue placeholder="Escolha uma sequência">{(value) => ((sequences.data?.items ?? []).find((item) => item.id === value)?.name ?? 'Escolha uma sequência')}</SelectValue></SelectTrigger><SelectContent>{(sequences.data?.items ?? []).filter((item) => item.enabled).map((item) => <SelectItem key={item.id} value={item.id}>{item.name} · v{item.version}</SelectItem>)}</SelectContent></Select></div> : null}<Button type="submit" disabled={!name.trim() || createWorkflow.isPending || (requiresSequence && !sequenceId)}>{createWorkflow.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Workflow className="size-4" aria-hidden="true" />}Criar workflow</Button></form></CardContent></Card><Card><CardHeader><CardTitle>Workflows configurados</CardTitle><CardDescription>Cada execução possui chave idempotente e histórico próprio.</CardDescription></CardHeader><CardContent className="space-y-3">{(workflows.data?.items.length ?? 0) === 0 ? <EmptyState title="Nenhum workflow" description="Crie uma regra simples para transformar eventos comerciais em tarefas, alertas ou outras ações controladas." /> : workflows.data?.items.map((workflow) => <article key={workflow.id} className="rounded-xl border p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-medium">{workflow.name}</h3><p className="mt-1 text-sm text-muted-foreground">{TRIGGER_LABELS[workflow.trigger_type] ?? workflow.trigger_type} → {workflow.actions.map((item) => ACTION_LABELS[item.type] ?? item.type).join(', ')}</p></div><Badge variant={workflow.enabled ? 'outline' : 'secondary'}>{workflow.enabled ? 'Ativo' : 'Desativado'}</Badge></div>{workflow.enabled ? <Button className="mt-3" variant="ghost" size="sm" onClick={() => void disableWorkflow.mutateAsync(workflow.id).catch((error) => toast.error(errorMessage(error, 'Não foi possível desativar.')))}>Desativar</Button> : null}</article>)}</CardContent></Card></div>;
}

function RunSection({ loading, items }: { loading: boolean; items: Array<{ id: string; trigger_type: string; event_key: string; status: string; started_at?: string | null; action_results: Array<Record<string, unknown>> }> }) {
  if (loading) return <div className="flex min-h-40 items-center justify-center text-muted-foreground"><Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />Carregando histórico...</div>;
  if (!items.length) return <EmptyState title="Nenhuma execução registrada" description="O histórico aparecerá aqui quando um fluxo receber um evento elegível." />;
  return <div className="space-y-3">{items.map((run) => <article key={run.id} className="flex flex-col gap-2 rounded-xl border bg-card p-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-medium">{TRIGGER_LABELS[run.trigger_type] ?? run.trigger_type}</p><p className="text-sm text-muted-foreground">{formatDate(run.started_at)} · {run.action_results.length} ação(ões)</p></div><Badge variant={run.status === 'COMPLETED' ? 'secondary' : 'outline'}>{run.status === 'COMPLETED' ? 'Concluído' : run.status === 'SKIPPED' ? 'Não aplicável' : run.status === 'FAILED' ? 'Falhou' : run.status}</Badge></article>)}</div>;
}
