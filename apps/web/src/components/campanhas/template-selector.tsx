'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2, Sparkles, Lock } from 'lucide-react';
import { useScoringTemplates, useOrgMembership } from '@/hooks/use-api';
import type { ScoringTemplate } from '@/lib/api';
import { TemplateEditor, STEP_OPTIONS, deriveSteps } from '@/components/vertentes/template-editor';

interface TemplateSelectorProps {
  value: string | null;
  onChange: (templateId: string | null, template: ScoringTemplate | null) => void;
}

export function TemplateSelector({ value, onChange }: TemplateSelectorProps) {
  const { data, isLoading } = useScoringTemplates({ scope: 'all', include_inactive: true });
  const { data: membership } = useOrgMembership();
  const templates = data?.templates ?? [];
  const selected = templates.find((t) => t.id === value) ?? null;

  const myRole = membership?.membership?.role;
  const canEdit =
    myRole === 'OWNER' || myRole === 'ADMIN' || membership?.membership?.sales_role === 'MANAGER';

  const handleSelect = (id: string) => {
    const tmpl = templates.find((t) => t.id === id) ?? null;
    onChange(id, tmpl);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Critérios de avaliação dos leads
          <Badge variant="secondary">como a IA escolhe as melhores oportunidades</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Carregando vertentes...
          </div>
        ) : (
          <>
            <div className="space-y-2">
              <Label>Escolher vertente</Label>
              <Select value={selected?.id ?? ''} onValueChange={(id) => id && handleSelect(id)}>
                <SelectTrigger>
                  <SelectValue>
                    {(value) => {
                      const t = templates.find((tpl) => tpl.id === value);
                      return t ? `${t.service_label}${t.is_generated ? ' (gerada por IA)' : ''}` : 'Selecione uma vertente';
                    }}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {templates.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.service_label}
                      {t.is_generated ? ' (gerada por IA)' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {!selected && (
                <p className="text-xs text-muted-foreground">
                  Sem vertente específica: a IA escolhe os melhores critérios para o segmento automaticamente.
                </p>
              )}
            </div>

            {selected && (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  {selected.is_generated && (
                    <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">
                      <Sparkles className="mr-1 h-3 w-3" />
                      Gerada por IA — revise antes de usar em massa
                    </Badge>
                  )}
                  {STEP_OPTIONS.filter((o) => deriveSteps(selected).includes(o.key)).map((o) => (
                    <Badge key={o.key} variant="outline">
                      {o.label}
                    </Badge>
                  ))}
                </div>

                {!canEdit ? (
                  <div className="flex items-start gap-2 rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
                    <Lock className="mt-0.5 h-4 w-4 shrink-0" />
                    <p>
                      Você pode usar as vertentes disponíveis, mas a edição é exclusiva
                      de gestores e administradores. Peça ao gestor do time para ajustar
                      a vertente desta campanha.
                    </p>
                  </div>
                ) : (
                  <TemplateEditor template={selected} />
                )}
              </>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}