'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2, Sparkles, Plus, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useScoringTemplates, usePatchScoringTemplate } from '@/hooks/use-api';
import type { ScoringTemplate, ScoringTemplateInput } from '@/lib/api';

interface TemplateSelectorProps {
  value: string | null;
  onChange: (templateId: string | null, template: ScoringTemplate | null) => void;
}

export function TemplateSelector({ value, onChange }: TemplateSelectorProps) {
  const { data, isLoading } = useScoringTemplates({ scope: 'all', include_inactive: true });
  const patchTemplate = usePatchScoringTemplate();
  const templates = data?.templates ?? [];
  const selected = templates.find((t) => t.id === value) ?? null;
  const [draft, setDraft] = useState<Partial<ScoringTemplateInput> | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSelect = (id: string) => {
    const tmpl = templates.find((t) => t.id === id) ?? null;
    setDraft(null);
    onChange(id, tmpl);
  };

  const handleSave = async () => {
    if (!selected || !draft) return;
    setSaving(true);
    try {
      await patchTemplate.mutateAsync({ id: selected.id, data: draft });
      setDraft(null);
    } finally {
      setSaving(false);
    }
  };

  const updateSignal = (
    group: 'positive_signals' | 'negative_signals' | 'context_signals',
    index: number,
    patch: Partial<{ label: string; description: string; weight_hint: string }>,
  ) => {
    const base = selected;
    if (!base) return;
    const current = draft ?? {
      positive_signals: base.positive_signals,
      negative_signals: base.negative_signals,
      context_signals: base.context_signals,
    };
    const signals = [...(current[group] ?? [])];
    signals[index] = { ...signals[index], ...patch };
    setDraft({ ...current, [group]: signals });
  };

  const addSignal = (group: 'positive_signals' | 'negative_signals' | 'context_signals') => {
    const base = selected;
    if (!base) return;
    const current = draft ?? {
      positive_signals: base.positive_signals,
      negative_signals: base.negative_signals,
      context_signals: base.context_signals,
    };
    const signals = [...(current[group] ?? []), { label: '', weight_hint: 'medium' }];
    setDraft({ ...current, [group]: signals });
  };

  const removeSignal = (group: 'positive_signals' | 'negative_signals' | 'context_signals', index: number) => {
    const base = selected;
    if (!base) return;
    const current = draft ?? {
      positive_signals: base.positive_signals,
      negative_signals: base.negative_signals,
      context_signals: base.context_signals,
    };
    const signals = [...(current[group] ?? [])];
    signals.splice(index, 1);
    setDraft({ ...current, [group]: signals });
  };

  const groups: { key: 'positive_signals' | 'negative_signals' | 'context_signals'; title: string; hint: string; tone: string }[] = [
    { key: 'positive_signals', title: 'Sinais positivos', hint: 'Aumentam o score quando presentes', tone: 'text-green-700' },
    { key: 'negative_signals', title: 'Sinais negativos', hint: 'Reduzem o score quando presentes', tone: 'text-red-700' },
    { key: 'context_signals', title: 'Sinais contextuais', hint: 'Contexto extra (região, segmento)', tone: 'text-muted-foreground' },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Template de critérios
          <Badge variant="secondary">como a IA avalia os leads</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Carregando templates...
          </div>
        ) : (
          <>
            <div className="space-y-2">
              <Label>Escolher template</Label>
              <Select value={selected?.id ?? ''} onValueChange={(id) => id && handleSelect(id)}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione um template" />
                </SelectTrigger>
                <SelectContent>
                  {templates.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.service_label}
                      {t.is_generated ? ' (gerado)' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {!selected && (
                <p className="text-xs text-muted-foreground">
                  Sem template específico: a IA roteia automaticamente o melhor critério para o segmento.
                </p>
              )}
            </div>

            {selected && (
              <>
                <div className="flex flex-wrap gap-2">
                  {selected.is_generated && (
                    <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">
                      <Sparkles className="mr-1 h-3 w-3" />
                      Gerado por IA — revisar antes de usar em massa
                    </Badge>
                  )}
                  {selected.requires_technical_report && <Badge variant="outline">Análise técnica</Badge>}
                  {selected.requires_business_data && <Badge variant="outline">Dados cadastrais</Badge>}
                </div>

                <div className="space-y-2">
                  <Label>Instruções extras (opcional)</Label>
                  <Input
                    value={draft?.extra_instructions ?? selected.extra_instructions ?? ''}
                    onChange={(e) =>
                      setDraft({ ...(draft ?? {}), extra_instructions: e.target.value })
                    }
                    placeholder="Instrução livre injetada no prompt da IA"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Flags</Label>
                  <div className="flex gap-6">
                    <label className="flex items-center gap-2 text-sm">
                      <Switch
                        checked={draft?.requires_technical_report ?? selected.requires_technical_report}
                        onCheckedChange={(v) =>
                          setDraft({ ...(draft ?? {}), requires_technical_report: v === true })
                        }
                      />
                      Análise técnica do site
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <Switch
                        checked={draft?.requires_business_data ?? selected.requires_business_data}
                        onCheckedChange={(v) =>
                          setDraft({ ...(draft ?? {}), requires_business_data: v === true })
                        }
                      />
                      Dados cadastrais
                    </label>
                  </div>
                </div>

                {groups.map((group) => (
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
                    {(draft?.[group.key] ?? selected[group.key] ?? []).map((sig, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <Input
                          className="flex-1"
                          placeholder="Sinal"
                          value={sig.label}
                          onChange={(e) => updateSignal(group.key, i, { label: e.target.value })}
                        />
                        <Input
                          className="hidden flex-1 md:block"
                          placeholder="Descrição"
                          value={sig.description ?? ''}
                          onChange={(e) => updateSignal(group.key, i, { description: e.target.value })}
                        />
                        <Select
                          value={sig.weight_hint}
                          onValueChange={(v) => v && updateSignal(group.key, i, { weight_hint: v })}
                        >
                          <SelectTrigger className="w-24">
                            <SelectValue />
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
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ))}

                <Button onClick={handleSave} disabled={saving || !draft}>
                  {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Salvar alterações no template
                </Button>
              </>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
