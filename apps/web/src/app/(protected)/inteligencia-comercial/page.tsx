import { CommercialIntelligenceDashboard } from '@/components/commercial-platform/commercial-intelligence-dashboard';
import { LearningCoachingPanel } from '@/components/commercial-platform/learning-coaching-panel';
import { PageHeader } from '@/components/ui/page-header';

export default function InteligenciaComercialPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inteligência"
        title="O que está funcionando nas vendas"
        description="Entenda quais sinais, fontes e segmentos geram avanço comercial, calibre ofertas com replay histórico e acompanhe coaching baseado em evidência sem transformar correlação em causalidade."
      />
      <CommercialIntelligenceDashboard />
      <LearningCoachingPanel />
    </div>
  );
}
