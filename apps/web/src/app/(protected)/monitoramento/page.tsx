import { ProspectingRadar } from '@/components/monitoring/prospecting-radar';
import { PageHeader } from '@/components/ui/page-header';

export default function MonitoringPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inteligência contínua"
        title="Radar comercial"
        description="Salve buscas, acompanhe novos matches, reconheça eventos recorrentes e veja o estado operacional dos leads sem perder controle sobre cotas e ações externas."
      />
      <ProspectingRadar />
    </div>
  );
}
