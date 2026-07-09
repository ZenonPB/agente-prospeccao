'use client';

import { useMemo, useCallback } from 'react';
import { Badge } from '@/components/ui/badge';
import { GripVertical, Clock, AlertTriangle } from 'lucide-react';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';
import { useLeads } from '@/hooks/use-api';

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

export function KanbanBoard() {
  const { data, isLoading } = useLeads();
  const leads = data?.leads || [];

  const columns = useMemo(() => groupLeadsByColumn(leads), [leads]);

  const onDragEnd = useCallback((_result: DropResult) => {
    // For real-time updates, we'd need to call the API to update lead status
  }, []);

  const totalLeads = Object.values(columns).reduce((acc, col) => acc + col.length, 0);

  if (isLoading) {
    return <div className="text-center py-8 text-muted-foreground">Carregando leads...</div>;
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
                              <div className="flex items-center justify-between text-xs text-muted-foreground">
                                <div className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  <span>{Math.floor((Date.now() - new Date(lead.created_at).getTime()) / (1000 * 60 * 60 * 24))} dias</span>
                                </div>
                                {column.id === 'CONTATADO' && (
                                  <div className="flex items-center gap-1 text-amber-600">
                                    <AlertTriangle className="h-3 w-3" />
                                    <span>Pendente</span>
                                  </div>
                                )}
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
