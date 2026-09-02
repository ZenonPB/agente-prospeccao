'use client';

import { useMemo, useCallback, useState, memo } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { GripVertical, Clock, AlertTriangle, AlertCircle, RefreshCw, UserPlus, User, Check, MoreHorizontal, MessageCircle, ArrowRight, Filter, Users, BrainCircuit } from 'lucide-react';
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
  { id: 'REUNIAO_MARCADA', title: 'ReuniÃ£o Agendada', color: 'bg-amber-500', status: ['REUNIAO_MARCADA'] },
  { id: 'REUNIAO_FEITA', title: 'ReuniÃ£o Realizada', color: 'bg-teal-500', status: ['REUNIAO_FEITA'] },
  { id: 'PROPOSTA_ENVIADA', title: 'Proposta Enviada', color: 'bg-pink-500', status: ['PROPOSTA_ENVIADA'] },
];

const NEG_STAGE_LABELS: Record<string, string> = {
  RD: 'DemonstraÃ§Ã£o',
  ORCAMENTO: 'OrÃ§amento',
  RP: 'Proposta',
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type LeadData = Record<string, any>;

// Subconjunto do LeadData usado pelo card memoizado. MantÃ©m a tipagem
// permissiva (Record<string, any>) alinhada com o resto do arquivo.
type LeadbanCard = LeadData;

interface KanbanCardProps {
  // O `lead` vem de `useAllLeads`; tem `id` garantido pelo endpoint
  // (lead.id é NOT NULL no schema). Tipamos como `LeadData` com id
  // opcional para alinhar com o resto do arquivo sem acoplamento.
  lead: LeadbanCard;
  index: number;
  column: KanbanColumn;
  slaAlert: SlaAlertItem | undefined;
  activeDragFrom: string | null;
  now: number;
  currentUserId: string | null;
  // Membros da org para o menu "Atribuir a". O endpoint devolve
  // `assigned_to` como string; mantemos o union.
  members: { user_id: string; name?: string; email?: string }[] | undefined;
  canAssignOthers: boolean;
  // Recebemos só o `mutate` do useMutation para manter a superfície
  // pequena — `KanbanCard` não usa isPending, etc.
  recordWhatsApp: { mutate: (vars: { leadId: string }) => void };
  onAssignToMe: (leadId: string) => void;
  onAssignTo: (leadId: string, userId: string | null, name?: string) => void;
  onMoveTo: (leadId: string, status: string) => void;
  onOpenFeedback: (lead: LeadbanCard) => void;
  onOpenLead: (leadId: string) => void;
}

// Subcomponente memoizado: cada card sÃ³ re-renderiza quando suas props
// mudam de fato. Sem memo, o re-render do pai (causado por onDragStart/
// onDragEnd/optimistic update) re-renderizava TODOS os 30+ cards a cada
// drag, mesmo os que nÃ£o estavam sendo arrastados.
const KanbanCard = memo(function KanbanCard({
  lead,
  index,
  column,
  slaAlert,
  activeDragFrom,
  now,
  currentUserId,
  members,
  canAssignOthers,
  recordWhatsApp,
  onAssignToMe,
  onAssignTo,
  onMoveTo,
  onOpenFeedback,
  onOpenLead,
}: KanbanCardProps) {
  const daysSinceCreated = useMemo(() => {
    const created = new Date(lead.created_at).getTime();
    if (!Number.isFinite(created)) return 0;
    return Math.floor((now - created) / (1000 * 60 * 60 * 24));
  }, [lead.created_at, now]);
  // `now` vem de ref, Ã© estÃ¡vel â€” sÃ³ recalcula se o `created_at` mudar.

  return (
    // O endpoint garante `lead.id`; usamos fallback '' em vez de `!` para
    // satisfazer o strict do TS sem perder a checagem de runtime (a key
    // do pai já filtra cards sem id).
    <Draggable draggableId={lead.id ?? ''} index={index}>
      {(provided, snapshot) => {
        // Combina o `style` que o @hello-pangea/dnd injeta com
        // `transform: translate3d(...)` (move o card durante o drag) com
        // estilos nossos. SEM isto, o card ficava parado mesmo com o
        // mouse arrastando â€” a "travada" e o "card nÃ£o segue o mouse"
        // vinham daqui.
        const draggableStyle: React.CSSProperties = provided.draggableProps.style ?? {};
        const compositeStyle: React.CSSProperties = {
          ...draggableStyle,
          // will-change durante o arraste ativa a composiÃ§Ã£o em GPU e
          // evita o jank causado por repaints da main thread.
          willChange: snapshot.isDragging ? 'transform' : undefined,
          // Nenhuma transition no estado "dragging": a lib atualiza o
          // `transform` em cada pointermove; qualquer transition cria
          // lag entre o cursor e o card.
          transition: snapshot.isDragging ? 'none' : undefined,
        };

        return (
          <div
            ref={provided.innerRef}
            {...provided.draggableProps}
            style={compositeStyle}
            className={`group rounded-lg border bg-card p-3.5 shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
              snapshot.isDragging
                ? 'rotate-[1.5deg] scale-[1.03] shadow-xl ring-2 ring-primary/40'
                : `transition-[border-color,box-shadow] duration-100 ${
                    activeDragFrom
                      ? 'opacity-40 saturate-50'
                      : 'hover:border-primary/20 hover:shadow-md'
                  }`
            }`}
          >
            {/* CabeÃ§alho do cartÃ£o = alÃ§a de arraste. */}
            <div
              {...provided.dragHandleProps}
              className="-mx-1 mb-2 flex cursor-grab touch-none select-none items-start justify-between gap-2 rounded-lg px-1 py-1 transition-colors hover:bg-muted/60 active:cursor-grabbing"
              title="Segure e arraste para mudar de etapa"
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation();
                onOpenLead(lead.id);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onOpenLead(lead.id);
                }
              }}
            >
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-1.5">
                  <GripVertical className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" aria-hidden="true" />
                  <h3 className="truncate text-sm font-semibold text-foreground">
                    {lead.company_name}
                  </h3>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                  {lead.priority && (
                    <Badge
                      variant={
                        lead.priority === 'HOT'
                          ? 'destructive'
                          : lead.priority === 'WARM'
                            ? 'default'
                            : 'secondary'
                      }
                      className="h-4 px-1.5 py-0 text-[10px] font-medium"
                    >
                      {lead.priority === 'HOT' ? 'Quente' : lead.priority === 'WARM' ? 'Morno' : 'Frio'}
                    </Badge>
                  )}
                  {typeof lead.qualification_score === 'number' && (
                    <span className="font-medium text-foreground/80">
                      {lead.qualification_score.toFixed(0)} pts
                    </span>
                  )}
                  {lead.negotiation_stage && (
                    <span className="rounded border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                      {NEG_STAGE_LABELS[lead.negotiation_stage] || lead.negotiation_stage}
                    </span>
                  )}
                  <span className="flex items-center gap-0.5">
                    <Clock className="h-3 w-3" aria-hidden="true" />
                    {daysSinceCreated}d
                  </span>
                  {slaAlert && (
                    <span className="rounded border border-red-300 bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-700">
                      SLA
                    </span>
                  )}
                </div>
              </div>
            </div>
            {/* BotÃµes de aÃ§Ã£o rÃ¡pida. Stop propagation para nÃ£o abrir o lead. */}
            <div className="flex flex-wrap items-center justify-end gap-1.5">
              {lead.contact_phone && (
                <Button
                  variant="outline"
                  size="icon"
                  className="h-11 w-11 shrink-0 sm:h-8 sm:w-8"
                  onClick={(e) => {
                    e.stopPropagation();
                    const url = whatsAppLink(lead.contact_phone);
                    if (url) window.open(url, '_blank', 'noopener');
                    recordWhatsApp.mutate({ leadId: lead.id ?? '' });
                  }}
                  aria-label={`Enviar WhatsApp para ${lead.company_name}`}
                  title="Abrir WhatsApp"
                >
                  <MessageCircle className="h-3.5 w-3.5" />
                </Button>
              )}
              {!lead.assigned_to && currentUserId && (
                <Button
                  variant="outline"
                  size="icon"
                  className="h-11 w-11 shrink-0 sm:h-8 sm:w-8"
                  onClick={(e) => {
                    e.stopPropagation();
                    onAssignToMe(lead.id);
                  }}
                  aria-label={`Atribuir ${lead.company_name} a mim`}
                  title="Atribuir a mim"
                >
                  <UserPlus className="h-3.5 w-3.5" />
                </Button>
              )}
              {lead.assigned_to && (
                <Badge
                  variant="outline"
                  className="h-6 gap-1 border-blue-200 bg-blue-50 px-2 text-[10px] font-medium text-blue-700"
                  title={lead.assigned_to_name || lead.assigned_to}
                >
                  <User className="h-3 w-3" />
                  {lead.assigned_to_name || 'AtribuÃ­do'}
                </Badge>
              )}
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-11 w-11 shrink-0 sm:h-8 sm:w-8"
                      onClick={(e: { stopPropagation: () => void }) => e.stopPropagation()}
                      aria-label={`Mais aÃ§Ãµes para ${lead.company_name}`}
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </Button>
                  }
                />
                <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
                  <DropdownMenuGroup>
                    {canAssignOthers && currentUserId && (
                      <DropdownMenuGroup>
                        <DropdownMenuLabel>Atribuir a</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            onAssignToMe(lead.id);
                          }}
                        >
                          <UserPlus className="mr-2 h-3.5 w-3.5" />
                          VocÃª
                        </DropdownMenuItem>
                        {members?.filter((m) => m.user_id !== currentUserId).map((m) => (
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
                    )}
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenFeedback(lead);
                      }}
                    >
                      <BrainCircuit className="mr-2 h-3.5 w-3.5" />
                      Discordar do score
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
              {/* Fallback acessÃ­vel por toque: mover de etapa sem arrastar. */}
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
                          onMoveTo(lead.id, c.id);
                        }}
                      >
                        {c.title}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        );
      }}
    </Draggable>
  );
}, (prev, next) => {
  // ComparaÃ§Ã£o custom para memo: evita re-render quando o objeto `lead`
  // mudou de referÃªncia (ex.: novo fetch) mas o conteÃºdo Ã© o mesmo.
  if (prev.lead !== next.lead) return false;
  if (prev.index !== next.index) return false;
  if (prev.column.id !== next.column.id) return false;
  if (prev.slaAlert !== next.slaAlert) return false;
  if (prev.activeDragFrom !== next.activeDragFrom) return false;
  if (prev.now !== next.now) return false;
  if (prev.currentUserId !== next.currentUserId) return false;
  if (prev.members !== next.members) return false;
  if (prev.canAssignOthers !== next.canAssignOthers) return false;
  // Callbacks vÃªm do useCallback no pai â€” se as refs forem estÃ¡veis,
  // nunca mudam. Se mudar, re-renderiza (seguranÃ§a).
  if (prev.recordWhatsApp !== next.recordWhatsApp) return false;
  if (prev.onAssignToMe !== next.onAssignToMe) return false;
  if (prev.onAssignTo !== next.onAssignTo) return false;
  if (prev.onMoveTo !== next.onMoveTo) return false;
  if (prev.onOpenFeedback !== next.onOpenFeedback) return false;
  if (prev.onOpenLead !== next.onOpenLead) return false;
  return true;
});

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
  // Feedback de score: qual lead estÃ¡ sendo corrigido e se o diÃ¡logo estÃ¡ aberto.
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
  // o card "volta" para a posiÃ§Ã£o antiga ao soltar (e sÃ³ reposiciona quando o
  // refetch termina) â€” parece que o drag nÃ£o funciona. Aqui movemos o card
  // imediatamente e desfazemos em caso de erro.
  const [draftColumns, setDraftColumns] = useState<Record<string, LeadData[]> | null>(null);
  const visibleColumns = draftColumns ?? columns;

  // Coluna de origem do arraste em curso: usada para realÃ§ar os alvos de
  // drop e esmaecer os cartÃµes que nÃ£o estÃ£o sendo arrastados.
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

  // Congela `Date.now()` em uma ref para o cÃ¡lculo de "dias desde criaÃ§Ã£o".
  // Sem isso, cada re-render do kanban (incluindo os disparados pelo drag)
  // recalculava `Date.now()` no JSX, gerando novas referÃªncias e quebrando
  // qualquer `React.memo` aplicado ao card.
  const [now] = useState(() => Date.now());

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
              ? `PrÃ³xima aÃ§Ã£o sugerida: ${new Date(res.suggested_next_action_at).toLocaleDateString('pt-BR')}`
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
          toast.success('Lead atribuÃ­do a vocÃª.');
        },
        onError: () => {
          toast.error('NÃ£o foi possÃ­vel atribuir o lead.');
        },
      }
    );
  }, [currentUserId, assignLead]);

  const onAssignTo = useCallback((leadId: string, userId: string | null, name?: string) => {
    assignLead.mutate(
      { id: leadId, assignedToId: userId },
      {
        onSuccess: () => {
          toast.success(userId ? `Lead atribuÃ­do a ${name || 'consultor'}.` : 'Lead desatribuÃ­do.');
        },
        onError: () => {
          toast.error('NÃ£o foi possÃ­vel atribuir o lead.');
        },
      }
    );
  }, [assignLead]);

  // Mover de etapa pelo dropdown (fallback acessÃ­vel por toque).
  // Centralizado aqui para que o KanbanCard memoizado receba um callback
  // estÃ¡vel (useCallback) em vez de um inline criado a cada render.
  const onMoveTo = useCallback((leadId: string, status: string) => {
    updateStatus.mutate(
      { id: leadId, status },
      {
        onSuccess: (res) => {
          const colTitle = COLUMNS.find((c) => c.id === status)?.title || status;
          toast.success(`Lead movido para ${colTitle}`, {
            description: res.suggested_next_action_at
              ? `PrÃ³xima aÃ§Ã£o sugerida: ${new Date(res.suggested_next_action_at).toLocaleDateString('pt-BR')}`
              : undefined,
          });
        },
        onError: () => toast.error('Erro ao mover lead'),
      }
    );
  }, [updateStatus]);

  // Abrir lead (navega para a pÃ¡gina de detalhes). EstÃ¡vel para o memo.
  const onOpenLead = useCallback((leadId: string) => {
    router.push(`/oportunidades/${leadId}`);
  }, [router]);

  // Abrir diÃ¡logo de feedback de score. EstÃ¡vel para o memo.
  const onOpenFeedback = useCallback((lead: LeadData) => {
    setFeedbackLead(lead);
    setFeedbackOpen(true);
  }, []);

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
      {/* Resumo do Funil de NegociaÃ§Ã£o */}
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
          <p className="text-xs font-medium text-muted-foreground">ReuniÃµes / Propostas</p>
          <p className="font-heading text-xl font-bold tracking-tight text-amber-600">
            {(visibleColumns['REUNIAO_MARCADA']?.length || 0) + (visibleColumns['REUNIAO_FEITA']?.length || 0) + (visibleColumns['PROPOSTA_ENVIADA']?.length || 0)}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <p className="hidden text-sm font-medium text-muted-foreground sm:block">
            Segure o topo de um cartÃ£o e arraste entre as colunas para atualizar a etapa
          </p>
          <p className="text-sm font-medium text-muted-foreground sm:hidden">
            Toque no cartÃ£o para abrir o lead Â· segure o topo para arrastar de etapa
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
                      className={`min-h-[120px] space-y-2.5 rounded-lg border-2 border-dashed p-2 transition-colors duration-100 ${
                        snapshot.isDraggingOver
                          ? 'border-primary/60 bg-primary/5'
                          : activeDragFrom
                            ? 'border-border/70 bg-muted/30'
                            : 'border-transparent bg-transparent'
                      }`}
                    >
                      {(visibleColumns[column.id] || []).map((lead, index) => (
                        <KanbanCard
                          key={lead.id}
                          lead={lead}
                          index={index}
                          column={column}
                          slaAlert={slaByLead[lead.id]}
                          activeDragFrom={activeDragFrom}
                          now={now}
                          currentUserId={currentUserId ?? null}
                          members={membersData?.members}
                          canAssignOthers={canAssignOthers}
                          recordWhatsApp={recordWhatsApp}
                          onAssignToMe={onAssignToMe}
                          onAssignTo={onAssignTo}
                          onMoveTo={onMoveTo}
                          onOpenFeedback={onOpenFeedback}
                          onOpenLead={onOpenLead}
                        />
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
                            {myLeadsOnly ? 'Desative o filtro ou atribua leads a vocÃª' : 'Arraste leads de outras colunas'}
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

      {/* Feedback de score: remonta por lead para o formulÃ¡rio comeÃ§ar zerado. */}
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
