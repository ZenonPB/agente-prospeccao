'use client';

import { ShieldAlert, Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/page-header';
import { useCommercialFilters } from '@/hooks/use-commercial-filters';
import {
  useOrgMembership,
  useScoreFeedbackMetrics,
  useAnalyticsOverview,
  useAnalyticsFunnel,
  useAnalyticsConsultants,
  useAnalyticsRanking,
  useAnalyticsGeo,
  useAnalyticsCampaigns,
  useAnalyticsTimeline,
  useAnalyticsForecast,
  useExportAnalyticsPdf,
} from '@/hooks/use-api';
import { ExecutiveKpis, ExecutiveKpisSkeleton } from '@/components/relatorios/executive-kpis';
import { FunnelCard, RatesCard, ScoreBandsCard, NegotiationCard, ChartCardSkeleton, ChartCardError } from '@/components/relatorios/chart-cards';
import { FunnelEndToEndCard, FunnelEndToEndSkeleton } from '@/components/relatorios/funnel-e2e-card';
import { ForecastCard } from '@/components/relatorios/forecast-card';
import { ConsultantsCard, CampaignsCard, TopLeadsCard, ListCardSkeleton } from '@/components/relatorios/list-cards';
import { GeoCard, GeoCardSkeleton } from '@/components/relatorios/brazil-state-map';
import { TimelineCard, TimelineSkeleton } from '@/components/relatorios/timeline-card';
import { ThresholdCard } from '@/components/relatorios/threshold-card';
import { ConvergenceCard } from '@/components/relatorios/convergence-card';
import { MessageVariantsCard } from '@/components/relatorios/message-variants-card';
import { IntelligenceSection } from '@/components/relatorios/intelligence-section';
import { ReportControls, downloadBlob } from '@/components/relatorios/report-controls';
import { SavedViewBar } from '@/components/relatorios/saved-view-bar';
import { SalesRoleBadge } from '@/components/sales/sales-role-badge';
import { Reveal } from '@/components/ui/motion';
import { toast } from 'sonner';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Tente novamente mais tarde.';
}

