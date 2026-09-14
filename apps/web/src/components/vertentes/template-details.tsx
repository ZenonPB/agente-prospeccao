'use client';

import { useState } from 'react';
import { ArrowRight, Copy, Pencil, TrendingDown, TrendingUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { STEP_OPTIONS, DEFAULT_CADENCE, deriveSteps } from '@/components/vertentes/template-editor';
import type { EnrichmentStep, ScoringTemplate } from '@/lib/api';

const WEIGHT_LABELS: Record<string, string> = { high: 'Alta', medium: 'Média', low: 'Baixa' };

function weightLabel(weightHint?: string): string {
  return WEIGHT_LABELS[weightHint ?? ''] ?? 'Média';
}

function humanizeStep(key: string): string {
  return key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

function stepLabel(key: EnrichmentStep | string): string {
  return STEP_OPTIONS.find((o) => o.key === key)?.label ?? humanizeStep(key);
}

function stepsOf(t: ScoringTemplate): EnrichmentStep[] {
  return t.enrichment_steps?.length ? t.enrichment_steps : deriveSteps(t);
}

type Signal = { label?: string; description?: string; weight_hint?: string };

function SignalRow({ signal, tone }: { signal: Signal; tone: 'up' | 'down' }) {
  const Icon = tone === 'up' ? TrendingUp : TrendingDown;
  return (
    <li className="flex items-start gap-2.5 rounded-lg border p-3">
      <Icon
        className={tone === 'up' ? 'mt-0.5 h-4 w-4 shrink-0 text-emerald-600' : 'mt-0.5 h-4 w-4 shrink-0 text-red-600'}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium">{signal.label || 'Critério sem nome'}</p>
          <Badge variant="outline" className="text-[11px] font-normal">
            Importância: {weightLabel(signal.weight_hint)}
          </Badge>
        </div>
        {signal.description ? (
          <p className="mt-0.5 text-sm text-muted-foreground">{signal.description}</p>
        ) : null}
      </div>
    </li>
  );
}

function SimpleView({ template }: { template: ScoringTemplate }) {
  const steps = stepsOf(template);
  const cadence = template.cadence_schedule?.length ? template.cadence_schedule : DEFAULT_CADENCE;
  const positives = template.positive_signals ?? [];
  const negatives = template.negative_signals ?? [];
  const contexts = template.context_signals ?? [];

  return (
    <div className="space-y-6">
      <section aria-label="O que esta vertente procura">
        <h4 className="font-semibold">O que esta vertente procura</h4>
        <p className="mt-1 text-sm text-muted-foreground">
          {template.extra_instructions ||
            `Avalia empresas como potenciais clientes de ${template.service_label}.`}
        </p>
      </section>

      <section aria-label="Perfil desejado">
        <h4 className="font-semibold">Perfil desejado</h4>
        {contexts.length ? (
          <ul className="mt-2 flex flex-wrap gap-2">
            {contexts.map((c, i) => (
              <li key={i}>
                <Badge variant="secondary" className="px-3 py-1.5 text-sm font-normal" title={c.description}>
                  {c.label || 'Perfil sem nome'}
                </Badge>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            Sem perfil detalhado — a análise usa os critérios abaixo.
          </p>
        )}
      </section>

      {positives.length > 0 && (
        <section aria-label="O que aumenta a aderência">
          <h4 className="font-semibold">O que aumenta a aderência</h4>
          <ul className="mt-2 space-y-2">
            {positives.map((s, i) => (
              <SignalRow key={i} signal={s} tone="up" />
            ))}
          </ul>
        </section>
      )}

      {negatives.length > 0 && (
        <section aria-label="O que reduz a aderência">
          <h4 className="font-semibold">O que reduz a aderência</h4>
          <ul className="mt-2 space-y-2">
            {negatives.map((s, i) => (
              <SignalRow key={i} signal={s} tone="down" />
            ))}
          </ul>
        </section>
      )}

      <section aria-label="Como a análise acontece">
        <h4 className="font-semibold">Como a análise acontece</h4>
        <ol className="mt-2 flex flex-wrap items-center gap-1.5 text-sm">
          {['Empresa encontrada', ...steps.map(stepLabel), 'Análise dos critérios', 'Cálculo da aderência', 'Oportunidade priorizada'].map(
            (label, i, all) => (
              <li key={i} className="flex items-center gap-1.5">
                <span className="rounded-full border bg-muted/40 px-3 py-1">{label}</span>
                {i < all.length - 1 && <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />}
              </li>
            ),
          )}
        </ol>
      </section>

      <section aria-label="Acompanhamento">
        <h4 className="font-semibold">Acompanhamento</h4>
        <p className="mt-1 text-sm text-muted-foreground">
          Mensagens em {cadence.map((d) => `${d} dias`).join(', ').replace(/, ([^,]*)$/, ' e $1')} após o primeiro contato.
        </p>
      </section>
    </div>
  );
}

function AdvancedView({ template }: { template: ScoringTemplate }) {
  const steps = stepsOf(template);
  const prescoring = template.prescoring_config;
  const strategy = template.enrichment_strategy;

  const groups: { title: string; impact: string; signals: Signal[] }[] = [
    { title: 'Critérios positivos', impact: '+', signals: template.positive_signals ?? [] },
    { title: 'Critérios negativos', impact: '−', signals: template.negative_signals ?? [] },
    { title: 'Sinais de contexto', impact: '○', signals: template.context_signals ?? [] },
  ];

  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <section key={group.title} aria-label={group.title}>
          <h4 className="font-semibold">
            {group.title} <span className="text-muted-foreground">· impacto {group.impact}</span>
          </h4>
          {group.signals.length ? (
            <div className="mt-2 overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[520px] text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="p-2 font-medium">Critério</th>
                    <th className="p-2 font-medium">Descrição</th>
                    <th className="p-2 font-medium">Peso</th>
                  </tr>
                </thead>
                <tbody>
                  {group.signals.map((s, i) => (
                    <tr key={i} className="border-b last:border-b-0">
                      <td className="p-2 font-medium">{s.label || '—'}</td>
                      <td className="p-2 text-muted-foreground">{s.description || '—'}</td>
                      <td className="p-2 font-mono text-xs">{s.weight_hint || 'medium'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">Nenhum critério neste grupo.</p>
          )}
        </section>
      ))}

      <section aria-label="Pré-filtro da coleta">
        <h4 className="font-semibold">Pré-filtro da coleta</h4>
        {prescoring ? (
          <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
            <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Perfil</dt><dd className="font-medium">{prescoring.profile ?? '—'}</dd></div>
            <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Ativo</dt><dd className="font-medium">{prescoring.enabled === false ? 'Não' : 'Sim'}</dd></div>
            <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Nota mínima</dt><dd className="font-medium">{prescoring.threshold ?? '—'}</dd></div>
            <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Limite de candidatos</dt><dd className="font-medium">{prescoring.top_k ?? 'Sem limite'}</dd></div>
          </dl>
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            Sem pré-filtro configurado — nenhum candidato é descartado na coleta.
          </p>
        )}
      </section>

      <section aria-label="Dados utilizados">
        <h4 className="font-semibold">Dados utilizados</h4>
        <ul className="mt-2 space-y-1.5 text-sm">
          {steps.map((s) => (
            <li key={s} className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
              <span>
                <span className="font-medium">{stepLabel(s)}</span>
                <span className="text-muted-foreground">
                  {' — '}{STEP_OPTIONS.find((o) => o.key === s)?.hint ?? 'Fonte de informação da empresa'}
                </span>
              </span>
            </li>
          ))}
        </ul>
        {strategy && (strategy.skip?.length || strategy.stop_after) ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Ajustes de execução: {strategy.skip?.length ? `pula ${strategy.skip.map(stepLabel).join(', ')}` : ''}
            {strategy.skip?.length && strategy.stop_after ? '; ' : ''}
            {strategy.stop_after ? `para após ${stepLabel(strategy.stop_after)}` : ''}
          </p>
        ) : null}
      </section>

      <section aria-label="Configuração da avaliação">
        <h4 className="font-semibold">Configuração da avaliação</h4>
        <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Analisa site da empresa</dt><dd className="font-medium">{template.requires_technical_report ? 'Sim' : 'Não'}</dd></div>
          <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Usa dados cadastrais</dt><dd className="font-medium">{template.requires_business_data ? 'Sim' : 'Não'}</dd></div>
          <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Acompanhamento (dias)</dt><dd className="font-medium">{(template.cadence_schedule ?? DEFAULT_CADENCE).join(', ')}</dd></div>
          <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Instruções extras</dt><dd className="font-medium">{template.extra_instructions || '—'}</dd></div>
        </dl>
      </section>
    </div>
  );
}

interface TemplateDetailsProps {
  template: ScoringTemplate;
  isFactory: boolean;
  canManage: boolean;
  canEdit: boolean;
  onEdit: () => void;
  onDuplicate: () => void;
}

export function TemplateDetails({
  template,
  isFactory,
  canManage,
  canEdit,
  onEdit,
  onDuplicate,
}: TemplateDetailsProps) {
  const [view, setView] = useState<'simples' | 'avancada'>('simples');

  return (
    <div className="space-y-4">
      {isFactory && (
        <div className="rounded-lg border bg-muted/40 p-3 text-sm">
          <p className="font-medium">Vertente de fábrica</p>
          <p className="mt-0.5 text-muted-foreground">
            Esta é uma configuração padrão mantida pelo sistema. Ela pode receber melhorias ao
            longo do tempo e não pode ser alterada diretamente.
          </p>
          {canManage && (
            <Button variant="outline" size="sm" className="mt-2" onClick={onDuplicate}>
              <Copy className="mr-2 h-3.5 w-3.5" /> Duplicar e personalizar
            </Button>
          )}
        </div>
      )}

      <Tabs value={view} onValueChange={(v) => setView(v as 'simples' | 'avancada')}>
        <TabsList>
          <TabsTrigger value="simples">Visão simples</TabsTrigger>
          <TabsTrigger value="avancada">Visão avançada</TabsTrigger>
        </TabsList>
        <TabsContent value="simples" className="pt-4">
          <SimpleView template={template} />
        </TabsContent>
        <TabsContent value="avancada" className="pt-4">
          <AdvancedView template={template} />
        </TabsContent>
      </Tabs>

      {canEdit && (
        <div className="flex justify-end border-t pt-4">
          <Button onClick={onEdit}>
            <Pencil className="mr-2 h-4 w-4" /> Editar vertente
          </Button>
        </div>
      )}
    </div>
  );
}
