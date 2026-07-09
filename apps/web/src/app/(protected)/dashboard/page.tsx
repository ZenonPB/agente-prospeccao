import { MetricsGrid } from '@/components/dashboard/metrics';
import { FunnelChart } from '@/components/dashboard/funnel-chart';
import { ActivityTimeline } from '@/components/dashboard/activity-timeline';
import { QuickActions } from '@/components/dashboard/quick-actions';
import { ActiveCampaigns } from '@/components/dashboard/active-campaigns';

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground">
          Visão geral da sua prospecção
        </p>
      </div>

      {/* Metrics */}
      <MetricsGrid />

      {/* Main Content Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* Left Column - Charts */}
        <div className="lg:col-span-2 space-y-6">
          <FunnelChart />
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