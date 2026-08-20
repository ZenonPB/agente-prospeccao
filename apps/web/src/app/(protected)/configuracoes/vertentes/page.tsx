'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { toast } from 'sonner';
import {
  Plus,
  Copy,
  Trash2,
  Pencil,
  Sparkles,
  Search,
  Loader2,
  Lock,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/components/ui/page-header';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  useScoringTemplates,
  useGenerateScoringTemplate,
  useCreateScoringTemplate,
  useDeleteScoringTemplate,
  usePatchScoringTemplate,
  useOrgMembership,
} from '@/hooks/use-api';
import { TemplateEditor, STEP_OPTIONS } from '@/components/vertentes/template-editor';
import type { ScoringTemplate } from '@/lib/api';
import type { EnrichmentStep } from '@/lib/api';

function statusBadges(t: ScoringTemplate) {
  const badges: ReactNode[] = [];
  if (!t.organization_id) {
    badges.push(
      <Badge key="global" variant="outline">
        De fábrica (todos os times)
      </Badge>,
    );
    return badges;
  }
  if (t.is_generated && !t.is_active) {
    badges.push(
      <Badge key="draft" className="bg-amber-100 text-amber-800 hover:bg-amber-100">
        <Sparkles className="mr-1 h-3 w-3" /> Rascunho
      </Badge>,
    );
  } else if (t.is_generated) {
    badges.push(
      <Badge key="gen" variant="outline" className="text-amber-700">
        <Sparkles className="mr-1 h-3 w-3" /> Gerada por IA
      </Badge>,
    );
  }
  if (!t.is_active) {
    badges.push(
      <Badge key="inactive" variant="secondary">
        Inativa
      </Badge>,
    );
  }
  return badges;
}

