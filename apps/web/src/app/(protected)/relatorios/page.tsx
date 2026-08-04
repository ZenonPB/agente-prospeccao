'use client';

import { useState } from 'react';
import { ShieldAlert, Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/page-header';
import { useOrgMembership } from '@/hooks/use-api';
import { useAnalyticsOverview, useAnalyticsConsultants, useAnalyticsRanking, useAnalyticsGeo, useAnalyticsCampaigns, useAnalyticsTimeline, useExportAnalyticsPdf, type AnalyticsPeriod } from '@/hooks/use-api';
import { ExecutiveKpis, ExecutiveKpisSkeleton } from '@/components/relatorios/executive-kpis';
import { FunnelCard, RatesCard, ScoreBandsCard, ChartCardSkeleton, ChartCardError } from '@/components/relatorios/chart-cards';
import { ConsultantsCard, CampaignsCard, TopLeadsCard, ListCardSkeleton } from '@/components/relatorios/list-cards';
import { GeoCard, GeoCardSkeleton } from '@/components/relatorios/brazil-state-map';
import { TimelineCard, TimelineSkeleton } from '@/components/relatorios/timeline-card';
import { ReportControls, downloadBlob } from '@/components/relatorios/report-controls';
import { SalesRoleBadge } from '@/components/sales/sales-role-badge';

export default function RelatoriosPage() {
  const { data: membership, isLoading: loadingMembership } = useOrgMembership();
  const [period, setPeriod] = useState<AnalyticsPeriod>({});

  const canView = membership?.membership?.role === 'OWNER' || membership?.membership?.role === 'ADMIN' ||
    membership?.membership?.sales_role === 'ANALYST' || membership?.membership?.sales_role === 'MANAGER';

  const overviewQ = useAnalyticsOverview(period);
  const consultantsQ = useAnalyticsConsultants(period);
  const rankingQ = useAnalyticsRanking(period);
  const geoQ = useAnalyticsGeo(period);
  const campaignsQ = useAnalyticsCampaigns(period);
  const timelineQ = useAnalyticsTimeline(period);
  const exportPdf = useExportAnalyticsPdf();

  const anyLoading = [overviewQ, consultantsQ, rankingQ, geoQ, campaignsQ, timelineQ].some((q) => q.isLoading);
  const anyError = [overviewQ, consultantsQ, rankingQ, geoQ, campaignsQ, timelineQ].some((q) => q.isError);
  const errMsg = [overviewQ, consultantsQ, rankingQ, geoQ, campaignsQ, timelineQ].find((q) => q.error)?.error;

  const handleExport = async () => {
    try {
      const blob = await exportPdf.mutateAsync(period);
      const f = period.from || 'inicio';
      const t = period.to || 'hoje';
      downloadBlob(blob, `relatorio-prospeccao-${f}-${t}.pdf`);
    } catch (err) {
      console.error(err);
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
        eyebrow="Inteligência"
        title="Relatórios"
        description={`Visão executiva da operação · ${membership?.organization?.name || 'sua organização'}`}
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
