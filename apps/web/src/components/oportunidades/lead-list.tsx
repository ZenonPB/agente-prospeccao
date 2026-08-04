'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Search, AlertCircle, RefreshCw, CheckCheck, X, Download, UserPlus, User } from 'lucide-react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import {
  useLeads, useCampaigns, useAssignLead, useUpdateLeadStatus,
  useOrgMembership, useOrgMembers,
} from '@/hooks/use-api';
import type { Lead } from '@/types';
import { Skeleton } from '@/components/ui/skeleton';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';

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
  REUNIAO_FEITA: 'Reunião realizada',
  PROPOSTA_ENVIADA: 'Proposta enviada',
  PERDIDO: 'Perdido',
};

const bulkStatusOptions = [
  { value: 'CONTATADO', label: 'Marcar como contatado' },
  { value: 'RESPONDIDO', label: 'Marcar como respondeu' },
  { value: 'REUNIAO_MARCADA', label: 'Marcar reunião marcada' },
  { value: 'PROPOSTA_ENVIADA', label: 'Marcar proposta enviada' },
  { value: 'PERDIDO', label: 'Marcar como perdido' },
];

function exportSelectedCsv(leads: Lead[], name: string) {
  const headers = [
    'Empresa', 'Website', 'Telefone', 'WhatsApp', 'Email', 'Cidade', 'UF',
    'Status', 'Score', 'Prioridade',
  ];
  const rows = leads.map((lead) => [
    lead.company_name ?? '',
    lead.website ?? '',
    lead.phone ?? '',
    lead.whatsapp ?? '',
    lead.email ?? '',
    lead.city ?? '',
    lead.state ?? '',
    lead.status ?? '',
    lead.qualification_score ?? '',
    lead.priority ?? '',
  ]);
  const csv = [headers.join(';'), ...rows.map((r) => r.join(';'))].join('\n');
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

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
  const { data: session } = useSession();
  const currentUserId = (session?.user as { id?: string } | undefined)?.id;
  const assignLead = useAssignLead();
  const updateStatus = useUpdateLeadStatus();
  const { data: membership } = useOrgMembership();
  const orgId = membership?.organization?.id;
  const myRole = membership?.membership?.role;
  const mySalesRole = membership?.membership?.sales_role;
  const canAssignOthers = myRole === 'OWNER' || myRole === 'ADMIN' || mySalesRole === 'MANAGER';
  const { data: membersData } = useOrgMembers(canAssignOthers ? orgId : undefined);

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [campaignFilter, setCampaignFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('score_desc');
  const [selected, setSelected] = useState<Set<string>>(new Set());

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

  const selectedLeads = sortedLeads.filter((l) => selected.has(l.id));
  const allVisibleSelected = sortedLeads.length > 0 && sortedLeads.every((l) => selected.has(l.id));

  const toggleLead = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleAllVisible = useCallback(() => {
    setSelected((prev) => {
      if (sortedLeads.every((l) => prev.has(l.id))) {
        return new Set([...prev].filter((id) => !sortedLeads.some((l) => l.id === id)));
      }
      const next = new Set(prev);
      sortedLeads.forEach((l) => next.add(l.id));
      return next;
    });
  }, [sortedLeads]);

  const clearSelection = () => setSelected(new Set());

  const runBulk = (action: (id: string) => void) => {
    selectedLeads.forEach((lead) => action(lead.id));
    clearSelection();
  };

  const bulkAssign = (userId: string, name?: string) => {
    runBulk((id) =>
      assignLead.mutate(
        { id, assignedToId: userId },
        {
          onSuccess: () => toast.success(`Atribuído a ${name || 'consultor'}.`),
          onError: () => toast.error('Falha ao atribuir leads.'),
        }
      )
    );
  };

  const bulkStatus = (status: string) => {
    runBulk((id) =>
      updateStatus.mutate(
        { id, status },
        {
          onError: () => toast.error('Falha ao atualizar status.'),
        }
      )
    );
    toast.success(`${selectedLeads.length} lead(s) movido(s) para "${statusLabels[status] || status}".`);
  };

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

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/40 bg-primary/5 p-3">
          <div className="mr-auto flex items-center gap-2">
            <CheckCheck className="h-4 w-4 text-primary" aria-hidden="true" />
            <p className="text-sm font-medium">
              {selected.size} lead{selected.size !== 1 ? 's' : ''} selecionado{selected.size !== 1 ? 's' : ''}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={() => bulkAssign(currentUserId!, 'você')}
            disabled={!currentUserId}
          >
            <UserPlus className="mr-1.5 h-3.5 w-3.5" />
            Atribuir a mim
          </Button>
          {canAssignOthers && (
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="outline" size="sm" className="h-8" />}>
                <User className="mr-1.5 h-3.5 w-3.5" />
                Atribuir para
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
                <DropdownMenuLabel>Atribuir para</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {membersData?.members
                  .filter((m) => m.user_id !== currentUserId)
                  .map((m) => (
                    <DropdownMenuItem key={m.user_id} onClick={() => bulkAssign(m.user_id, m.name || m.email)}>
                      <User className="mr-2 h-3.5 w-3.5" />
                      {m.name || m.email}
                    </DropdownMenuItem>
                  ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <Select onValueChange={(v) => v && bulkStatus(v as string)}>
            <SelectTrigger className="h-8 w-auto">
              <SelectValue placeholder="Mover para..." />
            </SelectTrigger>
            <SelectContent>
              {bulkStatusOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={() => {
              exportSelectedCsv(selectedLeads, 'leads-selecionados.csv');
              clearSelection();
            }}
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            Exportar CSV
          </Button>
          <Button variant="ghost" size="sm" className="h-8" onClick={clearSelection}>
            <X className="mr-1.5 h-3.5 w-3.5" />
            Limpar
          </Button>
        </div>
      )}

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
        <>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <label className="flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                className="h-4 w-4 cursor-pointer accent-primary"
                checked={allVisibleSelected}
                onChange={toggleAllVisible}
                aria-label="Selecionar todos visíveis"
              />
              Selecionar todos visíveis
            </label>
            <span className="ml-auto">{data?.total ?? sortedLeads.length} lead(s)</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {sortedLeads.map((lead) => {
              const isChecked = selected.has(lead.id);
              return (
                <Link key={lead.id} href={`/oportunidades/${lead.id}`}>
                  <Card
                    className={`transition-all hover:shadow-md hover:border-primary ${
                      isChecked ? 'border-primary/60 bg-primary/5' : ''
                    }`}
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="flex min-w-0 items-start gap-2 pr-2">
                          <input
                            type="checkbox"
                            className="mt-1 h-4 w-4 shrink-0 cursor-pointer accent-primary"
                            checked={isChecked}
                            onChange={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              toggleLead(lead.id);
                            }}
                            onClick={(e) => e.stopPropagation()}
                            aria-label={`Selecionar ${lead.company_name}`}
                          />
                          <div className="min-w-0">
                            <CardTitle className="text-lg">{lead.company_name}</CardTitle>
                            <p className="text-sm text-muted-foreground">{lead.category || 'Sem categoria'}</p>
                          </div>
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
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
