'use client';

import { KanbanBoard } from '@/components/vendas/kanban-board';
import { PageHeader } from '@/components/ui/page-header';

export default function VendasPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operação"
        title="Negociações"
        description="Acompanhe e gerencie suas conversas com os leads"
      />

      <div data-tour="vendas-kanban">
        <KanbanBoard />
      </div>
    </div>
  );
}