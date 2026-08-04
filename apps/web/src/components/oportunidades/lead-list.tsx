'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Search, AlertCircle, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { useLeads, useCampaigns } from '@/hooks/use-api';
import { Skeleton } from '@/components/ui/skeleton';

const scoreColors = {
  high: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-red-100 text-red-700',
};

const getScoreColor = (score: number) => {
  if (score >= 80) return scoreColors.high;
  if (score >= 60) return scoreColors.medium;
  return scoreColors.low;
};

const primaryNeedLabels: Record<string, string> = {
  SECURITY_FIX: 'Problemas de segurança',
  MODERN_WEBSITE: 'Site desatualizado',
  PERFORMANCE: 'Site lento',
  SEO: 'Problemas de visibilidade',
  LGPD: 'Adequação LGPD',
  NONE: 'Sem necessidade',
};

const formatPrimaryNeed = (value?: string) => {
  if (!value) return 'Sem necessidade';
  return primaryNeedLabels[value] || value;
};

const priorityBadgeConfig: Record<string, { label: string; color: string; emoji: string }> = {
  HOT: { label: 'Quente', color: 'bg-red-100 text-red-700', emoji: '🔥' },
  WARM: { label: 'Morno', color: 'bg-amber-100 text-amber-700', emoji: '🌤️' },
  COLD: { label: 'Frio', color: 'bg-sky-100 text-sky-700', emoji: '❄️' },
};

const statusLabels: Record<string, string> = {
  NOVO: 'Novo',
  ANALISADO: 'Analisado',
  QUALIFICADO: 'Apto',
  DESQUALIFICADO: 'Desqualificado',
  CONTATADO: 'Contatado',
  RESPONDIDO: 'Respondeu',
  REUNIAO_MARCADA: 'Reunião',
  PERDIDO: 'Perdido',
};

function LeadCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <Skeleton className="h-5 w-36" />
            <Skeleton className="h-4 w-24" />
          </div>
          <Skeleton className="h-5 w-10 rounded-full" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-5 w-28 rounded-full" />
          </div>
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-12" />
            <Skeleton className="h-4 w-24" />
          </div>
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-12" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function LeadList() {
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [campaignFilter, setCampaignFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('score_desc');

  // Debounce (300ms) para não disparar uma query por tecla digitada (item 4.9).
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const { data: campaignsData, isLoading: campaignsLoading } = useCampaigns();
  const campaigns = campaignsData?.campaigns || [];

  const { data, isLoading, isError, error, refetch } = useLeads({
    search: debouncedSearch || undefined,
    campaign_id: campaignFilter !== 'all' ? campaignFilter : undefined,
  });

  const leads = data?.leads || [];

  const sortedLeads = [...leads].sort((a, b) => {
    switch (sortBy) {
      case 'score_desc':
        return b.qualification_score - a.qualification_score;
      case 'score_asc':
        return a.qualification_score - b.qualification_score;
      case 'date_desc':
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      case 'date_asc':
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      default:
        return 0;
    }
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 sm:w-64">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar lead..."
            className="pl-9 h-10"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={campaignFilter} onValueChange={(v) => setCampaignFilter(v || 'all')}>
          <SelectTrigger className="w-full sm:w-[180px] h-10">
            <SelectValue placeholder={campaignsLoading ? 'Carregando...' : 'Busca'} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas as buscas</SelectItem>
            {campaigns.map((c) => (
              <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={sortBy} onValueChange={(v) => setSortBy(v || 'score_desc')}>
          <SelectTrigger className="w-full sm:w-[180px] h-10">
            <SelectValue placeholder="Ordenar por" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="score_desc">Maior aptidão primeiro</SelectItem>
            <SelectItem value="score_asc">Menor aptidão primeiro</SelectItem>
            <SelectItem value="date_desc">Mais recente</SelectItem>
            <SelectItem value="date_asc">Mais antigo</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <LeadCardSkeleton key={i} />
          ))}
        </div>
      ) : isError ? (
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
      ) : sortedLeads.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">Nenhum lead encontrado</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sortedLeads.map((lead) => (
            <Link key={lead.id} href={`/oportunidades/${lead.id}`}>
              <Card className="transition-all hover:shadow-md hover:border-primary">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 pr-2">
                      <CardTitle className="text-lg">{lead.company_name}</CardTitle>
                      <p className="text-sm text-muted-foreground">{lead.category || 'Sem categoria'}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {lead.priority && priorityBadgeConfig[lead.priority] && (
                        <Badge className={`${priorityBadgeConfig[lead.priority].color} text-xs`}>
                          <span className="mr-1">{priorityBadgeConfig[lead.priority].emoji}</span>
                          {priorityBadgeConfig[lead.priority].label}
                        </Badge>
                      )}
                      <Badge className={getScoreColor(lead.qualification_score)}>
                        {lead.qualification_score}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Necessidade:</span>
                      <Badge variant="outline" className="text-xs">
                        {formatPrimaryNeed(lead.primary_need)}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Local:</span>
                      <span>{lead.city || 'Não informado'}{lead.state ? `, ${lead.state}` : ''}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Status:</span>
                      <Badge variant={lead.status === 'QUALIFICADO' ? 'default' : 'secondary'}>
                        {statusLabels[lead.status] || lead.status}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
