'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, CheckCircle, AlertTriangle, Info, User, Building, Search, Globe } from 'lucide-react';
import { LinkedInIcon } from '@/components/ui/linkedin-icon';
import { useLeadPitch } from '@/hooks/use-api';
import type { PitchOnePager, SiteAudit, SiteAuditSection } from '@/types';

const priorityBadgeConfig: Record<string, { label: string; color: string }> = {
  HOT: { label: 'Quente', color: 'bg-red-100 text-red-700' },
  WARM: { label: 'Morno', color: 'bg-amber-100 text-amber-700' },
  COLD: { label: 'Frio', color: 'bg-sky-100 text-sky-700' },
};

function StatusIcon({ status }: { status: string }) {
  if (status === 'ok') return <CheckCircle className="h-4 w-4 text-emerald-600" />;
  if (status === 'warning') return <AlertTriangle className="h-4 w-4 text-amber-600" />;
  return <Info className="h-4 w-4 text-slate-500" />;
}

function SiteAuditCard({ audit }: { audit: SiteAudit }) {
  if (!audit.available) {
    return (
      <Card>
        <CardHeader><CardTitle>Auditoria do Site</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{audit.summary}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Auditoria do Site</CardTitle>
          <Badge variant="outline" className={
            audit.overall_status === 'OK' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
            audit.overall_status === 'PROBLEMA' ? 'bg-amber-50 text-amber-700 border-amber-200' :
            'bg-red-50 text-red-700 border-red-200'
          }>
            {audit.overall_status === 'OK' ? 'Sem problemas' :
             audit.overall_status === 'PROBLEMA' ? 'Atenção' : 'Falha'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">{audit.summary}</p>
        <div className="space-y-3">
          {audit.sections.map((section: SiteAuditSection, i: number) => (
            <div key={i} className="rounded-lg border p-3">
              <div className="flex items-center gap-2 mb-1">
                <StatusIcon status={section.status} />
                <span className="text-sm font-medium">{section.title}</span>
              </div>
              <p className="text-sm text-muted-foreground ml-6">{section.detail}</p>
              {section.items && section.items.length > 0 && (
                <ul className="mt-2 ml-6 space-y-0.5">
                  {section.items.map((item: string, j: number) => (
                    <li key={j} className="text-xs text-muted-foreground">- {item}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function PitchCard({ pitch }: { pitch: PitchOnePager }) {
  const { identity, qualification, campaign, executive_summary, score_factors } = pitch;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Pitch One-Pager</CardTitle>
            <div className="flex items-center gap-2">
              <Badge className="bg-emerald-100 text-emerald-700 text-lg">{qualification.score}</Badge>
              {qualification.priority && priorityBadgeConfig[qualification.priority] && (
                <Badge className={priorityBadgeConfig[qualification.priority].color}>
                  {priorityBadgeConfig[qualification.priority].label}
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {campaign && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Search className="h-4 w-4" />
              <span>{campaign.name} — {campaign.target_service} / {campaign.target_segment}</span>
            </div>
          )}

          {executive_summary && (
            <div className="rounded-lg border bg-muted/30 p-4">
              <p className="text-sm font-medium text-muted-foreground mb-1">Resumo executivo</p>
              <p className="text-sm">{executive_summary}</p>
            </div>
          )}

          {(pitch.pitch.pitch_angle || pitch.pitch.suggested_subject) && (
            <div className="space-y-2">
              {pitch.pitch.pitch_angle && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Gancho de abordagem</p>
                  <p className="text-sm mt-0.5">{pitch.pitch.pitch_angle}</p>
                </div>
              )}
              {pitch.pitch.suggested_subject && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Assunto sugerido</p>
                  <p className="text-sm mt-0.5 italic">&ldquo;{pitch.pitch.suggested_subject}&rdquo;</p>
                </div>
              )}
            </div>
          )}

          {qualification.primary_need && (
            <div>
              <p className="text-sm font-medium text-muted-foreground">Necessidade primária</p>
              <p className="text-sm mt-0.5">{qualification.primary_need}</p>
            </div>
          )}

          {qualification.qualification_reason && (
            <div>
              <p className="text-sm font-medium text-muted-foreground">Por que este lead é uma oportunidade</p>
              <p className="text-sm mt-0.5">{qualification.qualification_reason}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">Identidade</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <Building className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">{identity.company_name}</span>
            </div>
            {identity.razao_social && identity.razao_social !== identity.company_name && (
              <p className="ml-6 text-muted-foreground">{identity.razao_social}</p>
            )}
            {identity.cnpj && <p className="ml-6 text-muted-foreground">CNPJ: {identity.cnpj}</p>}
            {identity.porte && <p className="ml-6 text-muted-foreground">Porte: {identity.porte}</p>}
            {identity.cnae_principal && <p className="ml-6 text-muted-foreground">CNAE: {identity.cnae_principal}</p>}
            {identity.idade_anos != null && <p className="ml-6 text-muted-foreground">{identity.idade_anos} anos de atividade</p>}
            {identity.capital_social != null && (
              <p className="ml-6 text-muted-foreground">
                Capital social: R$ {identity.capital_social.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
              </p>
            )}
            {identity.website && (
              <div className="flex items-center gap-2 ml-6">
                <Globe className="h-3.5 w-3.5 text-muted-foreground" />
                <a href={identity.website} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">{identity.website}</a>
              </div>
            )}
            {identity.company_linkedin_url && (
              <div className="flex items-center gap-2 ml-6">
                <LinkedInIcon className="h-3.5 w-3.5 text-primary" />
                <a href={identity.company_linkedin_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">
                  Empresa no LinkedIn
                </a>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Contato principal</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            {pitch.primary_contact ? (
              <>
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{pitch.primary_contact.name}</span>
                </div>
                {pitch.primary_contact.role && <p className="ml-6 text-muted-foreground">{pitch.primary_contact.role}</p>}
                {pitch.primary_contact.email && <p className="ml-6 text-muted-foreground">{pitch.primary_contact.email}</p>}
                {pitch.primary_contact.phone && <p className="ml-6 text-muted-foreground">{pitch.primary_contact.phone}</p>}
                {pitch.primary_contact.linkedin_url && (
                  <a
                    href={pitch.primary_contact.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-6 flex items-center gap-1.5 text-primary hover:underline"
                  >
                    <LinkedInIcon className="h-4 w-4" />
                    Ver perfil no LinkedIn
                  </a>
                )}
              </>
            ) : (
              <p className="text-muted-foreground">Nenhum contato identificado ainda.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {(score_factors.positive.length > 0 || score_factors.negative.length > 0) && (
        <Card>
          <CardHeader><CardTitle className="text-base">Fatores de qualificacao</CardTitle></CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-sm font-medium mb-2 text-emerald-700">Positivos</p>
                {score_factors.positive.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Nenhum</p>
                ) : (
                  <ul className="space-y-1.5">
                    {score_factors.positive.map((f, i) => (
                      <li key={i} className="flex gap-2 text-sm">
                        <span className="text-emerald-600 font-bold">+</span>
                        <div>
                          <span className="font-medium">{f.label}</span>
                          <p className="text-xs text-muted-foreground">{f.rationale}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <p className="text-sm font-medium mb-2 text-red-700">Negativos</p>
                {score_factors.negative.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Nenhum</p>
                ) : (
                  <ul className="space-y-1.5">
                    {score_factors.negative.map((f, i) => (
                      <li key={i} className="flex gap-2 text-sm">
                        <span className="text-red-600 font-bold">&minus;</span>
                        <div>
                          <span className="font-medium">{f.label}</span>
                          <p className="text-xs text-muted-foreground">{f.rationale}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {pitch.evidence.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Evidencias</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {pitch.evidence.map((ev, i) => (
              <div key={i} className="rounded-lg border p-3 space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{ev.title}</span>
                  <Badge variant="outline" className={
                    ev.severity === 'CRITICO' ? 'bg-red-50 text-red-700 border-red-200' :
                    ev.severity === 'ALTO' ? 'bg-orange-50 text-orange-700 border-orange-200' :
                    ev.severity === 'MEDIO' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                    ev.severity === 'BAIXO' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                    'bg-slate-50 text-slate-700 border-slate-200'
                  }>{ev.severity}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">{ev.description}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {pitch.site_audit && <SiteAuditCard audit={pitch.site_audit} />}
    </div>
  );
}

export function LeadPitchTab({ leadId }: { leadId: string }) {
  const { data: pitch, isLoading, error } = useLeadPitch(leadId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !pitch) {
    return (
      <Card>
        <CardContent className="py-8">
          <p className="text-sm text-muted-foreground text-center">
            Nenhum dado de pitch disponivel para este lead. Execute o pipeline de analise primeiro.
          </p>
        </CardContent>
      </Card>
    );
  }

  return <PitchCard pitch={pitch} />;
}
