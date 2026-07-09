'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Plus, MoreHorizontal, Pause, Play, Archive, Copy, PlayCircle, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useCampaigns } from '@/hooks/use-api';
import { Skeleton } from '@/components/ui/skeleton';

const statusConfig = {
  ACTIVE: { label: 'Em andamento', color: 'bg-emerald-100 text-emerald-700' },
  PAUSED: { label: 'Pausada', color: 'bg-amber-100 text-amber-700' },
  COMPLETED: { label: 'Concluída', color: 'bg-blue-100 text-blue-700' },
  ARCHIVED: { label: 'Arquivada', color: 'bg-gray-100 text-gray-700' },
};

function CampaignCardSkeleton() {
  return (
    <Card className="relative overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1 space-y-2">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-56" />
          </div>
          <Skeleton className="h-9 w-9 shrink-0 rounded-md" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-24" />
          </div>
          <Skeleton className="h-2 w-full" />
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-24 rounded-full" />
            <Skeleton className="h-4 w-16" />
          </div>
          <Skeleton className="h-10 w-full rounded-md" />
        </div>
      </CardContent>
    </Card>
  );
}

export function CampaignList() {
  const { data, isLoading, isError, error } = useCampaigns();
  const campaigns = data?.campaigns || [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Todas as Campanhas</h3>
        <Link href="/campanhas/nova">
          <Button className="h-10">
            <Plus className="mr-2 h-4 w-4" />
            Nova Campanha
          </Button>
        </Link>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <CampaignCardSkeleton key={i} />
          ))}
        </div>
      ) : isError ? (
        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-600">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <p className="text-sm font-medium">Erro ao carregar campanhas</p>
            </div>
            <p className="mt-1 text-xs text-red-500">
              {error instanceof Error ? error.message : 'Tente novamente mais tarde'}
            </p>
          </CardContent>
        </Card>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">Nenhuma campanha encontrada</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {campaigns.map((campaign) => (
              <Card key={campaign.id} className="relative overflow-hidden transition-all hover:shadow-md">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <Link href={`/campanhas/${campaign.id}`} className="hover:underline">
                      <CardTitle className="text-lg truncate">{campaign.name}</CardTitle>
                    </Link>
                    <p className="text-sm text-muted-foreground truncate">
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
                  <Link href={`/campanhas/${campaign.id}?start=true`}>
                    <Button size="sm" className="w-full mt-2">
                      <PlayCircle className="mr-2 h-4 w-4" />
                      Iniciar Coleta
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
