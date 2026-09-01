'use client';

import { useMemo, useCallback, useState } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { GripVertical, Clock, AlertTriangle, AlertCircle, RefreshCw, Loader2, UserPlus, User, Check, MoreHorizontal, MessageCircle, ArrowRight, Filter, Users, BrainCircuit } from 'lucide-react';
import { DragDropContext, Droppable, Draggable, DropResult, DragStart } from '@hello-pangea/dnd';
import { useUpdateLeadStatus, useAssignLead, useOrgMembership, useOrgMembers, useRecordWhatsAppClick, useSlaAlerts, useAllLeads } from '@/hooks/use-api';
import { ScoreFeedbackDialog } from '@/components/vendas/score-feedback-dialog';
import type { SlaAlertItem } from '@/types';
import { whatsAppLink } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';

interface KanbanColumn {
  id: string;
  title: string;
  color: string;
  status: string[];
}

const COLUMNS: KanbanColumn[] = [
  { id: 'NOVO', title: 'Novos Encontrados', color: 'bg-slate-500', status: ['NOVO'] },
  { id: 'QUALIFICADO', title: 'Aptos para Contato', color: 'bg-emerald-500', status: ['QUALIFICADO'] },
  { id: 'CONTATADO', title: 'Mensagem Enviada', color: 'bg-blue-500', status: ['CONTATADO'] },
  { id: 'RESPONDIDO', title: 'Cliente Respondeu', color: 'bg-purple-500', status: ['RESPONDIDO'] },
  { id: 'REUNIAO_MARCADA', title: 'Reunião Agendada', color: 'bg-amber-500', status: ['REUNIAO_MARCADA'] },
  { id: 'REUNIAO_FEITA', title: 'Reunião Realizada', color: 'bg-teal-500', status: ['REUNIAO_FEITA'] },
  { id: 'PROPOSTA_ENVIADA', title: 'Proposta Enviada', color: 'bg-pink-500', status: ['PROPOSTA_ENVIADA'] },
];

