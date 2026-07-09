'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Plus, MoreHorizontal, Pause, Play, Archive } from 'lucide-react';
import Link from 'next/link';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface Campaign {
  id: string;
  name: string;
  segment: string;
  city: string;
  state: string;
  lead_count: number;
  target_leads: number;
  avg_score: number;
  status: 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'ARCHIVED';
  created_at: string;
}

const campaigns: Campaign[] = [
  {
    id: '1',
    name: 'Restaurantes Araraquara',
    segment: 'Restaurantes',
    city: 'Araraquara',
    state: 'SP',
    lead_count: 45,
    target_leads: 100,
    avg_score: 72,
    status: 'ACTIVE',
    created_at: '2024-01-15',
  },
  {
    id: '2',
    name: 'Clínicas São Paulo',
    segment: 'Clínicas',
    city: 'São Paulo',
    state: 'SP',
    lead_count: 23,
    target_leads: 50,
    avg_score: 68,
    status: 'ACTIVE',
    created_at: '2024-01-20',
  },
  {
    id: '3',
    name: 'Academias Campinas',
    segment: 'Academias',
    city: 'Campinas',
    state: 'SP',
    lead_count: 30,
    target_leads: 30,
    avg_score: 75,
    status: 'COMPLETED',
    created_at: '2024-01-10',
  },
  {
    id: '4',
    name: 'Indústrias Guarulhos',
    segment: 'Indústrias',
    city: 'Guarulhos',
    state: 'SP',
    lead_count: 12,
    target_leads: 40,
    avg_score: 0,
    status: 'PAUSED',
    created_at: '2024-02-01',
  },
];

const statusConfig = {
  ACTIVE: { label: 'Ativa', color: 'bg-green-100 text-green-800' },
  PAUSED: { label: 'Pausada', color: 'bg-yellow-100 text-yellow-800' },
  COMPLETED: { label: 'Concluída', color: 'bg-blue-100 text-blue-800' },
  ARCHIVED: { label: 'Arquivada', color: 'bg-gray-100 text-gray-800' },
};

export function CampaignList() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Todas as Campanhas</h3>
        <Link href="/campanhas/nova">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Nova Campanha
          </Button>
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {campaigns.map((campaign) => (
          <Card key={campaign.id} className="relative overflow-hidden">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-lg">{campaign.name}</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {campaign.segment} • {campaign.city}, {campaign.state}
                  </p>
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="h-8 w-8" />}>
                    <MoreHorizontal className="h-4 w-4" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem>
                      {campaign.status === 'ACTIVE' ? (
                        <>
                          <Pause className="mr-2 h-4 w-4" />
                          Pausar
                        </>
                      ) : (
                        <>
                          <Play className="mr-2 h-4 w-4" />
                          Reativar
                        </>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem>Duplicar</DropdownMenuItem>
                    <DropdownMenuItem>Iniciar nova coleta</DropdownMenuItem>
                    <DropdownMenuItem>
                      <Archive className="mr-2 h-4 w-4" />
                      Arquivar
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Progresso</span>
                  <span className="font-medium">
                    {campaign.lead_count}/{campaign.target_leads} leads
                  </span>
                </div>
                <Progress 
                  value={(campaign.lead_count / campaign.target_leads) * 100} 
                  className="h-2"
                />
                <div className="flex items-center justify-between">
                  <Badge className={statusConfig[campaign.status].color}>
                    {statusConfig[campaign.status].label}
                  </Badge>
                  {campaign.avg_score > 0 && (
                    <span className="text-sm font-medium">
                      Score: {campaign.avg_score}
                    </span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}