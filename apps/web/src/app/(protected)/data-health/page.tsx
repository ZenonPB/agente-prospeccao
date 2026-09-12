import { DataHealthDashboard } from '@/components/data-health/data-health-dashboard';
import { PageHeader } from '@/components/ui/page-header';

export default function DataHealthPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Qualidade dos dados"
        title="Data Health"
        description="Veja quais informações estão vencidas, incompletas ou pouco confiáveis antes de abordar um lead."
      />
      <DataHealthDashboard />
    </div>
  );
}
