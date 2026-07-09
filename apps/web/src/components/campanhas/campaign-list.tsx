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
import { useCampaigns } from '@/hooks/use-api';

const statusConfig = {
  ACTIVE: { label: 'Em andamento', color: 'bg-emerald-100 text-emerald-700' },
  PAUSED: { label: 'Pausada', color: 'bg-amber-100 text-amber-700' },
  COMPLETED: { label: 'Concluída', color: 'bg-blue-100 text-blue-700' },
  ARCHIVED: { label: 'Arquivada', color: 'bg-gray-100 text-gray-700' },
};

export function CampaignList() {
  const { data, isLoading } = useCampaigns();
  const campaigns = data?.campaigns || [];

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

      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">Carregando campanhas...</div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">Nenhuma campanha encontrada</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {campaigns.map((campaign) => (
            <Card key={campaign.id} className="relative overflow-hidden transition-all hover:shadow-md">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-lg">{campaign.name}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {campaign.target_service || campaign.target_segment || 'Geral'} • {campaign.target_city || 'Todas as cidades'}{campaign.target_state ? `, ${campaign.target_state}` : ''}
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
                      {campaign.lead_count || 0} leads encontrados
                    </span>
                  </div>
                  <Progress 
                    value={campaign.lead_count ? Math.min((campaign.lead_count / 100) * 100, 100) : 0} 
                    className="h-2"
                  />
                  <div className="flex items-center justify-between">
                    <Badge className={statusConfig[campaign.status as keyof typeof statusConfig]?.color || 'bg-gray-100 text-gray-700'}>
                      {statusConfig[campaign.status as keyof typeof statusConfig]?.label || campaign.status}
                    </Badge>
                    {campaign.avg_score ? (
                      <span className="text-sm font-medium">
                        Aptidão: {campaign.avg_score}
                      </span>
                    ) : null}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}