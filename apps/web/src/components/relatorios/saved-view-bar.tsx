'use client';

import { useState } from 'react';
import { Bookmark, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useCreateSavedCommercialView, useDeleteSavedCommercialView, useSavedCommercialViews } from '@/hooks/use-sales-operating';
import type { CommercialFilterSnapshot } from '@/lib/api';

export function SavedViewBar({
  filters,
  onApply,
  canShare,
}: {
  filters: CommercialFilterSnapshot;
  onApply: (filters: CommercialFilterSnapshot) => void;
  canShare: boolean;
}) {
  const views = useSavedCommercialViews('analytics');
  const create = useCreateSavedCommercialView('analytics');
  const remove = useDeleteSavedCommercialView('analytics');
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [shared, setShared] = useState(false);

  const save = async () => {
    const cleaned = name.trim();
    if (cleaned.length < 2) {
      toast.error('Dê um nome com pelo menos 2 caracteres.');
      return;
    }
    try {
      await create.mutateAsync({ name: cleaned, view_kind: 'analytics', filters, shared: canShare && shared });
      setName('');
      setShared(false);
      setCreating(false);
      toast.success('Visão salva.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível salvar a visão.');
    }
  };

  return (
    <div className="rounded-xl border bg-card p-3" aria-label="Visões salvas">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 text-sm font-medium"><Bookmark className="h-4 w-4" aria-hidden="true" />Visões salvas</span>
        {views.isLoading ? <span className="text-xs text-muted-foreground">Carregando...</span> : null}
        {views.data?.items.map((view) => (
          <span key={view.id} className="inline-flex items-center overflow-hidden rounded-full border bg-background">
            <button type="button" onClick={() => onApply(view.filters)} className="px-3 py-1.5 text-xs hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" title={view.shared ? 'Compartilhada com o workspace' : 'Somente você'}>
              {view.name}{view.shared ? ' · equipe' : ''}
            </button>
            {view.editable ? (
              <button type="button" aria-label={`Excluir visão ${view.name}`} onClick={() => remove.mutate(view.id)} className="border-l px-2 py-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            ) : null}
          </span>
        ))}
        <Button type="button" size="sm" variant="outline" onClick={() => setCreating((value) => !value)}><Plus className="mr-1.5 h-4 w-4" />Salvar filtros atuais</Button>
      </div>

      {creating ? (
        <div className="mt-3 flex flex-col gap-2 rounded-lg bg-muted/30 p-3 sm:flex-row sm:items-center">
          <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Ex.: Troféus MEJ — último trimestre" maxLength={120} aria-label="Nome da visão" />
          {canShare ? (
            <label className="flex shrink-0 items-center gap-2 text-sm"><input type="checkbox" checked={shared} onChange={(event) => setShared(event.target.checked)} />Compartilhar com a equipe</label>
          ) : null}
          <div className="flex shrink-0 gap-2"><Button type="button" size="sm" onClick={() => void save()} disabled={create.isPending}>Salvar</Button><Button type="button" size="sm" variant="ghost" onClick={() => setCreating(false)}>Cancelar</Button></div>
        </div>
      ) : null}
    </div>
  );
}
