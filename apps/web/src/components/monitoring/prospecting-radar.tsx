'use client';

import { FormEvent, useMemo, useState } from 'react';
import {
  BellRing,
  CalendarClock,
  Loader2,
  Play,
  Radar,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  useAgentStates,
  useAlerts,
  useCreateSavedSearch,
  useEventSeries,
  usePatchAlert,
  useRefreshAgentStates,
  useRefreshEventSeries,
  useRunContinuousWatch,
  useRunSavedSearch,
  useSavedSearches,
  useToggleSavedSearch,
} from '@/hooks/use-prospecting-automation';
import { filterLabel, filterValueLabel } from '@/lib/commercial-labels';
import { OFFER_PROFILE_OPTIONS, offerProfileLabel } from '@/lib/offers';
import type { AgentState, ProspectingAlert, SavedSearchFilters } from '@/lib/prospecting-automation-api';

const STATE_LABELS: Record<AgentState, string> = {
  DISCOVERED: 'Novo no radar',
  NEEDS_ENRICHMENT: 'Precisa de mais informações',
  READY_TO_SCORE: 'Pronto para avaliar',
  READY_FOR_CONTACT: 'Pronto para contato',
  AWAITING_ACTION: 'Aguardando ação',
  IN_SEQUENCE: 'Em abordagem',
  WAITING: 'Em espera',
  REENGAGE: 'Hora de retomar',
  CLOSED: 'Encerrado',
};

const ALERT_STATUS_LABELS: Record<string, string> = {
  new: 'Novo',
  read: 'Revisado',
  dismissed: 'Arquivado',
  actioned: 'Ação realizada',
};

