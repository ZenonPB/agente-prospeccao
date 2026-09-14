'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Search, AlertCircle, RefreshCw, CheckCheck, X, Download, UserPlus, User, Target, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import {
  useInfiniteLeads, useCampaigns, usePreviewBulkLeads, useExecuteBulkLeads,
  useOrgMembership, useOrgMembers, LOST_REASON_OPTIONS,
  type LostReasonOption,
} from '@/hooks/use-api';
import type { BulkLeadCommand, BulkLeadPreviewResponse, Lead } from '@/types';
import { Skeleton } from '@/components/ui/skeleton';
import { WhyProspectSignals } from '@/components/oportunidades/why-prospect-signals';
import { EmptyState } from '@/components/ui/empty-state';
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';
import { getScoreBand, scoreBandBadge, SCORE_THRESHOLD_HINT } from '@/components/oportunidades/score-scale';

const getScoreColor = (score?: number | null) => scoreBandBadge[getScoreBand(score)];

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

const MAX_BULK_ITEMS = 100;

const bulkStatusOptions = [
  { value: 'CONTATADO', label: 'Marcar como contatado' },
  { value: 'RESPONDIDO', label: 'Marcar como respondeu' },
  { value: 'REUNIAO_MARCADA', label: 'Marcar reunião marcada' },
  { value: 'PROPOSTA_ENVIADA', label: 'Marcar proposta enviada' },
  { value: 'PERDIDO', label: 'Marcar como perdido' },
];

const lostReasonLabels: Record<LostReasonOption, string> = {
  PRECO: 'Preço / orçamento',
  PRAZO: 'Prazo',
  NAO_RESPONDEU: 'Sem resposta',
  CONCORRENTE: 'Fechou com concorrente',
  OUTRO: 'Outro motivo',
};

function makeBulkIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `bulk:${Date.now()}:${Math.random().toString(36).slice(2)}`;
}

function formatBulkReason(reason: string): string {
  const labels: Record<string, string> = {
    NOT_FOUND_OR_UNAUTHORIZED: 'Não encontrado ou sem acesso',
    VERSION_CONFLICT: 'Lead atualizado desde a seleção',
    NOT_AUTHORIZED: 'Sem permissão para este lead',
    ALREADY_IN_DESIRED_STATE: 'Já está nesse estado',
    ITEM_MUTATION_FAILED: 'Falha ao aplicar a alteração',
  };
  return labels[reason] || reason.replaceAll('_', ' ').toLowerCase();
}

function leadLabel(lead: Lead | undefined, id: string): string {
  return lead?.company_name || `Lead ${id.slice(0, 8)}`;
}

