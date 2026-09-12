import { CommercialIntelligenceDashboard } from '@/components/commercial-platform/commercial-intelligence-dashboard';
import { PageHeader } from '@/components/ui/page-header';

export default function InteligenciaComercialPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inteligência"
        title="O que está funcionando nas vendas"
        description="Entenda quais sinais, fontes e segmentos realmente geram respostas, reuniões e vendas sem confundir correlação com resultado não atribuído."
      />
      <CommercialIntelligenceDashboard />
    </div>
  );
}
