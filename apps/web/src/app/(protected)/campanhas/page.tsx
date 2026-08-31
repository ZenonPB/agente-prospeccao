import { CampaignList } from '@/components/campanhas/campaign-list';
import { CrmPasteModal } from '@/components/campanhas/leads-paste-modal';
import { PageHeader } from '@/components/ui/page-header';

export default function CampanhasPage() {
  return (
    <div className="space-y-6">
      <div data-tour="campanhas-header">
        <PageHeader
          eyebrow="Operação"
          title="Campanhas"
          description="Crie buscas de prospecção e colete oportunidades automaticamente"
          actions={<CrmPasteModal />}
        />
      </div>

      <CampaignList />
    </div>
  );
}