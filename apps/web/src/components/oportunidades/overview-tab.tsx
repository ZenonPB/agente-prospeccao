'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Globe,
  Phone,
  Mail,
  MapPin,
  Calendar,
  AlertTriangle,
  Check,
  CircleDashed,
  ChevronDown,
} from 'lucide-react';
import { LinkedInIcon } from '@/components/ui/linkedin-icon';
import { FollowUpCard, formatPrimaryNeed } from '@/components/oportunidades/follow-up-card';
import { NextActionCard } from '@/components/oportunidades/next-action-card';
import { EventTimingCard } from '@/components/oportunidades/event-timing-card';
import type { Lead } from '@/types/index';
import { getScoreBand, scoreBandBadge, SCORE_THRESHOLD_HINT, priorityLabels } from '@/components/oportunidades/score-scale';

const statusLabels: Record<string, string> = {
  NOVO: 'Novo',
  ANALISADO: 'Analisado',
  QUALIFICADO: 'Apto para contato',
  DESQUALIFICADO: 'Desqualificado',
  CONTATADO: 'Contatado',
  RESPONDIDO: 'Respondeu',
  REUNIAO_MARCADA: 'Reunião marcada',
  REUNIAO_FEITA: 'Reunião realizada',
  PROPOSTA_ENVIADA: 'Proposta enviada',
  PERDIDO: 'Perdido',
};

// Fontes de enriquecimento com dados fora do TTL (para o aviso de dados antigos).
function staleEnrichmentLabel(freshness?: Lead['enrichment_freshness']): string[] {
  if (!freshness) return [];
  const out: string[] = [];
  if (freshness.linkedin === 'stale') out.push('LinkedIn');
  if (freshness.site === 'stale') out.push('análise do site');
  if (freshness.reviews === 'stale') out.push('avaliações do Google');
  return out;
}