function escapeCsvCell(value: unknown): string {
  let text = String(value ?? '');
  // Evita formula injection ao abrir o CSV em Excel/Sheets.
  if (/^[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

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
  const csv = [headers, ...rows]
    .map((row) => row.map(escapeCsvCell).join(';'))
    .join('\n');
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
  const previewBulk = usePreviewBulkLeads();
  const executeBulk = useExecuteBulkLeads();
  const { data: membership } = useOrgMembership();
  const orgId = membership?.organization?.id;
  const myRole = membership?.membership?.role;
  const mySalesRole = membership?.membership?.sales_role;
  const canAssignOthers = myRole === 'OWNER' || myRole === 'ADMIN' || mySalesRole === 'MANAGER';
  const { data: membersData } = useOrgMembers(canAssignOthers ? orgId : undefined);

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [campaignFilter, setCampaignFilter] = useState<string>('all');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [presetFilter, setPresetFilter] = useState<'all' | 'hot' | 'qualified' | 'my_leads'>('all');
  const [minScoreFilter, setMinScoreFilter] = useState<number | undefined>(undefined);
  const [priorityFilter, setPriorityFilter] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [myLeadsOnly, setMyLeadsOnly] = useState<boolean>(false);
  const [bulkLostOpen, setBulkLostOpen] = useState(false);
  const [bulkLostReason, setBulkLostReason] = useState<LostReasonOption>('NAO_RESPONDEU');
  const [bulkPreviewOpen, setBulkPreviewOpen] = useState(false);
  const [bulkPreview, setBulkPreview] = useState<BulkLeadPreviewResponse | null>(null);
  const [bulkOperation, setBulkOperation] = useState<BulkLeadCommand | null>(null);
  const [bulkIdempotencyKey, setBulkIdempotencyKey] = useState<string | null>(null);
  const [bulkActionPending, setBulkActionPending] = useState(false);
  const bulkContextVersion = useRef(0);

  const handlePreset = (preset: 'all' | 'hot' | 'qualified' | 'my_leads') => {
    setPresetFilter(preset);
    if (preset === 'hot') {
      setPriorityFilter('HOT');
      setMinScoreFilter(undefined);
      setStatusFilter(undefined);
      setMyLeadsOnly(false);
    } else if (preset === 'qualified') {
      setPriorityFilter(undefined);
      setMinScoreFilter(60);
      setStatusFilter('QUALIFICADO');
      setMyLeadsOnly(false);
    } else if (preset === 'my_leads') {
      setPriorityFilter(undefined);
      setMinScoreFilter(undefined);
      setStatusFilter(undefined);
      setMyLeadsOnly(true);
    } else {
      setPriorityFilter(undefined);
      setMinScoreFilter(undefined);
      setStatusFilter(undefined);
      setMyLeadsOnly(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    bulkContextVersion.current += 1;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setSelected(new Set());
      setBulkLostOpen(false);
      setBulkPreviewOpen(false);
      setBulkPreview(null);
      setBulkOperation(null);
      setBulkIdempotencyKey(null);
    });
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch, campaignFilter, minScoreFilter, priorityFilter, statusFilter, myLeadsOnly]);

  const { data: campaignsData } = useCampaigns();
  const campaigns = campaignsData?.campaigns || [];

  const {
    data, isLoading, isError, error, refetch,
    fetchNextPage, hasNextPage, isFetchingNextPage, isFetchNextPageError,
  } = useInfiniteLeads({
    search: debouncedSearch || undefined,
    campaign_id: campaignFilter !== 'all' ? campaignFilter : undefined,
    min_score: minScoreFilter,
    priority: priorityFilter,
    status: statusFilter,
    assigned: myLeadsOnly ? 'me' : undefined,
  });

  const leads = data?.pages.flatMap((p) => p.leads) ?? [];
  const hasLoadedLeads = leads.length > 0;
  const hasPageLoadError = isFetchNextPageError && hasLoadedLeads;
  const totalLeads = data?.pages[0]?.total;
  const hasMore = hasNextPage ?? false;
  const loadingMore = isFetchingNextPage;

  const sortedLeads = leads;

  const selectedLeads = sortedLeads.filter((l) => selected.has(l.id));
  const allVisibleSelected = sortedLeads.length > 0 && sortedLeads.every((l) => selected.has(l.id));

  const toggleLead = useCallback((id: string) => {
    setSelected((prev) => {
      if (!prev.has(id) && prev.size >= MAX_BULK_ITEMS) {
        toast.info(`Você pode selecionar no máximo ${MAX_BULK_ITEMS} leads por vez.`);
        return prev;
      }
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleAllVisible = useCallback(() => {
    if (allVisibleSelected) {
      setSelected((prev) => new Set([...prev].filter((id) => !sortedLeads.some((l) => l.id === id))));
      return;
    }

    const candidates = sortedLeads.filter((lead) => !selected.has(lead.id));
    const available = Math.max(0, MAX_BULK_ITEMS - selected.size);
    if (available === 0) {
      toast.info(`Você pode selecionar no máximo ${MAX_BULK_ITEMS} leads por vez.`);
      return;
    }
    if (candidates.length > available) {
      toast.info(`Você pode selecionar no máximo ${MAX_BULK_ITEMS} leads por vez. Os primeiros ${available} leads visíveis foram selecionados.`);
    }

    setSelected((prev) => {
      const next = new Set(prev);
      candidates.slice(0, Math.max(0, MAX_BULK_ITEMS - prev.size)).forEach((lead) => next.add(lead.id));
      return next;
    });
  }, [allVisibleSelected, selected, sortedLeads]);

  const clearSelection = () => setSelected(new Set());

  const expectedVersionsFor = (targets: Lead[]) =>
    Object.fromEntries(
      targets
        .filter((lead) => typeof lead.updated_at === 'string' && lead.updated_at.length > 0)
        .map((lead) => [lead.id, lead.updated_at]),
    );

  const previewBulkOperation = async (command: BulkLeadCommand, closeLostDialog = false) => {
    if (command.lead_ids.length === 0 || bulkActionPending) return;
    const requestVersion = bulkContextVersion.current;
    setBulkActionPending(true);
    try {
      const preview = await previewBulk.mutateAsync(command);
      if (requestVersion !== bulkContextVersion.current) return;
      setBulkOperation(command);
      setBulkPreview(preview);
      setBulkIdempotencyKey(preview.accepted_ids.length > 0 ? makeBulkIdempotencyKey() : null);
      if (closeLostDialog) setBulkLostOpen(false);
      setBulkPreviewOpen(true);
    } catch (error) {
      if (requestVersion === bulkContextVersion.current) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível validar a operação em lote.');
      }
    } finally {
      setBulkActionPending(false);
    }
  };

  const bulkAssign = (userId: string | null) => {
    const targets = [...selectedLeads];
    if (targets.length === 0 || bulkActionPending) return;
    void previewBulkOperation({
      operation: 'assign',
      lead_ids: targets.map((lead) => lead.id),
      assigned_to_id: userId,
      expected_updated_at: expectedVersionsFor(targets),
    });
  };

  const bulkStatus = (status: string) => {
    if (status === 'PERDIDO') {
      setBulkLostReason('NAO_RESPONDEU');
      setBulkLostOpen(true);
      return;
    }

    const targets = [...selectedLeads];
    if (targets.length === 0 || bulkActionPending) return;
    void previewBulkOperation({
      operation: 'status',
      lead_ids: targets.map((lead) => lead.id),
      status: status as Lead['status'],
      expected_updated_at: expectedVersionsFor(targets),
    });
  };

  const confirmBulkLost = () => {
    const targets = [...selectedLeads];
    if (targets.length === 0 || bulkActionPending) return;
    void previewBulkOperation({
      operation: 'status',
      lead_ids: targets.map((lead) => lead.id),
      status: 'PERDIDO',
      lost_reason: bulkLostReason,
      expected_updated_at: expectedVersionsFor(targets),
    }, true);
  };

  const executePreview = async () => {
    const idempotencyKey = bulkIdempotencyKey;
    if (!bulkOperation || !bulkPreview || bulkPreview.accepted_ids.length === 0 || !idempotencyKey || bulkActionPending) return;
    const requestVersion = bulkContextVersion.current;
    const acceptedIds = bulkPreview.accepted_ids;
    const acceptedIdSet = new Set(acceptedIds);
    const expectedUpdatedAt = Object.fromEntries(
      Object.entries(bulkOperation.expected_updated_at).filter(([id]) => acceptedIdSet.has(id)),
    );
    setBulkActionPending(true);
    try {
      const result = await executeBulk.mutateAsync({
        ...bulkOperation,
        lead_ids: acceptedIds,
        expected_updated_at: expectedUpdatedAt,
        idempotency_key: idempotencyKey,
      });
      if (requestVersion !== bulkContextVersion.current) return;

      const rejectedOrFailed = new Set(
        result.items
          .filter((item) => item.status === 'REJECTED' || item.status === 'FAILED')
          .map((item) => item.id),
      );
      const previewRejected = new Set(bulkPreview.rejected.map((item) => item.id));
      setSelected((previous) => {
        const next = new Set(previous);
        acceptedIds.forEach((id) => next.delete(id));
        previewRejected.forEach((id) => next.add(id));
        rejectedOrFailed.forEach((id) => next.add(id));
        return next;
      });
      setBulkPreviewOpen(false);
      setBulkPreview(null);
      setBulkOperation(null);
      setBulkIdempotencyKey(null);

      const operationLabel = bulkOperation.operation === 'assign'
        ? 'atribuição'
        : `status para ${statusLabels[bulkOperation.status || ''] || bulkOperation.status}`;
      toast.success(
        `${operationLabel}: ${result.accepted} aplicado(s), ${result.duplicate} já estava(m) no estado e ${result.rejected + result.failed} pendência(s).${result.replayed ? ' A operação já tinha sido aplicada com segurança.' : ''}`,
      );
      const issues = result.items.filter((item) => item.status === 'REJECTED' || item.status === 'FAILED');
      if (issues.length > 0) {
        const reasons = [...new Set(issues.map((item) => formatBulkReason(item.reason || item.status)))].join('; ');
        toast.error(`${issues.length} lead(s) continuam selecionados: ${reasons}.`);
      }
    } catch (error) {
      if (requestVersion === bulkContextVersion.current) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível executar a operação em lote. Nenhuma alteração foi aplicada.');
      }
    } finally {
      setBulkActionPending(false);
    }
  };

  const previewLeadById = (id: string) => leads.find((lead) => lead.id === id);

  return (
    <div className="space-y-4" data-tour="oportunidades-lista">
      <div data-tour="oportunidades-filtros" className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mr-1">
          Filtros Rápidos:
        </span>
        <Button
          variant={presetFilter === 'all' ? 'default' : 'outline'}
          size="sm"
          className="h-9 rounded-full text-xs font-medium sm:h-8"
          onClick={() => handlePreset('all')}
        >
          Todos os leads
        </Button>
        <Button
          variant={presetFilter === 'hot' ? 'default' : 'outline'}
          size="sm"
          className="h-9 rounded-full text-xs font-medium sm:h-8"
          onClick={() => handlePreset('hot')}
        >
          🔥 Leads Quentes
        </Button>
        <Button
          variant={presetFilter === 'qualified' ? 'default' : 'outline'}
          size="sm"
          className="h-9 rounded-full text-xs font-medium sm:h-8"
          onClick={() => handlePreset('qualified')}
        >
          ✅ Aptos para Contato
        </Button>
        {currentUserId && (
          <Button
            variant={presetFilter === 'my_leads' ? 'default' : 'outline'}
            size="sm"
            className="h-9 rounded-full text-xs font-medium sm:h-8"
            onClick={() => handlePreset('my_leads')}
          >
            👤 Meus Leads
          </Button>
        )}
      </div>

      <div data-tour="oportunidades-busca" className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-0 flex-1 sm:w-64">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar lead..."
            className="h-10 w-full min-w-0 pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={campaignFilter} onValueChange={(v) => setCampaignFilter(v || 'all')}>
          <SelectTrigger className="w-full sm:w-[180px] h-10">
            <SelectValue>
              {(value) =>
                value === 'all'
                  ? 'Todas as buscas'
                  : campaigns.find((c) => c.id === value)?.name ?? 'Busca'
              }
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas as buscas</SelectItem>
            {campaigns.map((c) => (
              <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-xs text-muted-foreground" title="A lista vem do servidor em ordem de aptidão">
          {SCORE_THRESHOLD_HINT} · ordenado por aptidão
        </span>
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
            className="h-9 sm:h-8"
            onClick={() => bulkAssign(currentUserId!)}
            disabled={!currentUserId || bulkActionPending}
          >
            <UserPlus className="mr-1.5 h-3.5 w-3.5" />
            Atribuir a mim
          </Button>
          {canAssignOthers && (
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="outline" size="sm" className="h-9 sm:h-8" disabled={bulkActionPending} />}>
                <User className="mr-1.5 h-3.5 w-3.5" />
                Atribuir para
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
                <DropdownMenuGroup>
                  <DropdownMenuLabel>Atribuir para</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {membersData?.members
                    .filter((m) => m.user_id !== currentUserId)
                    .map((m) => (
                    <DropdownMenuItem key={m.user_id} onClick={() => bulkAssign(m.user_id)}>
                      <User className="mr-2 h-3.5 w-3.5" />
                      {m.name || m.email}
                    </DropdownMenuItem>
                    ))}
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <Select onValueChange={(v) => { if (v) void bulkStatus(v as string); }} disabled={bulkActionPending}>
            <SelectTrigger className="h-9 w-auto sm:h-8">
              <SelectValue>
                {(value) => bulkStatusOptions.find((o) => o.value === value)?.label ?? 'Mover para...'}
              </SelectValue>
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
            className="h-9 sm:h-8"
            onClick={() => {
              exportSelectedCsv(selectedLeads, 'leads-selecionados.csv');
              clearSelection();
            }}
            disabled={bulkActionPending}
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            Exportar CSV
          </Button>
          <Button variant="ghost" size="sm" className="h-9 sm:h-8" onClick={clearSelection} disabled={bulkActionPending}>
            <X className="mr-1.5 h-3.5 w-3.5" />
            Limpar
          </Button>
        </div>
      )}

      {isLoading && !hasLoadedLeads ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <LeadCardSkeleton key={i} />
          ))}
        </div>
      ) : isError && !hasLoadedLeads ? (
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
        <EmptyState
          icon={<Target className="h-5 w-5" aria-hidden="true" />}
          title={myLeadsOnly ? 'Nenhum lead atribuído a você' : 'Nenhum lead encontrado'}
          description={myLeadsOnly
            ? 'Sua carteira está vazia com os filtros atuais. Veja todos os leads ou peça uma atribuição ao gestor.'
            : 'Nenhuma oportunidade atende aos filtros selecionados. Tente ajustar a busca ou os status.'}
          action={myLeadsOnly ? (
            <Button variant="outline" size="sm" onClick={() => handlePreset('all')}>
              Ver todos os leads
            </Button>
          ) : undefined}
        />
      ) : (
        <>
          {hasPageLoadError && (
            <div
              className="flex flex-col gap-3 rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between"
              role="status"
              aria-live="polite"
            >
              <div className="flex items-start gap-2">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <div>
                  <p className="font-medium">Não foi possível carregar a próxima página.</p>
                  <p className="text-xs text-amber-800">Os leads já carregados continuam disponíveis.</p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-9 border-amber-300 bg-transparent sm:h-8"
                onClick={() => void fetchNextPage()}
                disabled={loadingMore}
              >
                <RefreshCw className="mr-2 h-3 w-3" aria-hidden="true" />
                Tentar carregar novamente
              </Button>
            </div>
          )}
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
            <span className="ml-auto">{totalLeads ?? leads.length} lead(s)</span>
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
                      <div className="flex flex-wrap items-start justify-between gap-2">
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
                        <div className="flex flex-wrap items-center justify-end gap-2 shrink-0">
                          {lead.priority && priorityBadgeConfig[lead.priority] && (
                            <Badge className={`${priorityBadgeConfig[lead.priority].color} text-xs`}>
                              <span className="mr-1">{priorityBadgeConfig[lead.priority].emoji}</span>
                              {priorityBadgeConfig[lead.priority].label}
                            </Badge>
                          )}
                          <Badge
                            className={getScoreColor(lead.qualification_score)}
                            title={getScoreBand(lead.qualification_score) === 'unevaluated' ? 'Ainda não avaliado' : SCORE_THRESHOLD_HINT}
                          >
                            {getScoreBand(lead.qualification_score) === 'unevaluated' ? 'não avaliado' : lead.qualification_score}
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2 text-sm">
                        <WhyProspectSignals signals={lead.why_signals} />
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
          {hasMore && (
            <div className="mt-6 flex justify-center">
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchNextPage()}
                disabled={loadingMore}
              >
                {loadingMore ? (
                  <RefreshCw className="mr-2 h-3 w-3 animate-spin" aria-hidden="true" />
                ) : null}
                Carregar mais{typeof totalLeads === 'number' ? ` (${Math.max(0, totalLeads - leads.length)} restantes)` : ''}
              </Button>
            </div>
          )}
        </>
      )}

      <Dialog
        open={bulkPreviewOpen}
        onOpenChange={(open) => {
          if (!bulkActionPending) setBulkPreviewOpen(open);
        }}
      >
        <DialogContent className="w-[calc(100%-2rem)] sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>Revisar operação em lote</DialogTitle>
            <DialogDescription>
              {bulkOperation?.operation === 'assign'
                ? 'Confira a atribuição antes de aplicar as alterações.'
                : `Confira os leads antes de marcar como ${statusLabels[bulkOperation?.status || ''] || 'novo status'}.`}
            </DialogDescription>
          </DialogHeader>
          {bulkPreview && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                <div className="rounded-lg border bg-muted/30 p-3">
                  <p className="text-muted-foreground">Selecionados</p>
                  <p className="mt-1 text-lg font-semibold">{bulkPreview.total_selected}</p>
                </div>
                <div className="rounded-lg border bg-emerald-50 p-3 text-emerald-800">
                  <p>Aceitos</p>
                  <p className="mt-1 text-lg font-semibold">{bulkPreview.accepted_ids.length}</p>
                </div>
                <div className="rounded-lg border bg-amber-50 p-3 text-amber-800">
                  <p>Rejeitados</p>
                  <p className="mt-1 text-lg font-semibold">{bulkPreview.rejected.length}</p>
                </div>
              </div>
              {bulkPreview.rejected.length > 0 ? (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium">Itens que não serão executados</h3>
                  <ul className="max-h-48 space-y-2 overflow-y-auto rounded-lg border p-3 text-sm" aria-label="Motivos das rejeições">
                    {bulkPreview.rejected.map((item) => (
                      <li key={item.id} className="flex items-start justify-between gap-3">
                        <span className="min-w-0 break-words">{leadLabel(previewLeadById(item.id), item.id)}</span>
                        <span className="shrink-0 text-right text-muted-foreground">{formatBulkReason(item.reason)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Todos os itens selecionados estão aptos para esta operação.</p>
              )}
              {bulkPreview.accepted_ids.length === 0 && (
                <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                  Nenhum item foi aceito. A operação não pode ser executada.
                </p>
              )}
            </div>
          )}
          <DialogFooter className="flex-col-reverse gap-2 sm:flex-row">
            <Button variant="outline" className="h-11" onClick={() => setBulkPreviewOpen(false)} disabled={bulkActionPending}>
              Cancelar
            </Button>
            <Button className="h-11" onClick={() => void executePreview()} disabled={bulkActionPending || !bulkPreview || bulkPreview.accepted_ids.length === 0}>
              {bulkActionPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
              Executar itens aceitos
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={bulkLostOpen}
        onOpenChange={(open) => {
          if (!bulkActionPending) setBulkLostOpen(open);
        }}
      >
        <DialogContent className="w-[calc(100%-2rem)] sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle>Marcar {selectedLeads.length} lead(s) como perdido(s)</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              A perda é um resultado comercial e exige motivo. O mesmo motivo será aplicado a todos os leads selecionados.
            </p>
            <div className="space-y-2">
              <label htmlFor="bulkLostReason" className="text-sm font-medium">Motivo da perda</label>
              <select
                id="bulkLostReason"
                value={bulkLostReason}
                onChange={(event) => setBulkLostReason(event.target.value as LostReasonOption)}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                disabled={bulkActionPending}
              >
                {LOST_REASON_OPTIONS.map((reason) => (
                  <option key={reason} value={reason}>{lostReasonLabels[reason]}</option>
                ))}
              </select>
            </div>
          </div>
          <DialogFooter className="flex-col-reverse gap-2 sm:flex-row">
            <Button variant="outline" className="h-11" onClick={() => setBulkLostOpen(false)} disabled={bulkActionPending}>
              Cancelar
            </Button>
            <Button className="h-11" onClick={() => void confirmBulkLost()} disabled={bulkActionPending || selectedLeads.length === 0}>
              {bulkActionPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Continuar para revisão
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
