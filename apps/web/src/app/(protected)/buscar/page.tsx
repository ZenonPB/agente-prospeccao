import { PageHeader } from '@/components/ui/page-header';
import { SearchWorkspace } from '@/components/search/search-workspace';

export default function BuscarPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Prospecção"
        title="Pesquisar empresas e pessoas"
        description="Encontre empresas e contatos que já estão cadastrados no sistema. Use filtros ou descreva em uma frase quem você procura."
      />
      <SearchWorkspace />
    </div>
  );
}
