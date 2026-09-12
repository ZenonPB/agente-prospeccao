import { EngagementWorkspace } from '@/components/engagement/engagement-workspace';
import { PageHeader } from '@/components/ui/page-header';

export default function SequencesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Engagement"
        title="Sequências e workflows"
        description="Organize abordagens, tarefas e automações comerciais com rastreabilidade, pausas seguras e controle humano sobre ações externas."
      />
      <EngagementWorkspace />
    </div>
  );
}
