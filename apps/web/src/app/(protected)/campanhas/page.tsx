import { CampaignList } from '@/components/campanhas/campaign-list';
import { PageHeader } from '@/components/ui/page-header';

export default function CampanhasPage() {
  return (
    <div className="space-y-6">
      <div data-tour="campanhas-header">
        <PageHeader
          eyebrow="Operação"
          title="Campanhas"
          description="Crie buscas de prospecção e colete oportunidades automaticamente"
        />
      </div>

      <CampaignList />
    </div>
  );
}