'use client';

import { useState } from 'react';
import { ProcessBanner } from '@/components/dashboard/process-banner';
import { MetricsGrid } from '@/components/dashboard/metrics';
import { FunnelChart } from '@/components/dashboard/funnel-chart';
import { ActivityTimeline } from '@/components/dashboard/activity-timeline';
import { QuickActions } from '@/components/dashboard/quick-actions';
import { ActiveCampaigns } from '@/components/dashboard/active-campaigns';
import { TodayActions } from '@/components/dashboard/today-actions';
import { PageHeader } from '@/components/ui/page-header';

export default function DashboardPage() {
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <div data-tour="dashboard-header">
        <PageHeader
          eyebrow="Visão Geral"
          title="Seu radar comercial"
          description="Acompanhe os resultados da sua prospecção em um só lugar"
        />
      </div>

      {/* Process Banner */}
      <ProcessBanner />

      {/* Metrics */}
      <div data-tour="dashboard-metrics">
        <MetricsGrid onFilter={setActiveFilter} activeFilter={activeFilter} />
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column - Charts */}
        <div className="lg:col-span-2 space-y-6">
          <div data-tour="dashboard-funnel">
            <FunnelChart onFilter={setActiveFilter} activeFilter={activeFilter} />
          </div>
          <div data-tour="dashboard-campanhas">
            <ActiveCampaigns />
          </div>
        </div>

        {/* Right Column - Activity & Actions */}
        <div className="space-y-6">
          <div data-tour="dashboard-hoje">
            <TodayActions />
          </div>
          <QuickActions />
          <div data-tour="dashboard-timeline">
            <ActivityTimeline />
          </div>
        </div>
      </div>
    </div>
  );
}