'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Ban,
  Loader2,
  Mail,
  Phone,
  RefreshCw,
  Search,
  Sparkles,
  UserCheck,
} from 'lucide-react';
import { whatsAppLink } from '@/lib/utils';
import { offerProfileLabel } from '@/lib/offers';
import { useEnrichContacts } from '@/hooks/use-api';
import { toast } from 'sonner';
import type { Lead, NextBestAction } from '@/types/index';

const actionLabels: Record<string, { label: string; icon: typeof Mail }> = {
  START_EMAIL_CADENCE: { label: 'Enviar e-mails de acompanhamento', icon: Mail },
  CALL: { label: 'Ligar para o contato', icon: Phone },
  RESEARCH: { label: 'Buscar canal de contato', icon: Search },
  RE_ENRICH: { label: 'Enriquecer os dados do lead', icon: RefreshCw },
  REVIEW_DECISION_MAKER: { label: 'Revisar o decisor', icon: UserCheck },
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

// Telefone mais acionável: decisor principal, WhatsApp do lead ou primeiro contato com fone.
function bestPhone(lead: Lead): string | null {
  const primary = lead.contacts?.find((c) => c.is_primary)?.phone;
  if (primary) return primary;
  if (lead.whatsapp) return lead.whatsapp;
  if (lead.phone) return lead.phone;
  return lead.contacts?.find((c) => c.phone)?.phone ?? null;
}

interface NextActionCardProps {
  lead: Lead;
  nextAction?: Lead['next_best_action'];
  onOpenTab?: (tab: string) => void;
}

export function NextActionCard({ lead, nextAction, onOpenTab }: NextActionCardProps) {
  const enrichContacts = useEnrichContacts();

  if (!nextAction) {
    return (
      <Card className="border-l-4 border-l-border">
        <CardContent className="space-y-3 pt-6">
          <p className="font-medium leading-snug">Sem recomendação por enquanto</p>
          <p className="text-sm text-muted-foreground">
            Abra a aba Decisores e Contatos para conferir os dados da empresa.
          </p>
          <Button
            className="h-11"
            variant="outline"
            onClick={() => onOpenTab?.('contacts')}
          >
            Abrir contatos
          </Button>
        </CardContent>
      </Card>
    );
  }

  const meta = actionLabels[nextAction.action];
  const Icon = meta?.icon ?? Sparkles;
  const highPriority = nextAction.priority === 'HIGH';
  const evidences = (nextAction.evidence ?? [])
    .map((key) => evidenceLabels[key] ?? key)
    .slice(0, 3);

  const handleEnrich = () => {
    const cnpj = (lead.cnpj || '').trim();
    if (!cnpj) {
      toast.error('Informe o CNPJ na aba Contatos para buscar os sócios.');
      onOpenTab?.('contacts');
      return;
    }
    enrichContacts.mutate(
      { leadId: lead.id, cnpj },
      {
        onSuccess: (data) => toast.success(`Dados enriquecidos: ${data?.contacts?.length ?? 0} contato(s).`),
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao enriquecer.'),
      },
    );
  };

  const renderCta = () => {
    switch (nextAction.action) {
      case 'CALL': {
        const phone = bestPhone(lead);
        const waUrl = whatsAppLink(phone);
        if (waUrl) {
          return (
            <Button className="h-11" onClick={() => window.open(waUrl, '_blank')}>
              <Phone className="h-4 w-4" aria-hidden="true" />
              Ligar agora
            </Button>
          );
        }
        if (phone) {
          return (
            <Button className="h-11" render={<a href={`tel:${phone.replace(/\D/g, '')}`} />}>
              <Phone className="h-4 w-4" aria-hidden="true" />
              Ligar agora
            </Button>
          );
        }
        return (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Sem telefone cadastrado — abra os contatos para completar.
            </p>
            <Button className="h-11" variant="outline" onClick={() => onOpenTab?.('contacts')}>
              Abrir contatos
            </Button>
          </div>
        );
      }
      case 'START_EMAIL_CADENCE':
        return (
          <Button className="h-11" onClick={() => onOpenTab?.('cadence')}>
            <Mail className="h-4 w-4" aria-hidden="true" />
            Abrir acompanhamento
          </Button>
        );
      case 'RESEARCH':
        return (
          <Button className="h-11" onClick={() => onOpenTab?.('contacts')}>
            <Search className="h-4 w-4" aria-hidden="true" />
            Buscar contato
          </Button>
        );
      case 'RE_ENRICH':
        return (
          <Button className="h-11" onClick={handleEnrich} disabled={enrichContacts.isPending}>
            {enrichContacts.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
            )}
            Enriquecer agora
          </Button>
        );
      case 'REVIEW_DECISION_MAKER':
        return (
          <Button className="h-11" onClick={() => onOpenTab?.('contacts')}>
            <UserCheck className="h-4 w-4" aria-hidden="true" />
            Revisar decisor
          </Button>
        );
      case 'STOP':
        return (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Este lead está bloqueado (opt-out, perdido ou fechado). Confira o
              histórico com o gestor antes de retomar qualquer contato.
            </p>
            <Button className="h-11" variant="outline" onClick={() => onOpenTab?.('activities')}>
              Ver histórico
            </Button>
          </div>
        );
      default:
        return (
          <Button className="h-11" variant="outline" onClick={() => onOpenTab?.('actions')}>
            Ver próximos passos
          </Button>
        );
    }
  };

  return (
    <Card
      className={highPriority ? 'border-l-4 border-l-amber-500' : 'border-l-4 border-l-border'}
    >
      <CardContent className="space-y-3 pt-6">
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
              Oferta: {offerProfileLabel(nextAction.offer_key)}
            </Badge>
          )}
        </div>
        <div className="pt-1">{renderCta()}</div>
      </CardContent>
    </Card>
  );
}

export type { NextBestAction };
