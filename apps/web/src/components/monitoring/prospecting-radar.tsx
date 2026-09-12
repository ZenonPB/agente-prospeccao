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
import type { AgentState, ProspectingAlert } from '@/lib/prospecting-automation-api';

const STATE_LABELS: Record<AgentState, string> = {
  DISCOVERED: 'Descoberto',
  NEEDS_ENRICHMENT: 'Precisa enriquecer',
  READY_TO_SCORE: 'Pronto para score',
  READY_FOR_CONTACT: 'Pronto para contato',
  AWAITING_ACTION: 'Aguardando ação',
  IN_SEQUENCE: 'Em sequência',
  WAITING: 'Em espera',
  REENGAGE: 'Reengajar',
  CLOSED: 'Encerrado',
};

function formatDate(value?: string | null) {
  if (!value) return 'Ainda não executada';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Data indisponível' : date.toLocaleString('pt-BR');
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
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
  const [minScore, setMinScore] = useState('60');
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
    const numericScore = Number(minScore);
    try {
      await createSearch.mutateAsync({
        name: name.trim(),
        offer_key: offerKey.trim() || null,
        filters: {
          ...(query.trim() ? { q: query.trim() } : {}),
          ...(city.trim() ? { city: city.trim() } : {}),
          ...(state.trim() ? { state: state.trim().toUpperCase() } : {}),
          ...(Number.isFinite(numericScore) ? { min_score: Math.max(0, Math.min(100, numericScore)) } : {}),
          ...(hasEmail ? { has_email: true } : {}),
          ...(hasPhone ? { has_phone: true } : {}),
        },
        schedule: 'manual',
        notification_policy: { create_alert: true },
      });
      setName('');
      toast.success('Busca salva criada. Você pode executá-la agora sem consumir providers externos.');
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível salvar a busca.'));
    }
  }

  async function executeSavedSearch(id: string) {
    try {
      const result = await runSearch.mutateAsync(id);
      toast.success(`${result.matches.length} match(es) encontrado(s) · ${result.created_alerts} novo(s) alerta(s).`);
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível executar a busca.'));
    }
  }

  async function executeWatch() {
    try {
      const result = await runWatch.mutateAsync();
      if (result.status === 'disabled') {
        toast.info('Monitoramento externo desativado neste workspace. As cotas opt-in continuam protegidas.');
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
          <CardContent className="text-sm text-muted-foreground">Filtros reutilizáveis e isolados por workspace.</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardDescription>Alertas novos</CardDescription><CardTitle className="text-3xl">{unreadAlerts}</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">Matches e janelas de recompra ainda não revisados.</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardDescription>Séries de eventos</CardDescription><CardTitle className="text-3xl">{series.data?.items.length ?? 0}</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">Recorrência inferida somente a partir do histórico observado.</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardDescription>Prontos para contato</CardDescription><CardTitle className="text-3xl">{agentCounts.get('READY_FOR_CONTACT') ?? 0}</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">Estado derivado de oportunidade, contato e ação disponível.</CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.05fr_1.35fr]" aria-labelledby="saved-searches-heading">
        <Card>
          <CardHeader>
            <CardTitle id="saved-searches-heading" className="flex items-center gap-2"><Search className="size-5" aria-hidden="true" />Nova busca salva</CardTitle>
            <CardDescription>Crie um radar sobre leads já conhecidos. Executar esta busca não chama fontes pagas.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={submitSearch}>
              <div className="space-y-2"><Label htmlFor="search-name">Nome</Label><Input id="search-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Metalúrgicas SP com score alto" maxLength={160} required /></div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2"><Label htmlFor="search-query">Empresa ou termo</Label><Input id="search-query" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="metalúrgica" /></div>
                <div className="space-y-2"><Label htmlFor="offer-key">Oferta</Label><Input id="offer-key" value={offerKey} onChange={(e) => setOfferKey(e.target.value)} placeholder="mechanical_project" /></div>
                <div className="space-y-2"><Label htmlFor="search-city">Cidade</Label><Input id="search-city" value={city} onChange={(e) => setCity(e.target.value)} placeholder="São Carlos" /></div>
                <div className="space-y-2"><Label htmlFor="search-state">UF</Label><Input id="search-state" value={state} onChange={(e) => setState(e.target.value.slice(0, 2))} placeholder="SP" maxLength={2} /></div>
                <div className="space-y-2"><Label htmlFor="min-score">Score mínimo</Label><Input id="min-score" type="number" min={0} max={100} value={minScore} onChange={(e) => setMinScore(e.target.value)} /></div>
              </div>
              <fieldset className="flex flex-wrap gap-4 rounded-lg border p-3">
                <legend className="px-1 text-sm font-medium">Contato mínimo</legend>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={hasEmail} onChange={(e) => setHasEmail(e.target.checked)} className="size-4" />Com e-mail</label>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={hasPhone} onChange={(e) => setHasPhone(e.target.checked)} className="size-4" />Com telefone</label>
              </fieldset>
              <Button type="submit" disabled={createSearch.isPending || !name.trim()}>
                {createSearch.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Sparkles className="size-4" aria-hidden="true" />}Salvar busca
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Buscas ativas</CardTitle><CardDescription>Execute sob demanda e transforme somente matches novos em alertas.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {(saved.data?.items.length ?? 0) === 0 ? (
              <EmptyState title="Nenhuma busca salva" description="Crie a primeira busca para começar a acompanhar seu ICP sem repetir filtros manualmente." />
            ) : saved.data?.items.map((item) => (
              <article key={item.id} className="rounded-xl border p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2"><h3 className="font-medium">{item.name}</h3><Badge variant={item.enabled ? 'outline' : 'secondary'}>{item.enabled ? 'Ativa' : 'Pausada'}</Badge>{item.offer_key && <Badge variant="secondary">{item.offer_key}</Badge>}</div>
                    <p className="mt-1 text-xs text-muted-foreground">Última execução: {formatDate(item.last_run_at)}</p>
                    <p className="mt-2 text-sm text-muted-foreground">{Object.entries(item.filters).map(([key, value]) => `${key}: ${String(value)}`).join(' · ') || 'Sem filtros adicionais'}</p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button variant="outline" size="sm" onClick={() => void toggleSearch.mutateAsync({ id: item.id, enabled: !item.enabled })}>{item.enabled ? 'Pausar' : 'Ativar'}</Button>
                    <Button size="sm" disabled={!item.enabled || runSearch.isPending} onClick={() => void executeSavedSearch(item.id)}><Play className="size-4" aria-hidden="true" />Executar</Button>
                  </div>
                </div>
              </article>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-2" aria-label="Monitoramento e recorrência">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><BellRing className="size-5" aria-hidden="true" />Alertas comerciais</CardTitle><CardDescription>O sistema deduplica o mesmo match para não criar ruído operacional.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {(alerts.data?.items.length ?? 0) === 0 ? <EmptyState title="Nenhum alerta" description="Execute uma busca salva ou atualize séries recorrentes para gerar alertas fundamentados." /> : alerts.data?.items.slice(0, 12).map((alert) => (
              <article key={alert.id} className="rounded-xl border p-4">
                <div className="flex items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><h3 className="font-medium">{alert.title}</h3><Badge variant={alert.status === 'new' ? 'default' : 'outline'}>{alert.status === 'new' ? 'Novo' : alert.status}</Badge></div><p className="mt-1 text-sm text-muted-foreground">{alert.reason}</p>{typeof alert.score === 'number' && <p className="mt-2 text-xs text-muted-foreground">Confiança/score: {Math.round(alert.score)}</p>}</div>{alert.status === 'new' && <Button variant="ghost" size="sm" onClick={() => void setAlertStatus(alert, 'read')}>Marcar lido</Button>}</div>
              </article>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><CalendarClock className="size-5" aria-hidden="true" />Eventos recorrentes</CardTitle><CardDescription>Séries são inferidas pelo histórico; só recorrências com confiança suficiente entram na janela de recompra.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            <Button variant="outline" disabled={refreshSeries.isPending} onClick={() => void materializeEventSeries()}><RefreshCw className={refreshSeries.isPending ? 'size-4 animate-spin' : 'size-4'} aria-hidden="true" />Recalcular recorrência</Button>
            {(series.data?.items.length ?? 0) === 0 ? <EmptyState title="Sem séries detectadas" description="Eventos repetidos com nome, organizador e histórico compatíveis aparecerão aqui." /> : series.data?.items.slice(0, 10).map((item) => (
              <article key={item.id} className="flex items-start justify-between gap-4 rounded-xl border p-4"><div><h3 className="font-medium">{item.name}</h3><p className="mt-1 text-xs text-muted-foreground">{item.family || 'Evento'} · confiança {Math.round(item.recurrence_confidence * 100)}%</p>{item.expected_next_window?.start && <p className="mt-2 text-sm">Próxima janela: {item.expected_next_window.start} → {item.expected_next_window.end}</p>}</div><ShieldCheck className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" /></article>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]" aria-label="Estado operacional do agente">
        <Card>
          <CardHeader><CardTitle>Fila do agente</CardTitle><CardDescription>Estado determinístico e auditável; nenhuma ação comercial é executada apenas por classificação.</CardDescription></CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(Object.keys(STATE_LABELS) as AgentState[]).map((key) => <div key={key} className="rounded-xl border p-4"><p className="text-sm text-muted-foreground">{STATE_LABELS[key]}</p><p className="mt-1 text-2xl font-semibold">{agentCounts.get(key) ?? 0}</p></div>)}
            </div>
            <Button className="mt-4" variant="outline" disabled={refreshStates.isPending} onClick={() => void materializeAgentStates()}><RefreshCw className={refreshStates.isPending ? 'size-4 animate-spin' : 'size-4'} aria-hidden="true" />Recalcular estados</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Radar className="size-5" aria-hidden="true" />Monitoramento externo</CardTitle><CardDescription>Execução manual respeita todas as cotas e opt-ins. Se o workspace estiver desabilitado, nenhuma fonte externa é chamada.</CardDescription></CardHeader>
          <CardContent className="space-y-4"><div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">Feeds de vagas, notícias e social continuam protegidos por quota própria. O botão força apenas o horário da checagem — nunca ignora orçamento ou configuração.</div><Button onClick={() => void executeWatch()} disabled={runWatch.isPending}>{runWatch.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Radar className="size-4" aria-hidden="true" />}Executar monitoramento agora</Button></CardContent>
        </Card>
      </section>
    </div>
  );
}
