'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Mail, Phone, UserPlus, Loader2, ShieldCheck, ShieldAlert } from 'lucide-react';
import { LinkedInIcon } from '@/components/ui/linkedin-icon';
import { useEnrichContacts } from '@/hooks/use-api';
import { toast } from 'sonner';
import type { ContactItem, Lead } from '@/types';

const LINKEDIN_MATCH_META: Record<NonNullable<ContactItem['linkedin_match_status']>, { label: string; className: string }> = {
  NOT_FOUND: { label: 'Não encontrado', className: '' },
  CANDIDATE: { label: 'Candidato', className: 'border-slate-200 bg-slate-50 text-slate-600' },
  NEEDS_REVIEW: { label: 'Revisar', className: 'border-amber-200 bg-amber-50 text-amber-700' },
  VERIFIED: { label: 'Confirmado', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
};

const emailSourceLabels: Record<string, string> = {
  hunter: 'Hunter',
  site: 'Site',
  'search:duckduckgo': 'Busca (DuckDuckGo)',
  'search:bing': 'Busca (Bing)',
  'search:cached': 'Busca (cache)',
  search: 'Busca',
  cnpj: 'CNPJ/Receita',
  heuristic: 'Padrão (heurística)',
  cnpj_receita: 'CNPJ/Receita',
};

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
}

export function ContactsTab({ lead }: ContactsTabProps) {
  const enrichContacts = useEnrichContacts();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>Contatos de decisores</CardTitle>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            enrichContacts.mutate({ leadId: lead.id }, {
              onSuccess: () => toast.success('Decisores enriquecidos (e-mail/LinkedIn).'),
              onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao enriquecer contatos.'),
            });
          }}
          disabled={enrichContacts.isPending}
        >
          {enrichContacts.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <UserPlus className="mr-2 h-4 w-4" aria-hidden="true" />
          )}
          Enriquecer decisores
        </Button>
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
                  {contact.confidence != null && (
                    <Badge className={contact.confidence >= 50 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>
                      Confiança {contact.confidence}
                    </Badge>
                  )}
                </div>

                <div className="mt-3 space-y-2 text-sm">
                  {contact.email && (
                    <div className="flex items-center gap-2">
                      <Mail className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                      <a href={`mailto:${contact.email}`} className="text-primary hover:underline">{contact.email}</a>
                      {contact.email_verified ? (
                        <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" aria-label="E-mail verificado" />
                      ) : (
                        <ShieldAlert className="h-3.5 w-3.5 text-amber-500" aria-label="E-mail não verificado" />
                      )}
                      {formatEmailSource(contact.raw_data) && (
                        <span className="text-xs text-muted-foreground">({formatEmailSource(contact.raw_data)})</span>
                      )}
                    </div>
                  )}
                  {contact.phone && (
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                      <a href={`tel:${contact.phone}`} className="text-primary hover:underline">{contact.phone}</a>
                    </div>
                  )}
                  {contact.linkedin_url && (
                    <div className="flex items-center gap-2">
                      <LinkedInIcon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                      <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                        LinkedIn
                      </a>
                      {contact.linkedin_match_status && contact.linkedin_match_status !== 'NOT_FOUND' && (
                        <Badge variant="outline" className={`text-[10px] ${LINKEDIN_MATCH_META[contact.linkedin_match_status]?.className || ''}`}>
                          {LINKEDIN_MATCH_META[contact.linkedin_match_status]?.label || contact.linkedin_match_status}
                        </Badge>
                      )}
                      {formatLinkedinSource(contact.raw_data) && (
                        <span className="text-xs text-muted-foreground">({formatLinkedinSource(contact.raw_data)})</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Nenhum contato de decisor encontrado. Clique em &ldquo;Enriquecer decisores&rdquo; para buscar automaticamente.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
