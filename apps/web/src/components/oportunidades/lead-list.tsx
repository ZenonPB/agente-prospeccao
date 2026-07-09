'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Search } from 'lucide-react';
import Link from 'next/link';
import { useLeads, useCampaigns } from '@/hooks/use-api';

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
  NONE: 'Sem problemas',
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

export function LeadList() {
  const [search, setSearch] = useState('');
  const [campaignFilter, setCampaignFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('score_desc');

  const { data: campaignsData } = useCampaigns();
  const campaigns = campaignsData?.campaigns || [];

  const { data, isLoading } = useLeads({
    search: search || undefined,
    campaign_id: campaignFilter !== 'all' ? campaignFilter : undefined,
  });

  const leads = data?.leads || [];

  // Ordena leads
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
      {/* Filters */}
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
            <SelectValue placeholder="Busca" />
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

      {/* Lead Cards */}
      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">Carregando leads...</div>
      ) : sortedLeads.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">Nenhum lead encontrado</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sortedLeads.map((lead) => (
            <Link key={lead.id} href={`/oportunidades/${lead.id}`}>
              <Card className="transition-all hover:shadow-md hover:border-primary">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg">{lead.company_name}</CardTitle>
                      <p className="text-sm text-muted-foreground">{lead.category || 'Sem categoria'}</p>
                    </div>
                    <Badge className={getScoreColor(lead.qualification_score)}>
                      {lead.qualification_score}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Necessidade:</span>
                      <Badge variant="outline" className="text-xs">
                        {primaryNeedLabels[lead.primary_need || 'NONE']}
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