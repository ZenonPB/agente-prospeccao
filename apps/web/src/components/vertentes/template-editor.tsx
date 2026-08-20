'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2, Plus, Trash2, Search, CalendarClock, BookOpen } from 'lucide-react';
import { cn } from '@/lib/utils';
import { usePatchScoringTemplate } from '@/hooks/use-api';
import type { ScoringTemplate, ScoringTemplateInput, Playbook, EnrichmentStep } from '@/lib/api';
import { toast } from 'sonner';

export const DEFAULT_CADENCE = [0, 3, 7, 14];

export const STEP_OPTIONS: { key: EnrichmentStep; label: string; hint: string }[] = [
  { key: 'technical_site', label: 'Site da empresa', hint: 'Tecnologias, segurança e desempenho do site' },
  { key: 'cnpj_receita', label: 'Dados da Receita Federal (CNPJ)', hint: 'Porte, ramo de atividade, tempo de empresa' },
  { key: 'business_social', label: 'Reputação no Google', hint: 'Nota e quantidade de avaliações' },
];

export const CADENCE_LABELS = ['1ª mensagem', '2ª mensagem', '3ª mensagem', 'Encerramento'];

// Templates antigos não têm `enrichment_steps` — deriva dos flags binários
// (mesmo critério do backend) para o switch aparecer preenchido.
export function deriveSteps(tmpl: ScoringTemplate): EnrichmentStep[] {
  const steps: EnrichmentStep[] = [];
  if (tmpl.requires_technical_report) steps.push('technical_site');
  if (tmpl.requires_business_data) steps.push('cnpj_receita');
  steps.push('business_social');
  return Array.from(new Set(steps));
}

const GROUPS: {
  key: 'positive_signals' | 'negative_signals' | 'context_signals';
  title: string;
  hint: string;
  tone: string;
  placeholder: string;
}[] = [
  {
    key: 'positive_signals',
    title: 'Características que indicam oportunidade',
    hint: 'Chances maiores quando presentes na empresa',
    tone: 'text-green-700',
    placeholder: 'Ex.: Porte industrial',
  },
  {
    key: 'negative_signals',
    title: 'Características que reduzem a chance',
    hint: 'Cuidado quando presentes na empresa',
    tone: 'text-red-700',
    placeholder: 'Ex.: Atuação residencial',
  },
  {
    key: 'context_signals',
    title: 'Contexto do mercado',
    hint: 'Situação extra — região, segmento, porte',
    tone: 'text-muted-foreground',
    placeholder: 'Ex.: Região com demanda aquecida',
  },
];

interface TemplateEditorProps {
  template: ScoringTemplate;
  canEdit?: boolean;
  showLabel?: boolean;
  onSaved?: (saved: ScoringTemplate) => void;
}