const NEG_STAGE_LABELS: Record<string, string> = {
  RD: 'Demonstração',
  ORCAMENTO: 'Orçamento',
  RP: 'Proposta',
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type LeadData = Record<string, any>;

function groupLeadsByColumn(leads: LeadData[]): Record<string, LeadData[]> {
  const grouped: Record<string, LeadData[]> = {};
  COLUMNS.forEach((col) => {
    grouped[col.id] = [];
  });

  leads.forEach((lead) => {
    const colId = COLUMNS.find((c) => c.status.includes(lead.status))?.id;
    if (colId && grouped[colId]) {
      grouped[colId].push(lead);
    }
  });

  // Dentro de cada coluna: maior score primeiro, depois prioridade (HOT > WARM > COLD).
  const priorityRank: Record<string, number> = { HOT: 0, WARM: 1, COLD: 2 };
  Object.values(grouped).forEach((list) => {
    list.sort((a, b) => {
      const scoreDiff = (b.qualification_score || 0) - (a.qualification_score || 0);
      if (scoreDiff !== 0) return scoreDiff;
      const pa = priorityRank[a.priority] ?? 3;
      const pb = priorityRank[b.priority] ?? 3;
      return pa - pb;
    });
  });

  return grouped;
}

function KanbanColumnSkeleton() {
  return (
    <div className="w-[260px] min-w-[260px] flex-shrink-0 sm:w-[300px] sm:min-w-[300px]">
      <div className="rounded-xl bg-muted/40 p-3">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Skeleton className="h-2.5 w-2.5 rounded-full" />
            <Skeleton className="h-4 w-28" />
          </div>
          <Skeleton className="h-5 w-6 rounded-full" />
        </div>
        <div className="space-y-2.5">
          {[1, 2].map((i) => (
            <Card key={i}>
              <CardContent className="p-3.5">
                <div className="mb-3 flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-4 w-4" />
                    <Skeleton className="h-4 w-24" />
                  </div>
                  <Skeleton className="h-5 w-10 rounded-full" />
                </div>
                <Skeleton className="h-4 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

const SALES_STATUSES = 'NOVO,QUALIFICADO,CONTATADO,RESPONDIDO,REUNIAO_MARCADA,REUNIAO_FEITA,PROPOSTA_ENVIADA';

export function KanbanBoard() {
  const router = useRouter();
  const { data: session } = useSession();
  const currentUserId = (session?.user as { id?: string } | undefined)?.id;
  const updateStatus = useUpdateLeadStatus();
  const assignLead = useAssignLead();
  const recordWhatsApp = useRecordWhatsAppClick();
  const { data: membership } = useOrgMembership();
  const orgId = membership?.organization?.id;
  const myRole = membership?.membership?.role;
  const mySalesRole = membership?.membership?.sales_role;
  const canAssignOthers = myRole === 'OWNER' || myRole === 'ADMIN' || mySalesRole === 'MANAGER';
  const { data: membersData } = useOrgMembers(canAssignOthers ? orgId : undefined);

  const [myLeadsOnly, setMyLeadsOnly] = useState(false);
  // Feedback de score: qual lead está sendo corrigido e se o diálogo está aberto.
  const [feedbackLead, setFeedbackLead] = useState<LeadData | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  const { data, isLoading, isError, error, refetch } = useAllLeads({
    status: SALES_STATUSES,
    assigned: myLeadsOnly && currentUserId ? currentUserId : undefined,
  });
  const { data: slaData } = useSlaAlerts(100);

  const columns = useMemo(
    () => groupLeadsByColumn(data?.leads || []),
    [data?.leads]
  );

  // Estado local espelhado das colunas durante o drag: sem optimistic update,
  // o card "volta" para a posição antiga ao soltar (e só reposiciona quando o
  // refetch termina) — parece que o drag não funciona. Aqui movemos o card
  // imediatamente e desfazemos em caso de erro.
  const [draftColumns, setDraftColumns] = useState<Record<string, LeadData[]> | null>(null);
  const visibleColumns = draftColumns ?? columns;

  // Coluna de origem do arraste em curso: usada para realçar os alvos de
  // drop e esmaecer os cartões que não estão sendo arrastados.
  const [activeDragFrom, setActiveDragFrom] = useState<string | null>(null);

  const onDragStart = useCallback((start: DragStart) => {
    setActiveDragFrom(start.source.droppableId);
  }, []);

  // Alerta de leads parados por lead: mapeia o alerta e o conta por coluna
  // (coluna do status do alerta).
  const slaByLead = useMemo(() => {
    const map: Record<string, SlaAlertItem> = {};
    (slaData?.alerts || []).forEach((alert) => {
      map[alert.id] = alert;
    });
    return map;
  }, [slaData]);

  const slaCountByColumn = useMemo(() => {
    const counts: Record<string, number> = {};
    COLUMNS.forEach((col) => {
      counts[col.id] = 0;
    });
    (slaData?.alerts || []).forEach((alert) => {
      const col = COLUMNS.find((c) => c.status.includes(alert.status || ''));
      if (col) counts[col.id] += 1;
    });
    return counts;
  }, [slaData]);

  const slaAlertsCount = Object.values(slaByLead).length;

  const onDragEnd = useCallback((result: DropResult) => {
    const { draggableId, destination, source } = result;
    setActiveDragFrom(null);
    if (!destination) return;
    if (destination.droppableId === source.droppableId) return;

    const newStatus = destination.droppableId;
    setDraftColumns((current) => {
      const base = current ?? columns;
      const lead = (base[source.droppableId] || []).find((l) => l.id === draggableId);
      if (!lead) return current;
      const next = { ...base };
      next[source.droppableId] = (base[source.droppableId] || []).filter((l) => l.id !== draggableId);
      next[destination.droppableId] = [...(base[destination.droppableId] || []), lead];
      return next;
    });

    updateStatus.mutate(
      { id: draggableId, status: newStatus },
      {
        onSuccess: (res) => {
          setDraftColumns(null);
          const colTitle = COLUMNS.find((c) => c.id === newStatus)?.title || newStatus;
          toast.success(`Lead movido para ${colTitle}`, {
            description: res.suggested_next_action_at
              ? `Próxima ação sugerida: ${new Date(res.suggested_next_action_at).toLocaleDateString('pt-BR')}`
              : undefined,
          });
        },
        onError: () => {
          setDraftColumns(null);
          toast.error('Erro ao mover lead');
        },
      }
    );
  }, [columns, updateStatus]);

  const onAssignToMe = useCallback((leadId: string) => {
    if (!currentUserId) return;
    assignLead.mutate(
      { id: leadId, assignedToId: currentUserId },
      {
        onSuccess: () => {
          toast.success('Lead atribuído a você.');
        },
        onError: () => {
          toast.error('Não foi possível atribuir o lead.');
        },
      }
    );
  }, [currentUserId, assignLead]);

  const onAssignTo = useCallback((leadId: string, userId: string | null, name?: string) => {
    assignLead.mutate(
      { id: leadId, assignedToId: userId },
      {
        onSuccess: () => {
          toast.success(userId ? `Lead atribuído a ${name || 'consultor'}.` : 'Lead desatribuído.');
        },
        onError: () => {
          toast.error('Não foi possível atribuir o lead.');
        },
      }
    );
  }, [assignLead]);

  const totalLeads = Object.values(visibleColumns).reduce((acc, col) => acc + col.length, 0);

  if (isLoading) {
    return (
      <div className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory">
        {COLUMNS.map((col) => (
          <KanbanColumnSkeleton key={col.id} />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <Card className="border-red-200 bg-red-50/50">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-red-600">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <p className="text-sm font-medium">Erro ao carregar leads</p>
          </div>
          <p className="mt-1 text-xs text-red-500">
            {error instanceof Error ? error.message : 'Tente novamente mais tarde'}
          </p>
          <Button variant="outline" size="sm" className="mt-3" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-3 w-3" />
            Tentar novamente
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Resumo do Funil de Negociação */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border bg-card p-3 shadow-sm">
          <p className="text-xs font-medium text-muted-foreground">Total no Pipeline</p>
          <p className="font-heading text-xl font-bold tracking-tight text-foreground">{totalLeads}</p>
        </div>
        <div className="rounded-lg border bg-card p-3 shadow-sm">
          <p className="text-xs font-medium text-muted-foreground">Aptos p/ Contato</p>
          <p className="font-heading text-xl font-bold tracking-tight text-emerald-600">{visibleColumns['QUALIFICADO']?.length || 0}</p>
        </div>
        <div className="rounded-lg border bg-card p-3 shadow-sm">
          <p className="text-xs font-medium text-muted-foreground">Em Abordagem</p>
          <p className="font-heading text-xl font-bold tracking-tight text-blue-600">
            {(visibleColumns['CONTATADO']?.length || 0) + (visibleColumns['RESPONDIDO']?.length || 0)}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3 shadow-sm">
          <p className="text-xs font-medium text-muted-foreground">Reuniões / Propostas</p>
          <p className="font-heading text-xl font-bold tracking-tight text-amber-600">
            {(visibleColumns['REUNIAO_MARCADA']?.length || 0) + (visibleColumns['REUNIAO_FEITA']?.length || 0) + (visibleColumns['PROPOSTA_ENVIADA']?.length || 0)}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <p className="hidden text-sm font-medium text-muted-foreground sm:block">
            Segure o topo de um cartão e arraste entre as colunas para atualizar a etapa
          </p>
          <p className="text-sm font-medium text-muted-foreground sm:hidden">
            Toque no cartão para abrir o lead · segure o topo para arrastar de etapa
          </p>
        </div>
        <div className="flex items-center gap-2">
          {currentUserId && (
            <Button
              variant={myLeadsOnly ? 'default' : 'outline'}
              size="sm"
              className="h-8 gap-1.5 rounded-full px-3 text-xs font-medium"
              onClick={() => setMyLeadsOnly(!myLeadsOnly)}
            >
              {myLeadsOnly ? (
                <Check className="h-3.5 w-3.5" />
              ) : (
                <Users className="h-3.5 w-3.5" />
              )}
              Meus Leads
            </Button>
          )}
          {slaAlertsCount > 0 && (
            <div className="flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-medium text-red-700">
              <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
              {slaAlertsCount} lead{slaAlertsCount !== 1 ? 's' : ''} parado{slaAlertsCount !== 1 ? 's' : ''}
            </div>
          )}
        </div>
      </div>

      <DragDropContext onDragStart={onDragStart} onDragEnd={onDragEnd}>
        <div
          className={`h-[min(60dvh,calc(100dvh-22rem))] max-h-[calc(100dvh-22rem)] min-h-[280px] overflow-x-auto overflow-y-auto rounded-xl pb-4 ${activeDragFrom ? 'cursor-grabbing select-none' : 'snap-x snap-mandatory'}`}
        >
          <div className="flex w-max gap-3 px-1 sm:gap-4">
            {COLUMNS.map((column) => (
              <div
                key={column.id}
                className="flex w-[260px] min-w-[260px] flex-shrink-0 snap-start flex-col sm:w-[300px] sm:min-w-[300px]"
              >
              <div className="rounded-xl bg-muted/40 p-3">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`h-2.5 w-2.5 rounded-full ${column.color}`} />
                    <h3 className="text-sm font-semibold">{column.title}</h3>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Badge variant="secondary" className="text-xs font-semibold">
                      {visibleColumns[column.id]?.length || 0}
                    </Badge>
                    {slaCountByColumn[column.id] > 0 && (
                      <Badge
                        variant="outline"
                        className="gap-1 border-red-200 bg-red-50 px-1.5 text-[11px] font-semibold text-red-700"
                        title="Leads parados nesta etapa"
                      >
                        <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                        {slaCountByColumn[column.id]}
                      </Badge>
                    )}
                  </div>
                </div>

                <Droppable droppableId={column.id}>
                  {(provided, snapshot) => (
                    <div
                      ref={provided.innerRef}
                      {...provided.droppableProps}
                      className={`min-h-[120px] space-y-2.5 rounded-lg border-2 border-dashed p-2 transition-colors duration-200 ${
                        snapshot.isDraggingOver
                          ? 'border-primary/60 bg-primary/5'
                          : activeDragFrom
                            ? 'border-border/70 bg-muted/30'
                            : 'border-transparent bg-transparent'
                      }`}
                    >
                      {(visibleColumns[column.id] || []).map((lead, index) => (
                        <Draggable key={lead.id} draggableId={lead.id} index={index}>
                          {(provided, snapshot) => (
                            <div
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              role="link"
                              tabIndex={0}
                              aria-label={`Abrir lead ${lead.company_name}`}
                              onClick={(e) => {
                                if (snapshot.isDragging) return;
                                e.stopPropagation();
                                router.push(`/oportunidades/${lead.id}`);
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.preventDefault();
                                  e.stopPropagation();
                                  router.push(`/oportunidades/${lead.id}`);
                                }
                              }}
                              className={`group rounded-lg border bg-card p-3.5 shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                                snapshot.isDragging
                                  ? 'rotate-[1.5deg] scale-[1.03] shadow-xl ring-2 ring-primary/40'
                                  : `transition-[border-color,box-shadow] duration-150 ${
                                      activeDragFrom
                                        ? 'opacity-40 saturate-50'
                                        : 'hover:border-primary/20 hover:shadow-md'
                                    }`
                              }`}
                            >
                              {/* Cabeçalho do cartão = alça de arraste. Área generosa
                                  (puxador + nome + nota): segurar aqui arrasta; tocar
                                  abre o lead. O corpo fica livre para os botões. */}
                              <div
                                {...provided.dragHandleProps}
                                className="-mx-1 mb-2 flex cursor-grab touch-none select-none items-start justify-between gap-2 rounded-lg px-1 py-1 transition-colors hover:bg-muted/60 active:cursor-grabbing"
                                title="Segure e arraste para mudar de etapa"
                              >
                                <div className="flex min-w-0 items-center gap-2">
                                  <span
                                    className="shrink-0 rounded p-0.5 text-muted-foreground/50 transition-colors group-hover:text-muted-foreground"
                                    aria-hidden="true"
                                  >
                                    <GripVertical className="h-5 w-5" />
                                  </span>
                                  <h4 className="truncate font-medium">{lead.company_name}</h4>
                                </div>
                                {lead.qualification_score != null ? (
                                  <Badge className="shrink-0 bg-emerald-100 text-emerald-700">
                                    {lead.qualification_score}
                                  </Badge>
                                ) : (
                                  <Badge variant="outline" className="shrink-0 text-xs text-muted-foreground">
                                    Sem score
                                  </Badge>
                                )}
                              </div>
                              {(lead.negotiation_stage || lead.contract_outcome) && (
                                <div className="mb-2 flex flex-wrap gap-1.5">
                                  {lead.negotiation_stage && (
                                    <Badge variant="outline" className="bg-violet-50 text-violet-700 text-xs">
                                      {NEG_STAGE_LABELS[lead.negotiation_stage] ?? lead.negotiation_stage}
                                    </Badge>
                                  )}
                                  {lead.contract_outcome && (
                                    <Badge
                                      variant="outline"
                                      className={
                                        lead.contract_outcome === 'APROVADO'
                                          ? 'bg-emerald-50 text-emerald-700 text-xs'
                                          : lead.contract_outcome === 'REPROVADO'
                                            ? 'bg-red-50 text-red-700 text-xs'
                                            : 'bg-amber-50 text-amber-700 text-xs'
                                      }
                                    >
                                      {lead.contract_outcome === 'EM_ANALISE' ? 'Em análise' : lead.contract_outcome}
                                    </Badge>
                                  )}
                                </div>
                              )}
                              {slaByLead[lead.id] && (
                                <div className="mb-2 flex flex-wrap gap-1.5">
                                  <Badge
                                    variant="outline"
                                    className="gap-1 border-red-200 bg-red-50 text-red-700 text-xs"
                                    title={slaByLead[lead.id].alert_label}
                                  >
                                    <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                                    Parado há {slaByLead[lead.id].days_since}d
                                  </Badge>
                                </div>
                              )}
                              <p className="mb-3 text-sm text-muted-foreground">
                                {lead.category || 'Sem categoria'} • {lead.city || 'Não informado'}{lead.state ? `, ${lead.state}` : ''}
                              </p>
                              <div className="mb-2 flex items-center gap-2 text-xs">
                                 {lead.value ? (
                                   <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2 py-0.5 font-medium text-emerald-600 dark:text-emerald-400">
                                     R$ {lead.value.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                                   </span>
                                 ) : null}
                                 {lead.assigned_to_id ? (
                                  <span
                                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${
                                      lead.assigned_to_id === currentUserId
                                        ? 'bg-primary/10 text-primary'
                                        : 'bg-muted text-muted-foreground'
                                    }`}
                                  >
                                    {lead.assigned_to_id === currentUserId ? (
                                      <Check className="h-3 w-3" />
                                    ) : (
                                      <User className="h-3 w-3" />
                                    )}
                                    {lead.assigned_to_id === currentUserId
                                      ? 'Seu lead'
                                      : (lead.assigned_to_name || 'Atribuído')}
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-muted-foreground">
                                    <User className="h-3 w-3" />
                                    Não atribuído
                                  </span>
                                )}
                              </div>
                              <div className="flex flex-wrap items-center justify-between gap-1.5 text-xs text-muted-foreground">
                                <div className="flex shrink-0 items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  <span>{Math.floor((Date.now() - new Date(lead.created_at).getTime()) / (1000 * 60 * 60 * 24))} dias</span>
                                </div>
                                <div className="flex min-w-0 flex-wrap items-center justify-end gap-1.5">
                                  {column.id === 'QUALIFICADO' && (
                                    <div className="flex items-center gap-1 text-emerald-600">
                                      <AlertCircle className="h-3 w-3" />
                                      <span>Aguardando 1º contato</span>
                                    </div>
                                  )}
                                  {column.id === 'CONTATADO' && (
                                    <div className="flex items-center gap-1 text-amber-600">
                                      <AlertTriangle className="h-3 w-3" />
                                      <span>Aguardando resposta</span>
                                    </div>
                                  )}
                                   {whatsAppLink(lead.whatsapp || lead.phone) && (
                                     <Button
                                       variant="ghost"
                                       size="icon"
                                       className="h-11 w-11 shrink-0 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground sm:h-6 sm:w-6"
                                       disabled={recordWhatsApp.isPending}
                                       onClick={(e) => {
                                         e.stopPropagation();
                                         recordWhatsApp.mutate(
                                           { leadId: lead.id },
                                           {
                                             onSuccess: (res) => {
                                               if (res.whatsapp_url) {
                                                 window.open(res.whatsapp_url, '_blank');
                                                 toast.success('WhatsApp acionado e registrado');
                                               }
                                             },
                                             onError: () => {
                                               const fallback = whatsAppLink(lead.whatsapp || lead.phone);
                                               if (fallback) window.open(fallback, '_blank');
                                             },
                                           }
                                         );
                                       }}
                                       title="Abrir WhatsApp e registrar na trilha"
                                       aria-label={`Abrir WhatsApp de ${lead.company_name}`}
                                     >
                                       {recordWhatsApp.isPending && recordWhatsApp.variables?.leadId === lead.id ? (
                                         <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                       ) : (
                                         <MessageCircle className="h-3.5 w-3.5" />
                                       )}
                                     </Button>
                                   )}
                                  {!lead.assigned_to_id && (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="h-11 shrink-0 gap-1.5 px-3 text-xs sm:h-6 sm:gap-1 sm:px-2 sm:text-[11px]"
                                      disabled={assignLead.isPending && assignLead.variables?.id === lead.id}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        onAssignToMe(lead.id);
                                      }}
                                    >
                                      {assignLead.isPending && assignLead.variables?.id === lead.id ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                      ) : (
                                        <UserPlus className="h-3 w-3" />
                                      )}
                                      Atribuir a mim
                                    </Button>
                                  )}
                                  {canAssignOthers && (
                                    <DropdownMenu>
                                      <DropdownMenuTrigger
                                        render={
                                          <Button
                                            data-tour="vendas-card-menu"
                                            variant="ghost"
                                            size="icon"
                                            className="h-11 w-11 shrink-0 sm:h-6 sm:w-6"
                                            onClick={(e: { stopPropagation: () => void }) => e.stopPropagation()}
                                            aria-label="Atribuir lead"
                                          >
                                            <MoreHorizontal className="h-3.5 w-3.5" />
                                          </Button>
                                        }
                                      />
                                      <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
                                        <DropdownMenuGroup>
                                          <DropdownMenuLabel>Atribuir para</DropdownMenuLabel>
                                          <DropdownMenuSeparator />
                                          <DropdownMenuItem
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              onAssignTo(lead.id, currentUserId as string, 'você');
                                            }}
                                            disabled={!currentUserId}
                                          >
                                            <User className="h-3.5 w-3.5" />
                                            Você
                                          </DropdownMenuItem>
                                          {membersData?.members
                                            .filter((m) => m.user_id !== currentUserId)
                                            .map((m) => (
                                              <DropdownMenuItem
                                                key={m.user_id}
                                                onClick={(e) => {
                                                  e.stopPropagation();
                                                  onAssignTo(lead.id, m.user_id, m.name);
                                                }}
                                              >
                                                <User className="h-3.5 w-3.5" />
                                                {m.name || m.email}
                                              </DropdownMenuItem>
                                            ))}
                                          <DropdownMenuSeparator />
                                          <DropdownMenuItem
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              onAssignTo(lead.id, null);
                                            }}
                                          >
                                            Desatribuir
                                          </DropdownMenuItem>
                                        </DropdownMenuGroup>
                                      </DropdownMenuContent>
                                    </DropdownMenu>
                                  )}
                                  {/* Fallback acessível por toque: mover de etapa sem arrastar. */}
                                  <DropdownMenu>
                                    <DropdownMenuTrigger
                                      render={
                                        <Button
                                          variant="outline"
                                          size="icon"
                                          className="h-11 w-11 shrink-0 sm:h-8 sm:w-8"
                                          onClick={(e: { stopPropagation: () => void }) => e.stopPropagation()}
                                          aria-label={`Mover ${lead.company_name} para outra etapa`}
                                        >
                                          <ArrowRight className="h-3.5 w-3.5" />
                                        </Button>
                                      }
                                    />
                                    <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
                                      <DropdownMenuGroup>
                                        <DropdownMenuLabel>Mover para</DropdownMenuLabel>
                                        <DropdownMenuSeparator />
                                        {COLUMNS.filter((c) => c.id !== column.id).map((c) => (
                                          <DropdownMenuItem
                                            key={c.id}
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              updateStatus.mutate(
                                                { id: lead.id, status: c.id },
                                                {
                                                  onSuccess: (res) => {
                                                    toast.success(`Lead movido para ${c.title}`, {
                                                      description: res.suggested_next_action_at
                                                        ? `Próxima ação sugerida: ${new Date(res.suggested_next_action_at).toLocaleDateString('pt-BR')}`
                                                        : undefined,
                                                    });
                                                  },
                                                  onError: () => toast.error('Erro ao mover lead'),
                                                }
                                              );
                                            }}
                                          >
                                            {c.title}
                                          </DropdownMenuItem>
                                        ))}
                                        <DropdownMenuSeparator />
                                        <DropdownMenuItem
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setFeedbackLead(lead);
                                            setFeedbackOpen(true);
                                          }}
                                        >
                                          <BrainCircuit className="mr-2 h-3.5 w-3.5" />
                                          Discordar do score
                                        </DropdownMenuItem>
                                      </DropdownMenuGroup>
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                </div>
                              </div>
                            </div>
                          )}
                        </Draggable>
                      ))}
                      {provided.placeholder}
                      {(visibleColumns[column.id] || []).length === 0 && !snapshot.isDraggingOver && (
                        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-muted-foreground/25 p-6 text-center">
                          <div className="mb-2 rounded-full bg-muted p-2">
                            <Filter className="h-4 w-4 text-muted-foreground" />
                          </div>
                          <p className="text-sm font-medium text-muted-foreground">
                            {myLeadsOnly ? 'Nenhum lead seu nesta etapa' : 'Nenhum lead nesta etapa'}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground/70">
                            {myLeadsOnly ? 'Desative o filtro ou atribua leads a você' : 'Arraste leads de outras colunas'}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </Droppable>
              </div>
            </div>
          ))}
          </div>
        </div>
      </DragDropContext>

      {/* Feedback de score: remonta por lead para o formulário começar zerado. */}
      <ScoreFeedbackDialog
        key={feedbackLead?.id ?? 'none'}
        lead={feedbackLead}
        open={feedbackOpen}
        onOpenChange={(open) => {
          setFeedbackOpen(open);
          if (!open) setFeedbackLead(null);
        }}
      />
    </div>
  );
}
