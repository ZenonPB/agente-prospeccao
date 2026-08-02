'use client';

import { useMemo, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { GripVertical, Clock, AlertTriangle, AlertCircle, RefreshCw, Loader2, UserPlus, User, Check } from 'lucide-react';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';
import { useLeads, useUpdateLeadStatus, useAssignLead } from '@/hooks/use-api';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';

interface KanbanColumn {
  id: string;
  title: string;
  color: string;
  status: string[];
}

const COLUMNS: KanbanColumn[] = [
  { id: 'CONTATADO', title: 'Mensagem enviada', color: 'bg-blue-500', status: ['CONTATADO'] },
  { id: 'RESPONDIDO', title: 'Respondeu', color: 'bg-purple-500', status: ['RESPONDIDO'] },
  { id: 'REUNIAO_MARCADA', title: 'Reunião marcada', color: 'bg-amber-500', status: ['REUNIAO_MARCADA'] },
  { id: 'REUNIAO_FEITA', title: 'Reunião realizada', color: 'bg-emerald-500', status: ['REUNIAO_FEITA'] },
  { id: 'PROPOSTA_ENVIADA', title: 'Proposta enviada', color: 'bg-pink-500', status: ['PROPOSTA_ENVIADA'] },
];

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

  return grouped;
}

function KanbanColumnSkeleton() {
  return (
    <div className="min-w-[280px] flex-1">
      <div className="rounded-xl bg-muted/50 p-3">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Skeleton className="h-2 w-2 rounded-full" />
            <Skeleton className="h-4 w-28" />
          </div>
          <Skeleton className="h-5 w-6 rounded-full" />
        </div>
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <Card key={i}>
              <CardContent className="p-4">
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

const SALES_STATUSES = 'CONTATADO,RESPONDIDO,REUNIAO_MARCADA,REUNIAO_FEITA,PROPOSTA_ENVIADA';

export function KanbanBoard() {
  const { data: session } = useSession();
  const currentUserId = (session?.user as { id?: string } | undefined)?.id;
  const updateStatus = useUpdateLeadStatus();
  const assignLead = useAssignLead();
  const { data, isLoading, isError, error, refetch } = useLeads({
    status: SALES_STATUSES,
  });

  const columns = useMemo(
    () => groupLeadsByColumn(data?.leads || []),
    [data?.leads]
  );

  const onDragEnd = useCallback((result: DropResult) => {
    const { draggableId, destination } = result;
    if (!destination) return;

    const newStatus = destination.droppableId;
    updateStatus.mutate(
      { id: draggableId, status: newStatus },
      {
        onSuccess: () => {
          toast.success('Lead movido para ' + destination.droppableId);
        },
        onError: () => {
          toast.error('Erro ao mover lead');
        },
      }
    );
  }, [updateStatus]);

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

  const totalLeads = Object.values(columns).reduce((acc, col) => acc + col.length, 0);

  if (isLoading) {
    return (
      <div className="flex gap-4 overflow-x-auto pb-4">
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
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {totalLeads} lead{totalLeads !== 1 ? 's' : ''} em acompanhamento
        </p>
        <p className="text-sm text-muted-foreground">
          Arraste os cartões entre as colunas para atualizar o status
        </p>
      </div>

      <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-4">
          {COLUMNS.map((column) => (
            <div key={column.id} className="min-w-[280px] flex-1">
              <div className="rounded-xl bg-muted/50 p-3">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`h-2 w-2 rounded-full ${column.color}`} />
                    <h3 className="font-medium">{column.title}</h3>
                  </div>
                  <Badge variant="secondary" className="text-xs">
                    {columns[column.id]?.length || 0}
                  </Badge>
                </div>

                <Droppable droppableId={column.id}>
                  {(provided, snapshot) => (
                    <div
                      ref={provided.innerRef}
                      {...provided.droppableProps}
                      className={`min-h-[200px] space-y-3 rounded-lg transition-colors ${
                        snapshot.isDraggingOver ? 'bg-primary/10' : ''
                      }`}
                    >
                      {(columns[column.id] || []).map((lead, index) => (
                        <Draggable key={lead.id} draggableId={lead.id} index={index}>
                          {(provided, snapshot) => (
                            <div
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              {...provided.dragHandleProps}
                              className={`rounded-lg border bg-card p-4 shadow-sm transition-shadow ${
                                snapshot.isDragging ? 'shadow-lg' : 'hover:shadow-md'
                              }`}
                            >
                              <div className="mb-2 flex items-start justify-between">
                                <div className="flex items-center gap-2">
                                  <GripVertical className="h-4 w-4 text-muted-foreground" />
                                  <h4 className="font-medium">{lead.company_name}</h4>
                                </div>
                                <Badge className="bg-emerald-100 text-emerald-700">
                                  {lead.qualification_score}
                                </Badge>
                              </div>
                              <p className="mb-3 text-sm text-muted-foreground">
                                {lead.category || 'Sem categoria'} • {lead.city || 'Não informado'}{lead.state ? `, ${lead.state}` : ''}
                              </p>
                              <div className="mb-2 flex items-center gap-2 text-xs">
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
                              <div className="flex items-center justify-between text-xs text-muted-foreground">
                                <div className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  <span>{Math.floor((Date.now() - new Date(lead.created_at).getTime()) / (1000 * 60 * 60 * 24))} dias</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  {column.id === 'CONTATADO' && (
                                    <div className="flex items-center gap-1 text-amber-600">
                                      <AlertTriangle className="h-3 w-3" />
                                      <span>Pendente</span>
                                    </div>
                                  )}
                                  {!lead.assigned_to_id && (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="h-6 gap-1 px-2 text-[11px]"
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
                                </div>
                              </div>
                            </div>
                          )}
                        </Draggable>
                      ))}
                      {provided.placeholder}
                      {(columns[column.id] || []).length === 0 && !snapshot.isDraggingOver && (
                        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                          Nenhum lead nesta etapa
                        </div>
                      )}
                    </div>
                  )}
                </Droppable>
              </div>
            </div>
          ))}
        </div>
      </DragDropContext>
    </div>
  );
}
