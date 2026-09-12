import { IntegrationsWorkspace } from '@/components/commercial-platform/integrations-workspace';
import { PageHeader } from '@/components/ui/page-header';

export default function IntegracoesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Gestão"
        title="Integrações comerciais"
        description="Conecte o sistema usado pela equipe para manter empresas, contatos e oportunidades alinhados com segurança."
      />
      <IntegrationsWorkspace />
    </div>
  );
}
