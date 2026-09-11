'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Mail,
  Phone,
  UserPlus,
  UserCheck,
  Loader2,
  Copy,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import { LinkedInIcon } from '@/components/ui/linkedin-icon';
import { useEnrichContacts } from '@/hooks/use-api';
import { toast } from 'sonner';
import { useState } from 'react';
import { Input } from '@/components/ui/input';
import type { ContactItem, Lead } from '@/types';

// Estado de match do LinkedIn derivado da fonte/confiança (ver
// linkedin_match_status na API). NOT_FOUND não ganha badge — o bloco
// "Associar perfil" já aparece no lugar.
const LINKEDIN_MATCH_META: Record<NonNullable<ContactItem['linkedin_match_status']>, { label: string; className: string }> = {
  NOT_FOUND: { label: 'Não encontrado', className: '' },
  CANDIDATE: { label: 'Candidato', className: 'border-slate-200 bg-slate-50 text-slate-600' },
  NEEDS_REVIEW: { label: 'Revisar', className: 'border-amber-200 bg-amber-50 text-amber-700' },
  VERIFIED: { label: 'Confirmado', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
};

// Proveniência do e-mail do decisor (onde foi encontrado).
const emailSourceLabels: Record<string, string> = {
  hunter: 'Hunter',
  site: 'Site',
  'search:duckduckgo': 'Busca (DuckDuckGo)',
  'search:bing': 'Busca (Bing)',
  'search:cached': 'Busca (cache)',
  search: 'Busca',
  cnpj: 'CNPJ/Receita',
  heuristic: 'Inferido (não confirmado)',
  cnpj_receita: 'CNPJ/Receita',
};

// Faixa de confiança em linguagem simples (0–100).
function confidenceBand(value?: number | null): { label: string; className: string } {
  if (value == null) return { label: 'Sem avaliação', className: 'bg-slate-100 text-slate-600' };
  if (value < 40) return { label: 'Confiança baixa', className: 'bg-red-100 text-red-700' };
  if (value < 70) return { label: 'Confiança média', className: 'bg-amber-100 text-amber-700' };
  return { label: 'Confiança alta', className: 'bg-emerald-100 text-emerald-700' };
}

// Origem do contato em PT.
function formatContactSource(source?: string | null): string | null {
  if (!source) return null;
  const key = source.toLowerCase();
  if (key.includes('heuristic')) return 'Inferido (não confirmado)';
  if (key.includes('cnpj') || key.includes('receita')) return 'Receita Federal (CNPJ)';
  if (key.includes('hunter')) return 'Hunter';
  if (key.includes('company_site') || key === 'site') return 'Site da empresa';
  if (key.includes('linkedin')) return 'LinkedIn';
  if (key.includes('search')) return 'Busca pública';
  if (key.includes('manual')) return 'Associado manualmente';
  return source;
}

// Selo confirmado vs inferido a partir do status de verificação.
function verificationSeal(contact: ContactItem): { label: string; confirmed: boolean } {
  if (contact.email_verified) return { label: 'Confirmado', confirmed: true };
  const status = (contact.verification_status || '').toLowerCase();
  if (status === 'fully_verified' || status === 'verified') return { label: 'Confirmado', confirmed: true };
  if (status === 'email_verified_no_identity') return { label: 'E-mail confirmado', confirmed: true };
  if (status === 'identity_verified_no_email') return { label: 'Identidade confirmada', confirmed: true };
  if (status === 'pending_real_check' || status === 'pending_verification') return { label: 'Aguardando confirmação', confirmed: false };
  if (status === 'needs_review') return { label: 'Precisa de revisão', confirmed: false };
  if (!status || status === 'unknown' || status === 'needs_full_name') return { label: 'Não confirmado', confirmed: false };
  return { label: 'Inferido (não confirmado)', confirmed: false };
}

function formatEmailSource(rawData: unknown): string | null {
  if (typeof rawData !== 'object' || rawData === null) return null;
  const source = (rawData as Record<string, unknown>).email_source;
  if (typeof source !== 'string' || !source) return null;
  return emailSourceLabels[source] || source;
}

function formatLinkedinSource(rawData: unknown): string | null {
  if (typeof rawData !== 'object' || rawData === null) return null;
  const source = (rawData as Record<string, unknown>).linkedin_source;
  if (typeof source === 'string' && source.startsWith('manual')) return 'Associado manualmente';
  return null;
}

interface ContactsTabProps {
  lead: Lead;
  onAssociate: (contact: ContactItem) => void;
}

export function ContactsTab({ lead, onAssociate }: ContactsTabProps) {
  const enrichContacts = useEnrichContacts();
  const [cnpjInput, setCnpjInput] = useState(lead.cnpj ?? '');
  const needsCnpj = !lead.cnpj;

  const copyToClipboard = (text: string, message: string) => {
    navigator.clipboard.writeText(text);
    toast.success(message);
  };

  const handleEnrich = () => {
    const cnpj = (lead.cnpj || cnpjInput).trim();
    if (!cnpj) {
      toast.error('Informe o CNPJ da empresa para buscar os sócios na Receita Federal.');
      return;
    }
    enrichContacts.mutate({ leadId: lead.id, cnpj }, {
      onSuccess: (data) => {
        const count = data?.contacts?.length ?? 0;
        if (count === 0) {
          toast.warning(
            'Nenhum decisor encontrado. Confira o CNPJ ou complete os dados da empresa — a busca usa a Receita Federal e fontes públicas.'
          );
        } else {
          toast.success(`Decisores enriquecidos: ${count} contato(s) (e-mail/LinkedIn).`);
        }
      },
      onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao enriquecer contatos.'),
    });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 gap-2">
        <CardTitle>Contatos de decisores</CardTitle>
        <div className="flex items-center gap-2">
          {needsCnpj && (
            <Input
              placeholder="CNPJ da empresa"
              value={cnpjInput}
              onChange={(e) => setCnpjInput(e.target.value)}
              className="h-8 w-40 text-xs"
              aria-label="CNPJ da empresa"
            />
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={handleEnrich}
            disabled={enrichContacts.isPending}
            title={needsCnpj ? 'Informe o CNPJ para buscar os sócios na Receita Federal' : 'Buscar sócios via Receita Federal e enriquecer com e-mail e LinkedIn'}
          >
            {enrichContacts.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <UserPlus className="mr-2 h-4 w-4" aria-hidden="true" />
            )}
            Enriquecer decisores
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {lead.contacts && lead.contacts.length > 0 ? (
          <div className="space-y-3">
            {lead.contacts.map((contact) => (
              <div key={contact.id} className="rounded-lg border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium">{contact.name}</p>
                      {contact.is_primary && (
                        <Badge variant="secondary" className="text-[10px] font-normal">Principal</Badge>
                      )}
                    </div>
                    {contact.role_label && (
                      <p className="text-xs text-muted-foreground">{contact.role_label}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-1.5 shrink-0 max-w-[220px]">
                    {(() => {
                      const identity = confidenceBand(contact.identity_confidence);
                      const contactBand = confidenceBand(contact.contact_confidence ?? contact.confidence);
                      const seal = verificationSeal(contact);
                      const source = formatContactSource(contact.source);
                      return (
                        <>
                          <Badge className={`${identity.className} text-[10px] font-normal`} title="Quanto confiamos que esta pessoa é quem diz ser">
                            Pessoa: {identity.label.replace('Confiança ', '').toLowerCase()}
                          </Badge>
                          <Badge className={`${contactBand.className} text-[10px] font-normal`} title="Quanto confiamos que este contato chega até a pessoa">
                            Contato: {contactBand.label.replace('Confiança ', '').toLowerCase()}
                          </Badge>
                          <Badge
                            variant="outline"
                            className={`text-[10px] font-normal gap-1 ${seal.confirmed ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}
                          >
                            {seal.confirmed
                              ? <ShieldCheck className="h-3 w-3 text-emerald-500" aria-hidden="true" />
                              : <ShieldAlert className="h-3 w-3 text-amber-500" aria-hidden="true" />}
                            {seal.label}
                          </Badge>
                          {source && (
                            <Badge variant="outline" className="text-[10px] font-normal text-muted-foreground">
                              Origem: {source}
                            </Badge>
                          )}
                        </>
                      );
                    })()}
                  </div>
                </div>

                <div className="mt-3 space-y-2 text-sm">
                  {contact.email && (
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <Mail className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      <a href={`mailto:${contact.email}`} className="min-w-0 break-all text-primary hover:underline">{contact.email}</a>
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => copyToClipboard(contact.email || '', 'E-mail copiado.')} aria-label="Copiar e-mail">
                        <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                      </Button>
                      {contact.email_verified ? (
                        <Badge variant="outline" className="text-[10px] font-normal gap-1">
                          <ShieldCheck className="h-3 w-3 text-emerald-500" aria-hidden="true" />
                          E-mail verificado
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px] font-normal gap-1">
                          <ShieldAlert className="h-3 w-3 text-amber-500" aria-hidden="true" />
                          Não verificado
                        </Badge>
                      )}
                      {formatEmailSource(contact.raw_data) && (
                        <Badge variant="outline" className="text-[10px] font-normal text-muted-foreground">
                          Fonte: {formatEmailSource(contact.raw_data)}
                        </Badge>
                      )}
                    </div>
                  )}
                  {contact.phone && (
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                      <span>{contact.phone}</span>
                    </div>
                  )}
                  {contact.linkedin_url ? (
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <LinkedInIcon className="h-4 w-4 shrink-0 text-primary" />
                      <a
                        href={contact.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="min-w-0 max-w-full break-all text-primary hover:underline"
                      >
                        {contact.linkedin_url}
                      </a>
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => copyToClipboard(contact.linkedin_url || '', 'Link do LinkedIn copiado.')} aria-label="Copiar LinkedIn">
                        <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                      </Button>
                      {contact.linkedin_match_status && contact.linkedin_match_status !== 'NOT_FOUND' ? (
                        <Badge variant="outline" className={`text-[10px] font-normal gap-1 ${LINKEDIN_MATCH_META[contact.linkedin_match_status].className}`}>
                          {contact.linkedin_match_status === 'VERIFIED' && <ShieldCheck className="h-3 w-3 text-emerald-500" aria-hidden="true" />}
                          {contact.linkedin_match_status === 'NEEDS_REVIEW' && <ShieldAlert className="h-3 w-3 text-amber-500" aria-hidden="true" />}
                          {contact.linkedin_match_status === 'CANDIDATE' && <UserCheck className="h-3 w-3 text-slate-500" aria-hidden="true" />}
                          {LINKEDIN_MATCH_META[contact.linkedin_match_status].label}
                        </Badge>
                      ) : null}
                      {formatLinkedinSource(contact.raw_data) && (
                        <Badge variant="outline" className="text-[10px] font-normal text-muted-foreground">
                          {formatLinkedinSource(contact.raw_data)}
                        </Badge>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center justify-between gap-2">
                      <p className="flex items-center gap-2 text-xs text-muted-foreground">
                        <LinkedInIcon className="h-4 w-4" />
                        LinkedIn não encontrado.
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 gap-1 text-[11px]"
                        onClick={() => onAssociate(contact)}
                      >
                        <UserPlus className="h-3 w-3" aria-hidden="true" />
                        Associar perfil
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <UserPlus className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground max-w-sm">
              Nenhum contato de decisor cadastrado ainda. Use &quot;Enriquecer decisores&quot; para buscar
              sócios via Receita Federal e enriquecer com e-mail e LinkedIn (busca passiva).
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
