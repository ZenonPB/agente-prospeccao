import { CommercialIntelligenceDashboard } from '@/components/commercial-platform/commercial-intelligence-dashboard';
import { LearningCoachingPanel } from '@/components/commercial-platform/learning-coaching-panel';
import { PageHeader } from '@/components/ui/page-header';

export default function InteligenciaComercialPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inteligência"
        title="O que está funcionando nas vendas"
        description="Descubra quais tipos de empresa, abordagens e sinais têm gerado melhores resultados e use esses dados para melhorar as próximas prospecções."
      />
      <CommercialIntelligenceDashboard />
      <LearningCoachingPanel />
    </div>
  );
}
