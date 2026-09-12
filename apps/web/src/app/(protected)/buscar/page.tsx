import { PageHeader } from '@/components/ui/page-header';
import { SearchWorkspace } from '@/components/search/search-workspace';

export default function BuscarPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Prospecção"
        title="Buscar empresas e pessoas"
        description="Explore a base do seu workspace com filtros avançados ou descreva o perfil ideal em linguagem natural."
      />
      <SearchWorkspace />
    </div>
  );
}
