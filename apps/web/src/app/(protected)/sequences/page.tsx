import { EngagementWorkspace } from '@/components/engagement/engagement-workspace';
import { PageHeader } from '@/components/ui/page-header';

export default function SequencesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operação"
        title="Próximos contatos"
        description="Organize quem precisa ser contatado, quando fazer o próximo contato e quais tarefas ainda precisam ser concluídas."
      />
      <EngagementWorkspace />
    </div>
  );
}
