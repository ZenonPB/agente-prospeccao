'use client';

import { useState } from 'react';
import { ShieldAlert, Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/page-header';
import { useOrgMembership } from '@/hooks/use-api';
import { useAnalyticsOverview, useAnalyticsFunnel, useAnalyticsConsultants, useAnalyticsRanking, useAnalyticsGeo, useAnalyticsCampaigns, useAnalyticsTimeline, useAnalyticsForecast, useExportAnalyticsPdf, type AnalyticsPeriod } from '@/hooks/use-api';
import { ExecutiveKpis, ExecutiveKpisSkeleton } from '@/components/relatorios/executive-kpis';
import { FunnelCard, RatesCard, ScoreBandsCard, NegotiationCard, ChartCardSkeleton, ChartCardError } from '@/components/relatorios/chart-cards';
import { FunnelEndToEndCard, FunnelEndToEndSkeleton } from '@/components/relatorios/funnel-e2e-card';
import { ForecastCard } from '@/components/relatorios/forecast-card';
import { ConsultantsCard, CampaignsCard, TopLeadsCard, ListCardSkeleton } from '@/components/relatorios/list-cards';
import { GeoCard, GeoCardSkeleton } from '@/components/relatorios/brazil-state-map';
import { TimelineCard, TimelineSkeleton } from '@/components/relatorios/timeline-card';
import { ThresholdCard } from '@/components/relatorios/threshold-card';
import { MessageVariantsCard } from '@/components/relatorios/message-variants-card';
import { ReportControls, downloadBlob } from '@/components/relatorios/report-controls';
import { SalesRoleBadge } from '@/components/sales/sales-role-badge';
import { toast } from 'sonner';

export default function RelatoriosPage() {
  const { data: membership, isLoading: loadingMembership } = useOrgMembership();
  const [period, setPeriod] = useState<AnalyticsPeriod>({});

  const canView = membership?.membership?.role === 'OWNER' || membership?.membership?.role === 'ADMIN' ||
    membership?.membership?.sales_role === 'ANALYST' || membership?.membership?.sales_role === 'MANAGER';

  const overviewQ = useAnalyticsOverview(period);
  const funnelQ = useAnalyticsFunnel(period);
  const consultantsQ = useAnalyticsConsultants(period);
  const rankingQ = useAnalyticsRanking(period);
  const geoQ = useAnalyticsGeo(period);
  const campaignsQ = useAnalyticsCampaigns(period);
  const timelineQ = useAnalyticsTimeline(period);
  const forecastQ = useAnalyticsForecast(period);
  const exportPdf = useExportAnalyticsPdf();

  const anyLoading = [overviewQ, funnelQ, consultantsQ, rankingQ, geoQ, campaignsQ, timelineQ, forecastQ].some((q) => q.isLoading);
  const anyError = [overviewQ, funnelQ, consultantsQ, rankingQ, geoQ, campaignsQ, timelineQ, forecastQ].some((q) => q.isError);
  const errMsg = [overviewQ, funnelQ, consultantsQ, rankingQ, geoQ, campaignsQ, timelineQ, forecastQ].find((q) => q.error)?.error;

  const handleExport = async () => {
    try {
      const blob = await exportPdf.mutateAsync(period);
      const f = period.from || 'inicio';
      const t = period.to || 'hoje';
      downloadBlob(blob, `relatorio-prospeccao-${f}-${t}.pdf`);
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Falha ao gerar o PDF. O runtime de renderização pode estar indisponível no servidor.';
      toast.error(msg);
    }
  };

  if (loadingMembership) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!canView) {
    return (
      <div className="mx-auto max-w-xl pt-12">
        <Card className="border-destructive/20 bg-destructive/5">
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <ShieldAlert className="h-10 w-10 text-destructive" />
            <h1 className="text-lg font-semibold">Acesso restrito</h1>
            <p className="max-w-sm text-sm text-muted-foreground">
              Relatórios estão disponíveis apenas para analistas, gestores e administradores da organização.
            </p>
            <SalesRoleBadge role={membership?.membership?.sales_role} />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Relatórios"
        title="Relatórios de Vendas"
        description={`Resumo de vendas e atendimentos da sua equipe · ${membership?.organization?.name || 'sua organização'}`}
      />

      <ReportControls
        period={period}
        onChange={setPeriod}
        onExport={handleExport}
        exporting={exportPdf.isPending}
      />

      {anyLoading ? (
        <ReportSkeleton />
      ) : anyError ? (
        <ChartCardError title="Não foi possível carregar os relatórios" message={errMsg instanceof Error ? errMsg.message : 'Tente novamente mais tarde'} />
      ) : (
        <>
          {overviewQ.data && <ExecutiveKpis overview={overviewQ.data} />}
          {forecastQ.data && <ForecastCard forecast={forecastQ.data} />}
          {funnelQ.data && <FunnelEndToEndCard funnel={funnelQ.data} />}
          {canView && (
            <div className="grid gap-6 lg:grid-cols-2">
              <ThresholdCard period={period} />
              <MessageVariantsCard period={period} />
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-6">
              {overviewQ.data && <FunnelCard overview={overviewQ.data} />}
              {geoQ.data && <GeoCard states={geoQ.data.states} />}
              {timelineQ.data && <TimelineCard timeline={timelineQ.data.timeline} />}
            </div>
            <div className="space-y-6">
              {overviewQ.data && (
                <>
                  <RatesCard overview={overviewQ.data} />
                  <ScoreBandsCard overview={overviewQ.data} />
                  <NegotiationCard overview={overviewQ.data} />
                </>
              )}
              {consultantsQ.data && <ConsultantsCard consultants={consultantsQ.data.consultants} />}
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {campaignsQ.data && <CampaignsCard campaigns={campaignsQ.data.campaigns} />}
            {rankingQ.data && <TopLeadsCard leads={rankingQ.data.items} />}
          </div>
        </>
      )}
    </div>
  );
}

function ReportSkeleton() {
  return (
    <div className="space-y-6">
      <ExecutiveKpisSkeleton />
      <FunnelEndToEndSkeleton />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <ChartCardSkeleton lines={6} />
          <GeoCardSkeleton />
          <TimelineSkeleton />
        </div>
        <div className="space-y-6">
          <ChartCardSkeleton lines={3} />
          <ChartCardSkeleton lines={4} />
          <ListCardSkeleton />
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <ListCardSkeleton />
        <ListCardSkeleton />
      </div>
    </div>
  );
}
