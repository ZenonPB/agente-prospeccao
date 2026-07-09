'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { GripVertical, Clock, AlertTriangle } from 'lucide-react';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';
import { Lead } from '@/types';

interface KanbanColumn {
  id: string;
  title: string;
  color: string;
  leads: Lead[];
}

const initialData: KanbanColumn[] = [
  {
    id: 'CONTATADO',
    title: 'Mensagem enviada',
    color: 'bg-blue-500',
    leads: [
      {
        id: '1',
        company_name: 'Tijuca Restaurante & Bar',
        category: 'Gastronomia',
        city: 'Araraquara',
        state: 'SP',
        country: 'Brasil',
        status: 'CONTATADO',
        qualification_score: 88,
        created_at: '2024-01-15',
        updated_at: '2024-01-20',
      },
    ],
  },
  {
    id: 'RESPONDIDO',
    title: 'Respondeu',
    color: 'bg-purple-500',
    leads: [
      {
        id: '2',
        company_name: 'Clínica Saúde Integral',
        category: 'Saúde',
        city: 'São Paulo',
        state: 'SP',
        country: 'Brasil',
        status: 'RESPONDIDO',
        qualification_score: 65,
        created_at: '2024-01-18',
        updated_at: '2024-01-22',
      },
    ],
  },
  {
    id: 'REUNIAO_MARCADA',
    title: 'Reunião marcada',
    color: 'bg-amber-500',
    leads: [
      {
        id: '3',
        company_name: 'Indústria MetalWorks',
        category: 'Indústria',
        city: 'Guarulhos',
        state: 'SP',
        country: 'Brasil',
        status: 'REUNIAO_MARCADA',
        qualification_score: 72,
        created_at: '2024-01-10',
        updated_at: '2024-01-25',
      },
    ],
  },
  {
    id: 'REUNIAO_FEITA',
    title: 'Reunião realizada',
    color: 'bg-emerald-500',
    leads: [],
  },
  {
    id: 'PROPOSTA_ENVIADA',
    title: 'Proposta enviada',
    color: 'bg-pink-500',
    leads: [],
  },
];

export function KanbanBoard() {
  const [columns, setColumns] = useState<KanbanColumn[]>(initialData);

  const onDragEnd = (result: DropResult) => {
    const { source, destination } = result;

    if (!destination) return;

    if (
      source.droppableId === destination.droppableId &&
      source.index === destination.index
    ) {
      return;
    }

    const newColumns = [...columns];
    const sourceColIdx = newColumns.findIndex((col) => col.id === source.droppableId);
    const destColIdx = newColumns.findIndex((col) => col.id === destination.droppableId);

    const sourceCol = newColumns[sourceColIdx];
    const destCol = newColumns[destColIdx];

    const sourceLeads = [...sourceCol.leads];
    const destLeads = sourceCol.id === destCol.id ? sourceLeads : [...destCol.leads];

    const [movedLead] = sourceLeads.splice(source.index, 1);
    destLeads.splice(destination.index, 0, movedLead);

    newColumns[sourceColIdx] = { ...sourceCol, leads: sourceLeads };
    if (sourceCol.id !== destCol.id) {
      newColumns[destColIdx] = { ...destCol, leads: destLeads };
    }

    setColumns(newColumns);
  };

  const totalLeads = columns.reduce((acc, col) => acc + col.leads.length, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {totalLeads} empresa{totalLeads !== 1 ? 's' : ''} em acompanhamento
        </p>
        <p className="text-sm text-muted-foreground">
          Arraste os cartões entre as colunas para atualizar o status
        </p>
      </div>

      <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-4">
          {columns.map((column) => (
            <div key={column.id} className="min-w-[280px] flex-1">
              <div className="rounded-xl bg-muted/50 p-3">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`h-2 w-2 rounded-full ${column.color}`} />
                    <h3 className="font-medium">{column.title}</h3>
                  </div>
                  <Badge variant="secondary" className="text-xs">
                    {column.leads.length}
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
                      {column.leads.map((lead, index) => (
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
                                {lead.category} • {lead.city}, {lead.state}
                              </p>
                              <div className="flex items-center justify-between text-xs text-muted-foreground">
                                <div className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  <span>5 dias</span>
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
                      {column.leads.length === 0 && !snapshot.isDraggingOver && (
                        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                          Nenhuma empresa nesta etapa
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