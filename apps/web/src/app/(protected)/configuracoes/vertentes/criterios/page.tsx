'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Copy, Pencil, Search, SlidersHorizontal } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import { TemplateEditor } from '@/components/vertentes/template-editor';
import {
  useCreateScoringTemplate,
  useOrgMembership,
  useScoringTemplates,
} from '@/hooks/use-api';
import type { ScoringTemplate } from '@/lib/api';

export default function CriteriosVertentesPage() {
  const { data, isLoading } = useScoringTemplates({ scope: 'all', include_inactive: true });
  const { data: membership, isLoading: loadingMembership } = useOrgMembership();
  const create = useCreateScoringTemplate();
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<ScoringTemplate | null>(null);
  const [editing, setEditing] = useState(false);

  const role = membership?.membership?.role;
  const canManage = role === 'OWNER' || role === 'ADMIN' || membership?.membership?.sales_role === 'MANAGER';
  const templates = useMemo(() => data?.templates ?? [], [data]);
  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('pt-BR');
    if (!query) return templates;
    return templates.filter((item) => item.service_label.toLocaleLowerCase('pt-BR').includes(query));
  }, [search, templates]);

  const duplicate = async (template: ScoringTemplate) => {
    try {
      const copy = await create.mutateAsync({
        service_label: `${template.service_label} (personalizada)`,
        source_template_id: template.id,
      });
      setSelected(copy);
      setEditing(true);
      toast.success('Critérios copiados para a sua organização.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível copiar os critérios.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3">
        <Link
          href="/configuracoes/vertentes"
          aria-label="Voltar para Vertentes"
          className="mt-1 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        </Link>
        <PageHeader
          eyebrow="Configuração avançada"
          title="Critérios de avaliação personalizados"
          description="A Vertente continua sendo a estratégia principal. Aqui ficam apenas critérios de scoring personalizados que ainda usam o contrato de compatibilidade existente."
        />
      </div>

      <Card className="border-dashed">
        <CardContent className="flex gap-3 p-4 text-sm">
          <SlidersHorizontal className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div>
            <p className="font-medium">Esta área não cria uma segunda Vertente.</p>
            <p className="mt-1 text-muted-foreground">
              ICP, discovery, pré-scoring, enrichment, timing, decisores e abordagem vêm do OfferProfile efetivo. Estes templates continuam disponíveis somente para preservar personalizações detalhadas da etapa de avaliação durante a migração.
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar critérios..." className="pl-9" />
      </div>

      {isLoading || loadingMembership ? (
        <div className="space-y-3">{[1, 2, 3].map((item) => <Skeleton key={item} className="h-24 w-full" />)}</div>
      ) : filtered.length === 0 ? (
        <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">Nenhum conjunto de critérios encontrado.</CardContent></Card>
      ) : (
        <div className="space-y-3">
          {filtered.map((template) => {
            const factory = !template.organization_id;
            const criteriaCount = (template.positive_signals?.length ?? 0) + (template.negative_signals?.length ?? 0) + (template.context_signals?.length ?? 0);
            return (
              <Card key={template.id}>
                <CardHeader className="pb-2">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <CardTitle className="text-base">{template.service_label}</CardTitle>
                        <Badge variant="outline">{factory ? 'Padrão de fábrica' : 'Da sua organização'}</Badge>
                        {!template.is_active ? <Badge variant="secondary">Inativo</Badge> : null}
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">{criteriaCount} {criteriaCount === 1 ? 'critério configurado' : 'critérios configurados'}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" size="sm" onClick={() => { setSelected(template); setEditing(false); }}>Ver critérios</Button>
                      {canManage && factory ? (
                        <Button size="sm" variant="outline" onClick={() => void duplicate(template)} disabled={create.isPending}>
                          <Copy className="mr-2 h-3.5 w-3.5" />Copiar e personalizar
                        </Button>
                      ) : null}
                      {canManage && !factory ? (
                        <Button size="sm" onClick={() => { setSelected(template); setEditing(true); }}>
                          <Pencil className="mr-2 h-3.5 w-3.5" />Editar critérios
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </CardHeader>
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={Boolean(selected)} onOpenChange={(open) => { if (!open) { setSelected(null); setEditing(false); } }}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{selected?.service_label}</DialogTitle>
            <DialogDescription>
              {editing ? 'Edite somente os critérios desta etapa de avaliação.' : 'Visualização dos critérios de scoring deste template.'}
            </DialogDescription>
          </DialogHeader>
          {selected ? (
            <TemplateEditor
              template={selected}
              canEdit={editing && canManage && Boolean(selected.organization_id)}
              showLabel={editing}
              onSaved={(saved) => { setSelected(saved); setEditing(false); }}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