function formatDate(value?: string | null) {
  if (!value) return 'Ainda não executada';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Data indisponível' : date.toLocaleString('pt-BR');
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function filtersSummary(filters: SavedSearchFilters) {
  const entries = Object.entries(filters);
  if (!entries.length) return 'Sem filtros adicionais';
  return entries.map(([key, value]) => `${filterLabel(key)}: ${filterValueLabel(key, value)}`).join(' · ');
}

export function ProspectingRadar() {
  const saved = useSavedSearches();
  const alerts = useAlerts();
  const series = useEventSeries();
  const states = useAgentStates();
  const createSearch = useCreateSavedSearch();
  const runSearch = useRunSavedSearch();
  const toggleSearch = useToggleSavedSearch();
  const patchAlert = usePatchAlert();
  const refreshSeries = useRefreshEventSeries();
  const refreshStates = useRefreshAgentStates();
  const runWatch = useRunContinuousWatch();

  const [name, setName] = useState('');
  const [query, setQuery] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [offerKey, setOfferKey] = useState('');
  const [minQuality, setMinQuality] = useState('60');
  const [hasEmail, setHasEmail] = useState(true);
  const [hasPhone, setHasPhone] = useState(false);

  const unreadAlerts = useMemo(
    () => alerts.data?.items.filter((item) => item.status === 'new').length ?? 0,
    [alerts.data],
  );
  const agentCounts = useMemo(() => {
    const counts = new Map<AgentState, number>();
    for (const item of states.data?.items ?? []) counts.set(item.state, (counts.get(item.state) ?? 0) + 1);
    return counts;
  }, [states.data]);

  const loading = saved.isLoading || alerts.isLoading || series.isLoading || states.isLoading;
  const failed = saved.isError || alerts.isError || series.isError || states.isError;

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    const numericQuality = Number(minQuality);
    try {
      await createSearch.mutateAsync({
        name: name.trim(),
        offer_key: offerKey || null,
        filters: {
          ...(query.trim() ? { q: query.trim() } : {}),
          ...(city.trim() ? { city: city.trim() } : {}),
          ...(state.trim() ? { state: state.trim().toUpperCase() } : {}),
          ...(Number.isFinite(numericQuality) ? { min_score: Math.max(0, Math.min(100, numericQuality)) } : {}),
          ...(hasEmail ? { has_email: true } : {}),
          ...(hasPhone ? { has_phone: true } : {}),
        },
        schedule: 'manual',
        notification_policy: { create_alert: true },
      });
      setName('');
      toast.success('Busca salva criada. Ela pode ser executada sem consultar fontes externas.');
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível salvar a busca.'));
    }
  }

  async function executeSavedSearch(id: string) {
    try {
      const result = await runSearch.mutateAsync(id);
      toast.success(`${result.matches.length} resultado(s) encontrado(s) · ${result.created_alerts} novo(s) alerta(s).`);
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível executar a busca.'));
    }
  }

  async function executeWatch() {
    try {
      const result = await runWatch.mutateAsync();
      if (result.status === 'disabled') {
        toast.info('Monitoramento externo desativado neste workspace. Nenhuma fonte externa foi consultada.');
        return;
      }
      toast.success(`Monitoramento concluído: ${result.processed} lead(s), ${result.changed} alteração(ões).`);
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível executar o monitoramento.'));
    }
  }

  async function materializeEventSeries() {
    try {
      const result = await refreshSeries.mutateAsync();
      toast.success(`${result.series} série(s) analisada(s) · ${result.rebuy_alerts_created} alerta(s) de recompra criado(s).`);
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível atualizar recorrências.'));
    }
  }

  async function materializeAgentStates() {
    try {
      const result = await refreshStates.mutateAsync();
      const total = Object.values(result.states).reduce((sum, value) => sum + value, 0);
      toast.success(`Estado operacional recalculado para ${total} lead(s).`);
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível atualizar o estado do agente.'));
    }
  }

  async function setAlertStatus(alert: ProspectingAlert, status: ProspectingAlert['status']) {
    try {
      await patchAlert.mutateAsync({ id: alert.id, status });
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível atualizar o alerta.'));
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center" role="status" aria-live="polite">
        <Loader2 className="size-5 animate-spin" aria-hidden="true" />
        <span className="ml-2 text-sm text-muted-foreground">Carregando radar comercial...</span>
      </div>
    );
  }

  if (failed) {
    const error = saved.error ?? alerts.error ?? series.error ?? states.error;
    return (
      <EmptyState
        icon={<Radar className="size-6" aria-hidden="true" />}
        title="Não foi possível carregar o radar"
        description={errorMessage(error, 'Tente novamente em instantes.')}
        action={<Button onClick={() => void Promise.all([saved.refetch(), alerts.refetch(), series.refetch(), states.refetch()])}>Tentar novamente</Button>}
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Resumo do radar">
        <Card>
          <CardHeader className="pb-2"><CardDescription>Buscas salvas</CardDescription><CardTitle className="text-3xl">{saved.data?.items.length ?? 0}</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">Critérios reutilizáveis e isolados por workspace.</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardDescription>Alertas novos</CardDescription><CardTitle className="text-3xl">{unreadAlerts}</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">Oportunidades e janelas de recompra ainda não revisadas.</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardDescription>Séries de eventos</CardDescription><CardTitle className="text-3xl">{series.data?.items.length ?? 0}</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">Recorrência estimada somente a partir do histórico observado.</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardDescription>Prontos para contato</CardDescription><CardTitle className="text-3xl">{agentCounts.get('READY_FOR_CONTACT') ?? 0}</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">Leads com oportunidade, contato e próxima ação disponíveis.</CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.05fr_1.35fr]" aria-labelledby="saved-searches-heading">
        <Card>
          <CardHeader>
            <CardTitle id="saved-searches-heading" className="flex items-center gap-2"><Search className="size-5" aria-hidden="true" />Nova busca salva</CardTitle>
            <CardDescription>Salve critérios para encontrar novamente oportunidades já conhecidas pelo sistema.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={submitSearch}>
              <div className="space-y-2">
                <Label htmlFor="search-name">Nome da busca</Label>
                <Input id="search-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Ex.: Metalúrgicas de SP com boa qualidade" maxLength={160} required />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2"><Label htmlFor="search-query">Empresa ou termo</Label><Input id="search-query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Metalúrgica" /></div>
                <div className="space-y-2">
                  <Label htmlFor="offer-key">Oferta</Label>
                  <Select value={offerKey || 'any'} onValueChange={(value) => setOfferKey(value === 'any' || value == null ? '' : value)}>
                    <SelectTrigger id="offer-key" className="w-full"><SelectValue>{(value) => (value === 'any' ? 'Qualquer oferta' : offerProfileLabel(value as string))}</SelectValue></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Qualquer oferta</SelectItem>
                      {OFFER_PROFILE_OPTIONS.map((offer) => <SelectItem key={offer.key} value={offer.key}>{offer.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2"><Label htmlFor="search-city">Cidade</Label><Input id="search-city" value={city} onChange={(event) => setCity(event.target.value)} placeholder="São Carlos" /></div>
                <div className="space-y-2"><Label htmlFor="search-state">Estado (UF)</Label><Input id="search-state" value={state} onChange={(event) => setState(event.target.value.slice(0, 2))} placeholder="SP" maxLength={2} /></div>
                <div className="space-y-2"><Label htmlFor="min-quality">Qualidade mínima</Label><Input id="min-quality" type="number" min={0} max={100} value={minQuality} onChange={(event) => setMinQuality(event.target.value)} /></div>
              </div>
              <fieldset className="space-y-3 rounded-lg border p-3">
                <legend className="px-1 text-sm font-medium">Dados de contato necessários</legend>
                <ToggleLine id="saved-search-email" label="Exigir e-mail" checked={hasEmail} onChange={setHasEmail} />
                <ToggleLine id="saved-search-phone" label="Exigir telefone" checked={hasPhone} onChange={setHasPhone} />
              </fieldset>
              <Button type="submit" disabled={createSearch.isPending || !name.trim()}>
                {createSearch.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Sparkles className="size-4" aria-hidden="true" />}
                Salvar busca
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Buscas salvas</CardTitle><CardDescription>Execute quando quiser e receba alertas apenas para resultados novos.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {(saved.data?.items.length ?? 0) === 0 ? (
              <EmptyState title="Nenhuma busca salva" description="Crie sua primeira busca para acompanhar um perfil de cliente sem repetir os filtros manualmente." />
            ) : saved.data?.items.map((item) => (
              <article key={item.id} className="rounded-xl border p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-medium">{item.name}</h3>
                      <Badge variant={item.enabled ? 'outline' : 'secondary'}>{item.enabled ? 'Ativa' : 'Pausada'}</Badge>
                      {item.offer_key ? <Badge variant="secondary">{offerProfileLabel(item.offer_key)}</Badge> : null}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">Última execução: {formatDate(item.last_run_at)}</p>
                    <p className="mt-2 text-sm text-muted-foreground">{filtersSummary(item.filters)}</p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button variant="outline" size="sm" disabled={toggleSearch.isPending} onClick={() => void toggleSearch.mutateAsync({ id: item.id, enabled: !item.enabled })}>{item.enabled ? 'Pausar' : 'Ativar'}</Button>
                    <Button size="sm" disabled={!item.enabled || runSearch.isPending} onClick={() => void executeSavedSearch(item.id)}><Play className="size-4" aria-hidden="true" />Executar</Button>
                  </div>
                </div>
              </article>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-2" aria-label="Alertas e recorrência">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><BellRing className="size-5" aria-hidden="true" />Alertas comerciais</CardTitle><CardDescription>Resultados repetidos são agrupados para reduzir ruído operacional.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {(alerts.data?.items.length ?? 0) === 0 ? <EmptyState title="Nenhum alerta" description="Execute uma busca salva ou atualize eventos recorrentes para gerar alertas fundamentados." /> : alerts.data?.items.slice(0, 12).map((alert) => (
              <article key={alert.id} className="rounded-xl border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2"><h3 className="font-medium">{alert.title}</h3><Badge variant={alert.status === 'new' ? 'default' : 'outline'}>{ALERT_STATUS_LABELS[alert.status] ?? 'Atualizado'}</Badge></div>
                    <p className="mt-1 text-sm text-muted-foreground">{alert.reason}</p>
                    {typeof alert.score === 'number' ? <p className="mt-2 text-xs text-muted-foreground">Indicador de oportunidade: {Math.round(alert.score)}</p> : null}
                  </div>
                  {alert.status === 'new' ? <Button variant="ghost" size="sm" onClick={() => void setAlertStatus(alert, 'read')}>Marcar como revisado</Button> : null}
                </div>
              </article>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><CalendarClock className="size-5" aria-hidden="true" />Eventos recorrentes</CardTitle><CardDescription>O histórico observado ajuda a estimar quando vale retomar uma oportunidade sazonal.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            <Button variant="outline" disabled={refreshSeries.isPending} onClick={() => void materializeEventSeries()}><RefreshCw className={refreshSeries.isPending ? 'size-4 animate-spin' : 'size-4'} aria-hidden="true" />Atualizar recorrências</Button>
            {(series.data?.items.length ?? 0) === 0 ? <EmptyState title="Sem recorrências detectadas" description="Eventos repetidos com histórico compatível aparecerão aqui." /> : series.data?.items.slice(0, 10).map((item) => (
              <article key={item.id} className="flex items-start justify-between gap-4 rounded-xl border p-4"><div><h3 className="font-medium">{item.name}</h3><p className="mt-1 text-xs text-muted-foreground">{item.family || 'Evento'} · confiança {Math.round(item.recurrence_confidence * 100)}%</p>{item.expected_next_window?.start ? <p className="mt-2 text-sm">Próxima janela: {item.expected_next_window.start} → {item.expected_next_window.end}</p> : null}</div><ShieldCheck className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" /></article>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]" aria-label="Estado operacional">
        <Card>
          <CardHeader><CardTitle>Fila operacional</CardTitle><CardDescription>Classificação auditável para ajudar a equipe a decidir o próximo trabalho. Ela não executa contato comercial sozinha.</CardDescription></CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(Object.keys(STATE_LABELS) as AgentState[]).map((key) => <div key={key} className="rounded-xl border p-4"><p className="text-sm text-muted-foreground">{STATE_LABELS[key]}</p><p className="mt-1 text-2xl font-semibold">{agentCounts.get(key) ?? 0}</p></div>)}
            </div>
            <Button className="mt-4" variant="outline" disabled={refreshStates.isPending} onClick={() => void materializeAgentStates()}><RefreshCw className={refreshStates.isPending ? 'size-4 animate-spin' : 'size-4'} aria-hidden="true" />Atualizar classificação</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Radar className="size-5" aria-hidden="true" />Atualização por fontes externas</CardTitle><CardDescription>Consulta manual protegida pelas permissões e limites configurados para este workspace.</CardDescription></CardHeader>
          <CardContent className="space-y-4"><div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">Vagas, notícias e sinais sociais só são consultados quando a fonte estiver habilitada e houver cota disponível.</div><Button onClick={() => void executeWatch()} disabled={runWatch.isPending}>{runWatch.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Radar className="size-4" aria-hidden="true" />}Atualizar sinais agora</Button></CardContent>
        </Card>
      </section>
    </div>
  );
}

function ToggleLine({ id, label, checked, onChange }: { id: string; label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <Label htmlFor={id} className="font-normal">{label}</Label>
      <Switch id={id} checked={checked} onCheckedChange={(value) => onChange(value === true)} />
    </div>
  );
}
