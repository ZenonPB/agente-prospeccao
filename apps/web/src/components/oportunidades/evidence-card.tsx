'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { EvidenceItem, ScoreFactor, LeadPriority } from '@/types';

const severityConfig: Record<string, { label: string; color: string }> = {
  CRITICO: { label: 'Crítico', color: 'bg-red-100 text-red-700 border-red-200' },
  ALTO: { label: 'Alto', color: 'bg-orange-100 text-orange-700 border-orange-200' },
  MEDIO: { label: 'Médio', color: 'bg-amber-100 text-amber-700 border-amber-200' },
  BAIXO: { label: 'Baixo', color: 'bg-blue-100 text-blue-700 border-blue-200' },
  INFO: { label: 'Info', color: 'bg-slate-100 text-slate-700 border-slate-200' },
};

const priorityConfig: Record<LeadPriority, { label: string; color: string; emoji: string }> = {
  HOT: { label: 'Quente', color: 'bg-red-100 text-red-700 border-red-200', emoji: '🔥' },
  WARM: { label: 'Morno', color: 'bg-amber-100 text-amber-700 border-amber-200', emoji: '🌤️' },
  COLD: { label: 'Frio', color: 'bg-sky-100 text-sky-700 border-sky-200', emoji: '❄️' },
};

const severityOrder = ['CRITICO', 'ALTO', 'MEDIO', 'BAIXO', 'INFO'];

interface EvidenceCardProps {
  score: number;
  priority?: LeadPriority | null;
  priorityReasoning?: string;
  executiveSummary?: string;
  scoreFactors?: ScoreFactor[];
  evidence?: EvidenceItem[];
}

export function EvidenceCard({
  priority,
  priorityReasoning,
  executiveSummary,
  scoreFactors = [],
  evidence = [],
}: EvidenceCardProps) {
  // Garante que scoreFactors seja sempre um array válido
  const validScoreFactors = Array.isArray(scoreFactors) ? scoreFactors : [];
  const validEvidence = Array.isArray(evidence) ? evidence : [];
  
  const positives = validScoreFactors.filter((f) => f.impact === '+');
  const negatives = validScoreFactors.filter((f) => f.impact === '-');
  const sortedEvidence = [...validEvidence].sort(
    (a, b) => severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity)
  );

  // Se não há dados de scoring, mostra mensagem apropriada
  if (validScoreFactors.length === 0 && validEvidence.length === 0 && !executiveSummary) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Análise e Evidências</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Este lead ainda não foi analisado ou não possui dados suficientes para scoring.
            Execute o pipeline de coleta e enriquecimento para gerar a análise completa.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Análise e Evidências</CardTitle>
          {priority && priorityConfig[priority] && (
            <Badge className={priorityConfig[priority].color}>
              <span className="mr-1">{priorityConfig[priority].emoji}</span>
              {priorityConfig[priority].label}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Resumo executivo */}
        {executiveSummary && (
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-1">
              Resumo do consultor
            </p>
            <p className="text-sm">{executiveSummary}</p>
          </div>
        )}

        {/* Prioridade reasoning */}
        {priority && priorityReasoning && (
          <div className="rounded-lg border p-3 bg-muted/30">
            <p className="text-sm font-medium mb-1">
              Por que este lead é {priorityConfig[priority].label.toLowerCase()}?
            </p>
            <p className="text-sm text-muted-foreground">{priorityReasoning}</p>
          </div>
        )}

        {/* Fatores + / - */}
        {(positives.length > 0 || negatives.length > 0) && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-sm font-medium mb-2 text-emerald-700">Fatores positivos</p>
              {positives.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhum identificado</p>
              ) : (
                <ul className="space-y-2">
                  {positives.map((f, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-emerald-600 font-bold">+</span>
                      <div>
                        <p className="text-sm font-medium">{f.label}</p>
                        <p className="text-xs text-muted-foreground">{f.rationale}</p>
                        {f.evidence_ref && (
                          <p className="text-xs text-muted-foreground italic mt-0.5">
                            evidência: {f.evidence_ref}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <p className="text-sm font-medium mb-2 text-red-700">Fatores negativos</p>
              {negatives.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhum identificado</p>
              ) : (
                <ul className="space-y-2">
                  {negatives.map((f, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-red-600 font-bold">−</span>
                      <div>
                        <p className="text-sm font-medium">{f.label}</p>
                        <p className="text-xs text-muted-foreground">{f.rationale}</p>
                        {f.evidence_ref && (
                          <p className="text-xs text-muted-foreground italic mt-0.5">
                            evidência: {f.evidence_ref}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Evidências */}
        {sortedEvidence.length > 0 && (
          <div>
            <p className="text-sm font-medium mb-2">Evidências utilizadas pela IA</p>
            <div className="space-y-2">
              {sortedEvidence.map((e, i) => {
                const sev = severityConfig[e.severity] || severityConfig.INFO;
                return (
                  <div key={i} className="rounded-lg border p-3 space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">{e.title}</p>
                      <Badge variant="outline" className={sev.color}>
                        {sev.label}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{e.description}</p>
                    {(e.source || e.type) && (
                      <p className="text-xs text-muted-foreground">
                        Fonte: {e.source || e.type}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!executiveSummary && priorityReasoning === undefined && scoreFactors.length === 0 && evidence.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Este lead ainda não foi analisado pelo pipeline contextual. As evidências aparecerão aqui após reanálise.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
