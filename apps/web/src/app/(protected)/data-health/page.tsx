import { DataHealthDashboard } from '@/components/data-health/data-health-dashboard';
import { PageHeader } from '@/components/ui/page-header';

export default function DataHealthPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inteligência comercial"
        title="Qualidade dos dados"
        description="Identifique informações desatualizadas, incompletas ou pouco confiáveis antes de abordar uma oportunidade."
      />
      <DataHealthDashboard />
    </div>
  );
}
