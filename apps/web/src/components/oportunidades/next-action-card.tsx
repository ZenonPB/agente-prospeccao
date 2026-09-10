'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Ban, Mail, Phone, RefreshCw, Search, Sparkles, UserCheck } from 'lucide-react';
import type { Lead, NextBestAction } from '@/types/index';

const actionLabels: Record<string, { label: string; icon: typeof Mail }> = {
  START_EMAIL_CADENCE: { label: 'Iniciar cadência por e-mail', icon: Mail },
  CALL: { label: 'Ligar agora', icon: Phone },
  RESEARCH: { label: 'Pesquisar canal de contato', icon: Search },
  RE_ENRICH: { label: 'Reenriquecer os dados do lead', icon: RefreshCw },
  REVIEW_DECISION_MAKER: { label: 'Revisar o decisor identificado', icon: UserCheck },
  STOP: { label: 'Lead bloqueado', icon: Ban },
};

const reasonLabels: Record<string, string> = {
  verified_email_and_active_opportunity: 'E-mail verificado e oportunidade ativa no funil.',
  direct_phone_contact: 'Telefone direto da pessoa.',
  pabx_with_target_person: 'PABX com pessoa-alvo identificada.',
  routable_phone_contact: 'Contato roteável com telefone.',
  institutional_phone_requires_reception: 'Telefone institucional — ligar pela recepção.',
  contact_requires_verification: 'Contato encontrado, mas ainda sem canal confirmado.',
  contact_unreachable: 'Contato sem canal acionável.',
  missing_actionable_contact: 'Nenhum contato acionável encontrado.',
  identity_needs_review: 'Identidade do decisor precisa de revisão humana.',
  routable_type_without_phone: 'Classificação roteável sem telefone registrado.',
  lead_blocked: 'Lead em opt-out, perdido ou fechado.',
};

const evidenceLabels: Record<string, string> = {
  verified_email: 'e-mail verificado',
  qualified_or_active_lead: 'lead no funil ativo',
  routability_type: 'roteabilidade classificada',
  routable: 'contato roteável',
  phone: 'telefone disponível',
  pabx: 'PABX',
  contact_found: 'contato encontrado',
  no_actionable_contact: 'sem contato acionável',
  verification_status: 'identidade sob revisão',
};

export function NextActionCard({ nextAction }: { nextAction?: Lead['next_best_action'] }) {
  if (!nextAction) return null;
  const meta = actionLabels[nextAction.action];
  const Icon = meta?.icon ?? Sparkles;
  const highPriority = nextAction.priority === 'HIGH';
  const evidences = (nextAction.evidence ?? [])
    .map((key) => evidenceLabels[key] ?? key)
    .slice(0, 3);

  return (
    <Card
      className={highPriority ? 'border-l-4 border-l-amber-500' : 'border-l-4 border-l-border'}
    >
      <CardContent className="pt-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Ação recomendada
          </span>
          <Badge
            className={highPriority ? 'bg-amber-100 text-amber-800' : 'bg-muted text-muted-foreground'}
          >
            {highPriority ? 'Prioridade alta' : 'Prioridade média'}
          </Badge>
        </div>
        <div className="mt-3 flex items-start gap-3">
          <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
          <div className="min-w-0 space-y-1">
            <p className="font-medium leading-snug">
              {meta?.label ?? nextAction.action}
            </p>
            <p className="text-sm text-muted-foreground">
              {reasonLabels[nextAction.why] ?? nextAction.why}
            </p>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge variant="outline">
            Confiança {Math.round(nextAction.confidence * 100)}%
          </Badge>
          {evidences.map((item) => (
            <Badge key={item} variant="outline" className="font-normal">
              {item}
            </Badge>
          ))}
          {nextAction.offer_key && (
            <Badge variant="outline" className="font-normal">
              Oferta: {nextAction.offer_key}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export type { NextBestAction };