export function OverviewTab({ lead, onOpenTab }: { lead: Lead; onOpenTab?: (tab: string) => void }) {
  const staleEnrichment = staleEnrichmentLabel(lead.enrichment_freshness);
  const [showSources, setShowSources] = useState(false);

  const whyItems: { known: boolean; text: string }[] = [];
  if (lead.category) {
    whyItems.push({ known: true, text: `Atua em ${lead.category}` });
  }
  if (lead.city || lead.state) {
    const place = [lead.city, lead.state].filter(Boolean).join(', ');
    whyItems.push({ known: true, text: `Está em ${place}` });
  }
  if (lead.qualification_score != null && lead.qualification_score >= 60) {
    whyItems.push({ known: true, text: 'Avaliado como compatível com sua oferta' });
  }
  if (lead.website) {
    whyItems.push({ known: true, text: 'Presença digital identificada' });
  } else {
    whyItems.push({ known: false, text: 'Ainda não identificamos o site da empresa' });
  }

  const sources: { label: string; detail?: string }[] = [];
  if (lead.website) {
    sources.push({ label: 'Site da empresa', detail: lead.website });
  }
  if (lead.company_linkedin_url) {
    sources.push({ label: 'LinkedIn', detail: 'Perfil da empresa' });
  }
  if (lead.instagram_url) {
    sources.push({ label: 'Instagram', detail: 'Perfil da empresa' });
  }
  if (lead.google_rating != null) {
    sources.push({ label: 'Google', detail: 'Avaliações e presença local' });
  }
  const freshness = lead.enrichment_freshness;
  if (freshness && !lead.website) {
    if (freshness.site) sources.push({ label: 'Site da empresa', detail: 'Análise técnica' });
  }
  if (freshness?.linkedin && !lead.company_linkedin_url) {
    sources.push({ label: 'LinkedIn', detail: 'Perfil consultado' });
  }
  if (freshness?.reviews && lead.google_rating == null) {
    sources.push({ label: 'Google', detail: 'Avaliações consultadas' });
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Informações do Lead</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {lead.website && (
              <div className="flex items-center gap-3">
                <Globe className="h-4 w-4 text-muted-foreground" />
                <a href={lead.website} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  {lead.website}
                </a>
              </div>
            )}
            {lead.company_linkedin_url && (
              <div className="flex items-center gap-3">
                <LinkedInIcon className="h-4 w-4 text-primary" />
                <a href={lead.company_linkedin_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">
                  Empresa no LinkedIn
                </a>
              </div>
            )}
            {lead.instagram_url && (
              <div className="flex items-center gap-3">
                <span aria-hidden="true" className="text-sm text-pink-600">📷</span>
                <a href={lead.instagram_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">
                  Perfil no Instagram
                </a>
              </div>
            )}
            {lead.phone && (
              <div className="flex items-center gap-3">
                <Phone className="h-4 w-4 text-muted-foreground" />
                <span>{lead.phone}</span>
              </div>
            )}
            {lead.email && (
              <div className="flex items-center gap-3">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <span>{lead.email}</span>
              </div>
            )}
            <div className="flex items-center gap-3">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              <span>{lead.city || 'Não informado'}{lead.state ? `, ${lead.state}` : ''}{lead.country ? `, ${lead.country}` : ''}</span>
            </div>
            <div className="flex items-center gap-3">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <span>Encontrado em {new Date(lead.created_at).toLocaleDateString('pt-BR')}</span>
            </div>
            {staleEnrichment.length > 0 && (
              <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-700">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span>{staleEnrichment.join(', ')} — dados antigos</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Aptidão</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Pontuação:</span>
              <Badge
                className={`${scoreBandBadge[getScoreBand(lead.qualification_score)]} text-lg`}
                title={getScoreBand(lead.qualification_score) === 'unevaluated' ? 'Ainda não avaliado' : SCORE_THRESHOLD_HINT}
              >
                {getScoreBand(lead.qualification_score) === 'unevaluated' ? 'não avaliado' : lead.qualification_score}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">{SCORE_THRESHOLD_HINT}</p>
            {lead.priority && (
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">Prioridade:</span>
                <Badge variant="outline">{priorityLabels[lead.priority] ?? lead.priority}</Badge>
              </div>
            )}
            {lead.priority && lead.priority_reasoning && (
              <div>
                <p className="text-sm text-muted-foreground">
                  Por que prioridade {(priorityLabels[lead.priority] ?? lead.priority).toLowerCase()}:
                </p>
                <p className="text-sm mt-1">{lead.priority_reasoning}</p>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Necessidade:</span>
              <Badge variant="outline">{formatPrimaryNeed(lead.primary_need)}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Status:</span>
              <Badge>{statusLabels[lead.status] || lead.status}</Badge>
            </div>
            {lead.qualification_reason && (
              <div className="pt-2">
                <p className="text-sm text-muted-foreground">Por que este lead é uma oportunidade:</p>
                <p className="text-sm mt-1">{lead.qualification_reason}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <NextActionCard lead={lead} nextAction={lead.next_best_action} onOpenTab={onOpenTab} />

      <Card>
        <CardHeader>
          <CardTitle>Por que encontramos esta empresa</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {whyItems.every((item) => !item.known) && (
            <p className="text-sm text-muted-foreground">
              Ainda estamos reunindo informações sobre esta empresa.
            </p>
          )}
          <ul className="space-y-2">
            {whyItems.map((item, index) => (
              <li key={index} className="flex items-start gap-2 text-sm">
                {item.known ? (
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
                ) : (
                  <CircleDashed className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                )}
                <span className={item.known ? undefined : 'text-muted-foreground'}>{item.text}</span>
              </li>
            ))}
          </ul>
          <div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSources((value) => !value)}
              aria-expanded={showSources}
              className="gap-1 px-2 text-xs"
            >
              Ver fontes
              <ChevronDown
                className={`h-3.5 w-3.5 transition-transform ${showSources ? 'rotate-180' : ''}`}
                aria-hidden="true"
              />
            </Button>
            {showSources && (
              <div className="mt-2 space-y-1.5 rounded-lg border bg-muted/30 p-3">
                {sources.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Ainda não há fontes registradas para este lead.
                  </p>
                ) : (
                  sources.map((source, index) => (
                    <p key={index} className="text-xs">
                      <span className="font-medium">{source.label}</span>
                      {source.detail && (
                        <span className="text-muted-foreground"> — {source.detail}</span>
                      )}
                    </p>
                  ))
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <EventTimingCard leadId={lead.id} />

      {(lead.pitch_angle || lead.suggested_subject) && (
        <Card>
          <CardHeader>
            <CardTitle>Pitch de Abordagem</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {lead.pitch_angle && (
              <div>
                <p className="text-sm text-muted-foreground">Gancho principal:</p>
                <p className="text-sm mt-1">{lead.pitch_angle}</p>
              </div>
            )}
            {lead.suggested_subject && (
              <div>
                <p className="text-sm text-muted-foreground">Sugestão de assunto para e-mail:</p>
                <p className="text-sm mt-1 italic">&ldquo;{lead.suggested_subject}&rdquo;</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <FollowUpCard lead={lead} />
    </div>
  );
}
