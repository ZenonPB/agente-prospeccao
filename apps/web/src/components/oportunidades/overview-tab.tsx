'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Globe,
  Phone,
  Mail,
  MapPin,
  Calendar,
  AlertTriangle,
} from 'lucide-react';
import { LinkedInIcon } from '@/components/ui/linkedin-icon';
import { FollowUpCard, formatPrimaryNeed } from '@/components/oportunidades/follow-up-card';
import type { Lead } from '@/types/index';

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

export function OverviewTab({ lead }: { lead: Lead }) {
  const staleEnrichment = staleEnrichmentLabel(lead.enrichment_freshness);

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
              <Badge className="bg-emerald-100 text-emerald-700 text-lg">{lead.qualification_score}</Badge>
            </div>
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
