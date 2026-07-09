'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { GripVertical, Clock, AlertTriangle } from 'lucide-react';
import { Lead } from '@/types';

interface KanbanColumn {
  id: string;
  title: string;
  leads: Lead[];
}

const kanbanColumns: KanbanColumn[] = [
  {
    id: 'CONTATADO',
    title: 'Contatado',
    leads: [
      {
        id: '1',
        company_name: 'Tijuca Restaurante & Bar',
        category: 'Restaurante',
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
    title: 'Respondido',
    leads: [
      {
        id: '2',
        company_name: 'Clínica Saúde Integral',
        category: 'Clínica',
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
    title: 'Reunião Marcada',
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
    title: 'Reunião Feita',
    leads: [],
  },
  {
    id: 'PROPOSTA_ENVIADA',
    title: 'Proposta Enviada',
    leads: [],
  },
];

export function KanbanBoard() {
  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {kanbanColumns.map((column) => (
        <div key={column.id} className="min-w-[300px] flex-1">
          <div className="rounded-lg bg-muted p-3">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-medium">{column.title}</h3>
              <Badge variant="secondary">{column.leads.length}</Badge>
            </div>
            <div className="space-y-3">
              {column.leads.map((lead) => (
                <Card key={lead.id} className="cursor-grab active:cursor-grabbing">
                  <CardContent className="p-4">
                    <div className="mb-2 flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <GripVertical className="h-4 w-4 text-muted-foreground" />
                        <h4 className="font-medium">{lead.company_name}</h4>
                      </div>
                      <Badge className="bg-green-100 text-green-800">
                        {lead.qualification_score}
                      </Badge>
                    </div>
                    <p className="mb-2 text-sm text-muted-foreground">
                      {lead.category} • {lead.city}, {lead.state}
                    </p>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        <span>5 dias</span>
                      </div>
                      {lead.status === 'CONTATADO' && (
                        <div className="flex items-center gap-1 text-yellow-600">
                          <AlertTriangle className="h-3 w-3" />
                          <span>Follow-up</span>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
              {column.leads.length === 0 && (
                <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
                  Nenhum lead nesta etapa
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}