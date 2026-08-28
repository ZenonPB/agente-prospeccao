'use client';

import { KanbanBoard } from '@/components/vendas/kanban-board';
import { PageHeader } from '@/components/ui/page-header';
import { Reveal } from '@/components/ui/motion';

export default function VendasPage() {
  return (
    <div className="space-y-6">
      <div data-tour="vendas-header">
        <PageHeader
          eyebrow="Operação"
          title="Negociações"
          description="Acompanhe e gerencie suas conversas com os leads"
        />
      </div>

      <div data-tour="vendas-kanban">
        <Reveal delay={80}>
          <KanbanBoard />
        </Reveal>
      </div>
    </div>
  );
}