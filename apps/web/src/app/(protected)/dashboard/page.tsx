'use client';

import { useState } from 'react';
import { MetricsGrid } from '@/components/dashboard/metrics';
import { FunnelChart } from '@/components/dashboard/funnel-chart';
import { ActivityTimeline } from '@/components/dashboard/activity-timeline';
import { QuickActions } from '@/components/dashboard/quick-actions';
import { ActiveCampaigns } from '@/components/dashboard/active-campaigns';

export default function DashboardPage() {
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Visão Geral</h2>
        <p className="text-muted-foreground">
          Acompanhe os resultados da sua prospecção
        </p>
      </div>

      {/* Metrics */}
      <MetricsGrid onFilter={setActiveFilter} activeFilter={activeFilter} />

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column - Charts */}
        <div className="lg:col-span-2 space-y-6">
          <FunnelChart onFilter={setActiveFilter} activeFilter={activeFilter} />
          <ActiveCampaigns />
        </div>

        {/* Right Column - Activity & Actions */}
        <div className="space-y-6">
          <QuickActions />
          <ActivityTimeline />
        </div>
      </div>
    </div>
  );
}