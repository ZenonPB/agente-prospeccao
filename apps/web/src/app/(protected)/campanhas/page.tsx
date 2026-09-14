import { CampaignList } from '@/components/campanhas/campaign-list';
import { CrmPlanilhaModal } from '@/components/campanhas/crm-planilha-modal';
import { PageHeader } from '@/components/ui/page-header';

export default function CampanhasPage() {
  return (
    <div className="space-y-6">
      <div data-tour="campanhas-header">
        <PageHeader
          eyebrow="Prospecção"
          title="Encontrar novos clientes"
          description="Crie uma busca para encontrar empresas que combinam com o que sua equipe vende. O sistema pesquisa, analisa e organiza os melhores candidatos para revisão."
          actions={<CrmPlanilhaModal />}
        />
      </div>

      <CampaignList />
    </div>
  );
}