export default function RelatoriosPage() {
  const { data: membership, isLoading: loadingMembership } = useOrgMembership();
  const { filters, setFilter, updateFilters, clearFilters, hasFilters } = useCommercialFilters();

  const canView = membership?.membership?.role === 'OWNER' || membership?.membership?.role === 'ADMIN' ||
    membership?.membership?.sales_role === 'ANALYST' || membership?.membership?.sales_role === 'MANAGER';
  const canShareViews = membership?.membership?.role === 'OWNER' || membership?.membership?.role === 'ADMIN' || membership?.membership?.sales_role === 'MANAGER';

  const overviewQ = useAnalyticsOverview(filters);
  const funnelQ = useAnalyticsFunnel(filters);
  const consultantsQ = useAnalyticsConsultants(filters);
  const rankingQ = useAnalyticsRanking(filters);
  const geoQ = useAnalyticsGeo(filters);
  const campaignsQ = useAnalyticsCampaigns(filters);
  const timelineQ = useAnalyticsTimeline(filters);
  const forecastQ = useAnalyticsForecast(filters);
  const metricsQ = useScoreFeedbackMetrics();
  const exportPdf = useExportAnalyticsPdf();

  const primaryQueries = [overviewQ, funnelQ, consultantsQ, rankingQ, geoQ, campaignsQ, timelineQ, forecastQ];
  const hasViewData = primaryQueries.some((query) => !!query.data);
  const hasViewError = primaryQueries.some((query) => query.isError);
  const isPartial = hasViewData && hasViewError;
  const period = { from: filters.from, to: filters.to };

  const toggleArrayFilter = (key: 'status' | 'score_bucket' | 'negotiation_stage', value: string) => {
    const current = filters[key] ?? [];
    setFilter(key, current.includes(value) ? current.filter((item) => item !== value) || undefined : [...current, value]);
  };

  const handleExport = async () => {
    try {
      const blob = await exportPdf.mutateAsync(filters);
      const f = filters.from || 'inicio';
      const t = filters.to || 'hoje';
      downloadBlob(blob, `relatorio-prospeccao-${f}-${t}.pdf`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Falha ao gerar o PDF. O runtime de renderização pode estar indisponível no servidor.';
      toast.error(msg);
    }
  };

  if (loadingMembership) {
    return <div className="flex items-center justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>;
  }

  if (!canView) {
    return (
      <div className="mx-auto max-w-xl pt-12"><Card className="border-destructive/20 bg-destructive/5"><CardContent className="flex flex-col items-center gap-3 py-12 text-center"><ShieldAlert className="h-10 w-10 text-destructive" /><h1 className="text-lg font-semibold">Acesso restrito</h1><p className="max-w-sm text-sm text-muted-foreground">Relatórios estão disponíveis apenas para analistas, gestores e administradores da organização.</p><SalesRoleBadge role={membership?.membership?.sales_role} /></CardContent></Card></div>
    );
  }

  return (
    <div className="space-y-6" data-tour="relatorios-conteudo">
      <div data-tour="relatorios-header"><PageHeader eyebrow="Relatórios" title="Relatórios de Vendas" description={`Resumo de vendas e atendimentos da sua equipe · ${membership?.organization?.name || 'sua organização'}`} /></div>

      <div data-tour="relatorios-controles">
        <ReportControls period={period} filters={filters} onChange={(nextPeriod) => updateFilters(nextPeriod)} onFilterChange={setFilter} onClear={clearFilters} hasFilters={hasFilters} onExport={handleExport} exporting={exportPdf.isPending} campaigns={campaignsQ.data?.campaigns ?? []} consultants={consultantsQ.data?.consultants ?? []} />
      </div>

      <SavedViewBar filters={filters} onApply={updateFilters} canShare={!!canShareViews} />

      <div className="rounded-lg border bg-muted/25 px-3 py-2 text-xs text-muted-foreground" role="note">
        Os gráficos e listas destacados são interativos: clique em uma etapa, faixa, campanha ou consultor para filtrar todas as visões ao mesmo tempo. Os filtros ficam na URL e podem ser compartilhados.
      </div>

      {isPartial ? <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200" role="status">Algumas visões não puderam ser atualizadas; os dados válidos continuam visíveis.</div> : null}

      <section aria-label="Indicadores executivos">{overviewQ.isLoading ? <ExecutiveKpisSkeleton /> : overviewQ.isError ? <ChartCardError title="Indicadores indisponíveis" message={errorMessage(overviewQ.error)} /> : overviewQ.data ? <Reveal><ExecutiveKpis overview={overviewQ.data} /></Reveal> : null}</section>
      <section aria-label="Previsão de vendas">{forecastQ.isLoading ? <ChartCardSkeleton lines={4} /> : forecastQ.isError ? <ChartCardError title="Previsão indisponível" message={errorMessage(forecastQ.error)} /> : forecastQ.data ? <Reveal delay={70}><ForecastCard forecast={forecastQ.data} /></Reveal> : null}</section>
      <Reveal delay={90}><IntelligenceSection period={period} /></Reveal>
      {metricsQ.data && metricsQ.data.total_feedbacks > 0 ? <Reveal delay={100}><ConvergenceCard metrics={metricsQ.data} /></Reveal> : null}
      <section aria-label="Funil ponta a ponta">{funnelQ.isLoading ? <FunnelEndToEndSkeleton /> : funnelQ.isError ? <ChartCardError title="Funil indisponível" message={errorMessage(funnelQ.error)} /> : funnelQ.data ? <Reveal delay={140}><FunnelEndToEndCard funnel={funnelQ.data} /></Reveal> : null}</section>
      <Reveal delay={210}><div className="grid gap-6 lg:grid-cols-2"><ThresholdCard period={period} /><MessageVariantsCard period={period} /></div></Reveal>

      <Reveal delay={280}>
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            {overviewQ.data ? <FunnelCard overview={overviewQ.data} activeStatus={filters.status} onStatusFilter={(value) => toggleArrayFilter('status', value)} /> : overviewQ.isLoading ? <ChartCardSkeleton lines={6} /> : overviewQ.isError ? <ChartCardError title="Funil indisponível" message={errorMessage(overviewQ.error)} /> : null}
            {geoQ.isLoading ? <GeoCardSkeleton /> : geoQ.isError ? <ChartCardError title="Mapa indisponível" message={errorMessage(geoQ.error)} /> : geoQ.data ? <GeoCard states={geoQ.data.states} /> : null}
            {timelineQ.isLoading ? <TimelineSkeleton /> : timelineQ.isError ? <ChartCardError title="Linha do tempo indisponível" message={errorMessage(timelineQ.error)} /> : timelineQ.data ? <TimelineCard timeline={timelineQ.data.timeline} /> : null}
          </div>
          <div className="space-y-6">
            {overviewQ.data ? <><RatesCard overview={overviewQ.data} /><ScoreBandsCard overview={overviewQ.data} activeBuckets={filters.score_bucket} onBucketFilter={(value) => toggleArrayFilter('score_bucket', value)} /><NegotiationCard overview={overviewQ.data} activeStages={filters.negotiation_stage} onStageFilter={(value) => toggleArrayFilter('negotiation_stage', value)} /></> : null}
            {consultantsQ.isLoading ? <ListCardSkeleton /> : consultantsQ.isError ? <ChartCardError title="Consultores indisponíveis" message={errorMessage(consultantsQ.error)} /> : consultantsQ.data ? <ConsultantsCard consultants={consultantsQ.data.consultants} activeConsultantId={filters.consultant_id} onConsultantFilter={(id) => setFilter('consultant_id', filters.consultant_id === id ? undefined : id)} /> : null}
          </div>
        </div>
      </Reveal>

      <Reveal delay={350}><div className="grid gap-6 lg:grid-cols-2">{campaignsQ.isLoading ? <ListCardSkeleton /> : campaignsQ.isError ? <ChartCardError title="Campanhas indisponíveis" message={errorMessage(campaignsQ.error)} /> : campaignsQ.data ? <CampaignsCard campaigns={campaignsQ.data.campaigns} activeCampaignId={filters.campaign_id} onCampaignFilter={(id) => setFilter('campaign_id', filters.campaign_id === id ? undefined : id)} /> : null}{rankingQ.isLoading ? <ListCardSkeleton /> : rankingQ.isError ? <ChartCardError title="Melhores oportunidades indisponíveis" message={errorMessage(rankingQ.error)} /> : rankingQ.data ? <TopLeadsCard leads={rankingQ.data.items} /> : null}</div></Reveal>
    </div>
  );
}
