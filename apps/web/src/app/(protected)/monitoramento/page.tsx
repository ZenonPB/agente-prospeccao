import { ProspectingRadar } from '@/components/monitoring/prospecting-radar';
import { PageHeader } from '@/components/ui/page-header';

export default function MonitoringPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inteligência contínua"
        title="Radar comercial"
        description="Salve buscas, acompanhe novos resultados, identifique eventos recorrentes e organize oportunidades sem perder o controle sobre limites de uso e consultas externas."
      />
      <ProspectingRadar />
    </div>
  );
}