export function TemplateEditor({
  template,
  canEdit = true,
  showLabel = false,
  onSaved,
}: TemplateEditorProps) {
  const patchTemplate = usePatchScoringTemplate();
  const [draft, setDraft] = useState<Partial<ScoringTemplateInput> | null>(null);
  const [saving, setSaving] = useState(false);

  const current = draft ?? {
    service_label: template.service_label,
    positive_signals: template.positive_signals,
    negative_signals: template.negative_signals,
    context_signals: template.context_signals,
    requires_technical_report: template.requires_technical_report,
    requires_business_data: template.requires_business_data,
    enrichment_steps: template.enrichment_steps,
    cadence_schedule: template.cadence_schedule,
    extra_instructions: template.extra_instructions,
    playbook: template.playbook ?? {},
  };

  const handleSave = async () => {
    if (!draft) return;
    const groups = ['positive_signals', 'negative_signals', 'context_signals'] as const;
    const emptyLabel = groups.some((g) =>
      (draft[g] ?? []).some((s) => !(s.label ?? '').trim())
    );
    if (emptyLabel) {
      toast.error('Preencha o nome de todas as características (ou remova as vazias) antes de salvar.');
      return;
    }
    setSaving(true);
    try {
      const saved = await patchTemplate.mutateAsync({ id: template.id, data: draft });
      setDraft(null);
      onSaved?.(saved);
      toast.success('Alterações salvas com sucesso.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Falha ao salvar a vertente.');
    } finally {
      setSaving(false);
    }
  };

  const updateSignal = (
    group: 'positive_signals' | 'negative_signals' | 'context_signals',
    index: number,
    patch: Partial<{ label: string; description: string; weight_hint: string }>,
  ) => {
    const signals = [...(current[group] ?? [])];
    signals[index] = { ...signals[index], ...patch };
    setDraft({ ...current, [group]: signals });
  };

  const addSignal = (group: 'positive_signals' | 'negative_signals' | 'context_signals') => {
    const signals = [...(current[group] ?? []), { label: '', description: '', weight_hint: 'medium' }];
    setDraft({ ...current, [group]: signals });
  };

  const removeSignal = (group: 'positive_signals' | 'negative_signals' | 'context_signals', index: number) => {
    const signals = [...(current[group] ?? [])];
    signals.splice(index, 1);
    setDraft({ ...current, [group]: signals });
  };

  const updatePlaybook = (patch: Partial<Playbook>) => {
    setDraft({ ...current, playbook: { ...(current.playbook ?? {}), ...patch } });
  };

  const playbook: Playbook = current.playbook ?? {};

  const addPlaybookItem = (key: 'hooks' | 'subject_ideas') => {
    updatePlaybook({ [key]: [...(playbook[key] ?? []), ''] });
  };

  const updatePlaybookItem = (key: 'hooks' | 'subject_ideas', index: number, value: string) => {
    const items = [...(playbook[key] ?? [])];
    items[index] = value;
    updatePlaybook({ [key]: items });
  };

  const removePlaybookItem = (key: 'hooks' | 'subject_ideas', index: number) => {
    const items = [...(playbook[key] ?? [])];
    items.splice(index, 1);
    updatePlaybook({ [key]: items });
  };

  const objections = playbook.objections ?? [];
  const updateObjection = (index: number, patch: Partial<{ objection: string; approach: string }>) => {
    const items = [...objections];
    items[index] = { ...items[index], ...patch };
    updatePlaybook({ objections: items });
  };

  const addObjection = () => {
    updatePlaybook({ objections: [...objections, { objection: '', approach: '' }] });
  };

  const removeObjection = (index: number) => {
    const items = [...objections];
    items.splice(index, 1);
    updatePlaybook({ objections: items });
  };

  const currentSteps: EnrichmentStep[] = draft?.enrichment_steps ?? template.enrichment_steps ?? deriveSteps(template);
  const currentCadence: number[] = draft?.cadence_schedule ?? template.cadence_schedule ?? DEFAULT_CADENCE;

  const toggleStep = (step: EnrichmentStep, enabled: boolean) => {
    const next = new Set(currentSteps);
    if (enabled) next.add(step);
    else next.delete(step);
    setDraft({ ...current, enrichment_steps: Array.from(next) });
  };

  const updateCadenceDay = (index: number, value: string) => {
    const days = [...currentCadence];
    days[index] = value === '' ? 0 : Number(value);
    setDraft({ ...current, cadence_schedule: days });
  };

  return (
    <div className="space-y-4">
      {showLabel && (
        <div className="space-y-2">
          <Label>Nome da vertente</Label>
          <Input
            value={current.service_label ?? ''}
            onChange={(e) => setDraft({ ...current, service_label: e.target.value })}
            placeholder="Ex.: Manutenção de compressores para indústrias"
          />
        </div>
      )}

      <div className="space-y-2">
        <Label>Instruções extras (opcional)</Label>
        <Input
          value={current.extra_instructions ?? ''}
          onChange={(e) => setDraft({ ...current, extra_instructions: e.target.value })}
          placeholder="Orientação simples enviada para a Inteligência Artificial"
        />
      </div>

      <fieldset disabled={!canEdit} className="space-y-4">
        <div className="space-y-3 rounded-lg border p-3">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm font-medium">O que analisar nesta empresa</p>
            <Badge variant="outline" className="text-[10px] font-normal">
              ajuste por tipo de serviço
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Escolha as informações que o sistema deve buscar para avaliar se a empresa
            é uma boa oportunidade. Indústrias costumam render melhor com dados da
            Receita do que com auditoria de site.
          </p>
          <div className="space-y-2">
            {STEP_OPTIONS.map((opt) => (
              <label
                key={opt.key}
                className="flex items-start gap-3 rounded-md p-2 hover:bg-muted/40"
              >
                <Switch
                  checked={currentSteps.includes(opt.key)}
                  onCheckedChange={(v) => toggleStep(opt.key, v === true)}
                  className="mt-0.5"
                />
                <span className="space-y-0.5">
                  <span className="block text-sm font-medium">{opt.label}</span>
                  <span className="block text-xs text-muted-foreground">{opt.hint}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="space-y-3 rounded-lg border p-3">
          <div className="flex items-center gap-2">
            <CalendarClock className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm font-medium">Acompanhamento da empresa</p>
            <Badge variant="outline" className="text-[10px] font-normal">
              dias após o primeiro contato
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Em que dias enviar cada mensagem? Para vendas rápidas, mensagens próximas
            umas das outras funcionam bem. Para vendas industriais longas, use semanas
            (ex.: 0, 7, 30, 60).
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {currentCadence.map((day, i) => (
              <div key={i} className="space-y-1">
                <Label className="text-xs text-muted-foreground">{CADENCE_LABELS[i]}</Label>
                <div className="flex items-center gap-1">
                  <Input
                    type="number"
                    min="0"
                    value={String(day)}
                    onChange={(e) => updateCadenceDay(i, e.target.value)}
                    className="h-9"
                    aria-label={`dia da ${CADENCE_LABELS[i]}`}
                  />
                  <span className="text-xs text-muted-foreground">dias</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {GROUPS.map((group) => (
          <div key={group.key} className="space-y-2">
            <div className="flex items-center justify-between">
              <div>
                <p className={cn('text-sm font-medium', group.tone)}>{group.title}</p>
                <p className="text-xs text-muted-foreground">{group.hint}</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => addSignal(group.key)}>
                <Plus className="mr-1 h-3 w-3" /> Adicionar
              </Button>
            </div>
            {(current[group.key] ?? []).map((sig, i) => (
              <div key={i} className="flex items-start gap-2">
                <Input
                  className="flex-1"
                  placeholder={group.placeholder}
                  value={sig.label ?? ''}
                  onChange={(e) => updateSignal(group.key, i, { label: e.target.value })}
                />
                <Input
                  className="hidden flex-1 md:block"
                  placeholder="Por que importa / como identificar"
                  value={sig.description ?? ''}
                  onChange={(e) => updateSignal(group.key, i, { description: e.target.value })}
                />
                <Select
                  value={sig.weight_hint ?? 'medium'}
                  onValueChange={(v) => v && updateSignal(group.key, i, { weight_hint: v })}
                >
                  <SelectTrigger className="w-24">
                    <SelectValue>
                      {(value) =>
                        ({ high: 'alta', medium: 'média', low: 'baixa' })[value as string] ?? (value as string)
                      }
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">alta</SelectItem>
                    <SelectItem value="medium">média</SelectItem>
                    <SelectItem value="low">baixa</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeSignal(group.key, i)}
                  aria-label="Remover característica"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        ))}

        <div className="space-y-3 rounded-lg border p-3">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm font-medium">Como abordar esse tipo de empresa</p>
            <Badge variant="outline" className="text-[10px] font-normal">
              mensagens deste tipo de empresa
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Frases de abertura, assuntos e dúvidas comuns deste perfil — usados para
            variar as mensagens conforme o serviço vendido.
          </p>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs text-muted-foreground">Frases de abertura</Label>
              <Button variant="ghost" size="sm" onClick={() => addPlaybookItem('hooks')}>
                <Plus className="mr-1 h-3 w-3" /> Adicionar
              </Button>
            </div>
            {(playbook.hooks ?? []).map((hook, i) => (
              <div key={i} className="flex items-start gap-2">
                <Input
                  className="flex-1"
                  placeholder="Ex.: Petshop perde dono local para o e-commerce"
                  value={hook ?? ''}
                  onChange={(e) => updatePlaybookItem('hooks', i, e.target.value)}
                />
                <Button variant="ghost" size="icon" onClick={() => removePlaybookItem('hooks', i)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs text-muted-foreground">Assuntos para o e-mail</Label>
              <Button variant="ghost" size="sm" onClick={() => addPlaybookItem('subject_ideas')}>
                <Plus className="mr-1 h-3 w-3" /> Adicionar
              </Button>
            </div>
            {(playbook.subject_ideas ?? []).map((subject, i) => (
              <div key={i} className="flex items-start gap-2">
                <Input
                  className="flex-1"
                  placeholder="Ex.: Seus clientes te acham no Google?"
                  value={subject ?? ''}
                  onChange={(e) => updatePlaybookItem('subject_ideas', i, e.target.value)}
                />
                <Button variant="ghost" size="icon" onClick={() => removePlaybookItem('subject_ideas', i)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs text-muted-foreground">Dúvidas comuns do cliente</Label>
              <Button variant="ghost" size="sm" onClick={addObjection}>
                <Plus className="mr-1 h-3 w-3" /> Adicionar
              </Button>
            </div>
            {objections.map((obj, i) => (
              <div key={i} className="space-y-1.5 rounded-md bg-muted/40 p-2">
                <Input
                  className="flex-1"
                  placeholder="Dúvida"
                  value={obj.objection ?? ''}
                  onChange={(e) => updateObjection(i, { objection: e.target.value })}
                />
                <div className="flex items-center gap-2">
                  <Input
                    className="flex-1"
                    placeholder="Como responder"
                    value={obj.approach ?? ''}
                    onChange={(e) => updateObjection(i, { approach: e.target.value })}
                  />
                  <Button variant="ghost" size="icon" onClick={() => removeObjection(i)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </fieldset>

      {canEdit && (
        <Button onClick={handleSave} disabled={saving || !draft}>
          {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Salvar alterações nesta vertente
        </Button>
      )}
    </div>
  );
}