export default function VertentesPage() {
  const { data: memberships, isLoading: loadingMembership } = useOrgMembership();
  const { data, isLoading } = useScoringTemplates({ scope: 'all', include_inactive: true });

  const generate = useGenerateScoringTemplate();
  const create = useCreateScoringTemplate();
  const remove = useDeleteScoringTemplate();
  const patch = usePatchScoringTemplate();

  const [search, setSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [description, setDescription] = useState('');
  const [segment, setSegment] = useState('');
  const [generating, setGenerating] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [dupSource, setDupSource] = useState<ScoringTemplate | null>(null);
  const [dupLabel, setDupLabel] = useState('');
  const [deleting, setDeleting] = useState<ScoringTemplate | null>(null);

  const myRole = memberships?.membership?.role;
  const canManage =
    myRole === 'OWNER' || myRole === 'ADMIN' || memberships?.membership?.sales_role === 'MANAGER';

  const templates = useMemo(() => data?.templates ?? [], [data]);
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return templates;
    return templates.filter((t) => t.service_label.toLowerCase().includes(q));
  }, [templates, search]);

  const editing = editingId ? templates.find((t) => t.id === editingId) ?? null : null;

  const handleGenerate = () => {
    if (!description.trim()) return;
    setGenerating(true);
    generate.mutate(
      { service: description.trim(), ...(segment.trim() ? { segment: segment.trim() } : {}) },
      {
        onSuccess: (t) => {
          setCreateOpen(false);
          setDescription('');
          setSegment('');
          setEditingId(t.id);
          toast.success('Rascunho criado. Revise e ative quando estiver satisfeito.');
        },
        onError: (err) => {
          toast.error(err instanceof Error ? err.message : 'Não foi possível gerar a vertente.');
        },
        onSettled: () => setGenerating(false),
      },
    );
  };

  const openDuplicate = (t: ScoringTemplate) => {
    setDupSource(t);
    setDupLabel(`${t.service_label} (cópia)`);
  };

  const handleDuplicate = () => {
    if (!dupSource) return;
    create.mutate(
      { service_label: dupLabel, source_template_id: dupSource.id },
      {
        onSuccess: (t) => {
          setDupSource(null);
          setEditingId(t.id);
          toast.success('Vertente duplicada. Personalize os critérios para o seu ICP.');
        },
        onError: (err) => {
          toast.error(err instanceof Error ? err.message : 'Não foi possível duplicar a vertente.');
        },
      },
    );
  };

  const handleDelete = () => {
    if (!deleting) return;
    remove.mutate(deleting.id, {
      onSuccess: () => {
        if (editingId === deleting.id) setEditingId(null);
        setDeleting(null);
        toast.success('Vertente removida com sucesso.');
      },
      onError: (err) => {
        setDeleting(null);
        toast.error(err instanceof Error ? err.message : 'Não foi possível remover a vertente.');
      },
    });
  };

  const toggleActive = (t: ScoringTemplate, active: boolean) => {
    patch.mutate(
      { id: t.id, data: { is_active: active } },
      {
        onError: (err) => {
          toast.error(err instanceof Error ? err.message : 'Não foi possível atualizar o status.');
        },
      },
    );
  };

  const stepsLabel = (t: ScoringTemplate): string => {
    const steps: EnrichmentStep[] = t.enrichment_steps ?? [];
    if (steps.length === 0) return 'Análise padrão';
    return STEP_OPTIONS.filter((o) => steps.includes(o.key))
      .map((o) => o.label)
      .join(' · ');
  };

  return (
    <div className="space-y-6">
      <div data-tour="vertentes-header">
        <PageHeader
          eyebrow="Gestão"
          title="Vertentes"
          description="Perfis de empresa que a IA usa para avaliar e abordar os leads. Crie com a IA ou duplique uma vertente de fábrica como ponto de partida."
          actions={
            canManage ? (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="mr-2 h-4 w-4" /> Criar vertente
              </Button>
            ) : undefined
          }
        />
      </div>

      {!canManage && (
        <div className="flex items-start gap-2 rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
          <Lock className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            Aqui você pode consultar e usar as vertentes do time. Criar, editar,
            duplicar ou ativar vertentes é exclusivo de gestores e administradores.
          </p>
        </div>
      )}

      {createOpen && canManage && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="h-4 w-4 text-amber-600" />
              Criar vertente com a IA
              <Badge variant="outline" className="text-[10px] font-normal">
                rascunho — revise antes de ativar
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label>Descreva o que você vende e para quem</Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Ex.: vendo manutenção de compressores para indústrias de alimentos"
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label>Segmento (opcional)</Label>
              <Input
                value={segment}
                onChange={(e) => setSegment(e.target.value)}
                placeholder="Ex.: indústrias de alimentos"
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleGenerate} disabled={generating || !description.trim()}>
                {generating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Gerando...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" /> Gerar rascunho
                  </>
                )}
              </Button>
              <Button variant="ghost" onClick={() => setCreateOpen(false)}>
                Cancelar
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div data-tour="vertentes-busca" className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar vertente..."
          className="pl-9"
        />
      </div>

      {isLoading || loadingMembership ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {search
              ? 'Nenhuma vertente encontrada com essa busca.'
              : 'Nenhuma vertente disponível ainda.'}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {filtered.map((t) => (
            <Card key={t.id} className="p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    {canManage ? (
                      <Button
                        variant="link"
                        className="h-auto p-0 text-left font-semibold text-foreground"
                        onClick={() => setEditingId(t.id)}
                      >
                        {t.service_label}
                      </Button>
                    ) : (
                      <span className="font-semibold text-foreground">{t.service_label}</span>
                    )}
                    {statusBadges(t)}
                  </div>
                  <p className="text-xs text-muted-foreground">{stepsLabel(t)}</p>
                </div>

                <div className="flex shrink-0 items-center gap-1.5">
                  {canManage && t.organization_id ? (
                    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Switch
                        checked={t.is_active}
                        onCheckedChange={(v) => toggleActive(t, v === true)}
                        aria-label={`Ativar ${t.service_label}`}
                      />
                      Ativa
                    </label>
                  ) : (
                    <span className="text-xs text-muted-foreground">De fábrica</span>
                  )}

{canManage ? (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditingId(t.id)}
                            aria-label={`Editar ${t.service_label}`}
                          >
                            <Pencil className="mr-1 h-3.5 w-3.5" /> Editar
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openDuplicate(t)}
                            aria-label={`Duplicar ${t.service_label}`}
                          >
                            <Copy className="mr-1 h-3.5 w-3.5" /> Duplicar
                          </Button>
                          {t.organization_id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-red-600 hover:text-red-700"
                              onClick={() => setDeleting(t)}
                              aria-label={`Remover ${t.service_label}`}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </>
                      ) : null}
                    </div>
                  </div>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!editing && canManage} onOpenChange={(open) => !open && setEditingId(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              Editando: {editing?.service_label}
            </DialogTitle>
            {editing?.organization_id ? (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Switch
                  checked={editing.is_active}
                  onCheckedChange={(v) => toggleActive(editing, v === true)}
                  aria-label="Vertente ativa"
                />
                Vertente ativa
              </div>
            ) : (
              <Badge variant="outline" className="w-fit">
                De fábrica — duplique para personalizar
              </Badge>
            )}
          </DialogHeader>
          {editing?.organization_id ? (
            <TemplateEditor template={editing} showLabel key={editing.id} />
          ) : (
            <div className="flex items-start gap-2 rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
              <Lock className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="space-y-3">
                <p>
                  Vertentes de fábrica são compartilhadas por todos os times e não podem ser
                  alteradas. Duplique para criar a sua própria versão e editá-la.
                </p>
                {canManage && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (editing) {
                        setEditingId(null);
                        openDuplicate(editing);
                      }
                    }}
                  >
                    <Copy className="mr-2 h-3.5 w-3.5" /> Duplicar esta vertente
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!dupSource} onOpenChange={(open) => !open && setDupSource(null)}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Copy className="h-4 w-4" />
              Duplicar vertente
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Será criada uma cópia da vertente <strong>{dupSource?.service_label}</strong> para o
            seu time. Você ajusta os critérios depois.
          </p>
          <div className="space-y-2">
            <Label>Nome da nova vertente</Label>
            <Input
              value={dupLabel}
              onChange={(e) => setDupLabel(e.target.value)}
              placeholder="Minha versão da vertente"
            />
          </div>
          {!!dupSource?.enrichment_steps?.length && (
            <p className="text-xs text-muted-foreground">
              Herda as fontes de informação, características e acompanhamento da original.
            </p>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDupSource(null)}>
              Cancelar
            </Button>
            <Button onClick={handleDuplicate} disabled={!dupLabel.trim()}>
              Duplicar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleting} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remover vertente?</AlertDialogTitle>
            <AlertDialogDescription>
              A vertente <strong>{deleting?.service_label}</strong> será removida do seu time.
              Campanhas que a usam precisam trocar de vertente antes.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
              Remover
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}