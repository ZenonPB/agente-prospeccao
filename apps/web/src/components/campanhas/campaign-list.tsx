'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Plus, MoreHorizontal, Pause, Play, Archive, Copy } from 'lucide-react';
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
    name: 'Restaurantes em Araraquara',
    segment: 'Gastronomia',
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
    name: 'Clínicas em São Paulo',
    segment: 'Saúde',
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
    name: 'Academias em Campinas',
    segment: 'Fitness',
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
    name: 'Indústrias em Guarulhos',
    segment: 'Indústria',
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
  ACTIVE: { label: 'Em andamento', color: 'bg-emerald-100 text-emerald-700' },
  PAUSED: { label: 'Pausada', color: 'bg-amber-100 text-amber-700' },
  COMPLETED: { label: 'Concluída', color: 'bg-blue-100 text-blue-700' },
  ARCHIVED: { label: 'Arquivada', color: 'bg-gray-100 text-gray-700' },
};

export function CampaignList() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Todas as Buscas</h3>
        <Link href="/campanhas/nova">
          <Button className="h-10">
            <Plus className="mr-2 h-4 w-4" />
            Nova Busca
          </Button>
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {campaigns.map((campaign) => (
          <Card key={campaign.id} className="relative overflow-hidden transition-all hover:shadow-md">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-lg">{campaign.name}</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {campaign.segment} • {campaign.city}, {campaign.state}
                  </p>
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="h-9 w-9 shrink-0" />}>
                    <MoreHorizontal className="h-4 w-4" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem>
                      {campaign.status === 'ACTIVE' ? (
                        <>
                          <Pause className="mr-2 h-4 w-4" />
                          Pausar busca
                        </>
                      ) : (
                        <>
                          <Play className="mr-2 h-4 w-4" />
                          Retomar busca
                        </>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <Copy className="mr-2 h-4 w-4" />
                      Duplicar para outra cidade
                    </DropdownMenuItem>
                    <DropdownMenuItem>Iniciar nova rodada</DropdownMenuItem>
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
                    {campaign.lead_count} de {campaign.target_leads} empresas
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
                      Aptidão: {campaign.avg_score}
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