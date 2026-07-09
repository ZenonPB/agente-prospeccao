import { KanbanBoard } from '@/components/vendas/kanban-board';

export default function VendasPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Negociações</h2>
        <p className="text-muted-foreground">
          Acompanhe e gerencie suas conversas com empresas
        </p>
      </div>

      <KanbanBoard />
    </div>
  );
}