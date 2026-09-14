'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { toast } from 'sonner';
import {
  Plus,
  Copy,
  Eye,
  MoreHorizontal,
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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
import { TemplateEditor, STEP_OPTIONS, deriveSteps } from '@/components/vertentes/template-editor';
import { TemplateDetails } from '@/components/vertentes/template-details';
import { TemplateInsightsCard } from '@/components/vertentes/template-insights-card';
import type { ScoringTemplate } from '@/lib/api';
import type { EnrichmentStep } from '@/lib/api';

function statusBadges(t: ScoringTemplate) {
  const badges: ReactNode[] = [];
  if (!t.organization_id) {
    badges.push(
      <Badge key="global" variant="outline">
        De fábrica
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
  if (badges.length === 0) {
    badges.push(
      <Badge key="own" variant="outline">
        Da sua organização
      </Badge>,
    );
  }
  return badges;
}

function summaryLine(t: ScoringTemplate): string {
  const criteria =
    (t.positive_signals?.length ?? 0) +
    (t.negative_signals?.length ?? 0) +
    (t.context_signals?.length ?? 0);
  const sources = deriveSteps(t).length;
  return `${criteria} ${criteria === 1 ? 'critério' : 'critérios'} · ${sources} ${sources === 1 ? 'fonte analisada' : 'fontes analisadas'}`;
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

  const [viewingId, setViewingId] = useState<string | null>(null);
  const [editingMode, setEditingMode] = useState(false);
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

  const viewing = viewingId ? templates.find((t) => t.id === viewingId) ?? null : null;
  const isFactoryViewing = !!viewing && !viewing.organization_id;
  const canEditViewing = !!viewing && !!viewing.organization_id && canManage;

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
          setViewingId(t.id);
          setEditingMode(true);
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
          setViewingId(t.id);
          setEditingMode(true);
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
        if (viewingId === deleting.id) {
          setViewingId(null);
          setEditingMode(false);
        }
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

      {canManage && <TemplateInsightsCard />}

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
          {filtered.map((t) => {
            const isFactory = !t.organization_id;
            return (
            <Card key={t.id} className="p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => { setViewingId(t.id); setEditingMode(false); }}
                      className="rounded text-left font-semibold text-foreground outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {t.service_label}
                    </button>
                    {statusBadges(t)}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t.extra_instructions || stepsLabel(t)}
                  </p>
                  <p className="text-xs text-muted-foreground">{summaryLine(t)}</p>
                </div>

                <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                  {canManage && !isFactory ? (
                    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Switch
                        checked={t.is_active}
                        onCheckedChange={(v) => toggleActive(t, v === true)}
                        aria-label={`Ativar ${t.service_label}`}
                      />
                      Ativa
                    </label>
                  ) : null}

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setViewingId(t.id); setEditingMode(false); }}
                    aria-label={`Ver detalhes de ${t.service_label}`}
                  >
                    <Eye className="mr-1 h-3.5 w-3.5" /> Ver detalhes
                  </Button>

                  {isFactory ? (
                    canManage ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openDuplicate(t)}
                        aria-label={`Duplicar ${t.service_label} e personalizar`}
                      >
                        <Copy className="mr-1 h-3.5 w-3.5" /> Duplicar e personalizar
                      </Button>
                    ) : null
                  ) : canManage ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button variant="ghost" size="sm" aria-label={`Mais ações para ${t.service_label}`} />
                        }
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => { setViewingId(t.id); setEditingMode(true); }}>
                          Editar
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => openDuplicate(t)}>
                          Duplicar
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-red-600 focus:text-red-700"
                          onClick={() => setDeleting(t)}
                        >
                          Excluir
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : null}
                </div>
              </div>
            </Card>
            );
          })}
        </div>
      )}

      <Dialog open={!!viewing} onOpenChange={(open) => { if (!open) { setViewingId(null); setEditingMode(false); } }}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex flex-wrap items-center gap-2">
              {editingMode && canEditViewing ? `Editando: ${viewing?.service_label}` : viewing?.service_label}
              {viewing && statusBadges(viewing)}
            </DialogTitle>
            {viewing && !editingMode && (
              <DialogDescription>
                {isFactoryViewing
                  ? 'Configuração padrão mantida pelo sistema.'
                  : 'Configuração da sua organização.'}
              </DialogDescription>
            )}
          </DialogHeader>
          {viewing && (editingMode && canEditViewing ? (
            <TemplateEditor template={viewing} showLabel key={viewing.id} />
          ) : (
            <TemplateDetails
              template={viewing}
              isFactory={isFactoryViewing}
              canManage={canManage}
              canEdit={canEditViewing}
              onEdit={() => setEditingMode(true)}
              onDuplicate={() => { setViewingId(null); setEditingMode(false); openDuplicate(viewing); }}
            />
          ))}
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