import { ProspectingRadar } from '@/components/monitoring/prospecting-radar';
import { PageHeader } from '@/components/ui/page-header';

export default function MonitoringPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inteligência contínua"
        title="Monitorar oportunidades"
        description="Acompanhe buscas importantes e veja quando surgirem novas empresas ou sinais que mereçam atenção."
      />
      <ProspectingRadar />
    </div>
  );
}
