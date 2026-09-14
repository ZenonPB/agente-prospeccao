import { LeadList } from '@/components/oportunidades/lead-list';
import { PageHeader } from '@/components/ui/page-header';

export default function OportunidadesPage() {
  return (
    <div className="space-y-6">
      <div data-tour="oportunidades-header">
        <PageHeader
          eyebrow="Operação"
          title="Oportunidades"
          description="Empresas que passaram pela análise do sistema e parecem valer uma abordagem. Revise os motivos antes de entrar em contato."
        />
      </div>

      <LeadList />
    </div>
  );
}