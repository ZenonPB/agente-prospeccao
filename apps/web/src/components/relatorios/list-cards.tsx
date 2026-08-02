'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertCircle } from 'lucide-react';
import type { AnalyticsConsultant, AnalyticsCampaign, AnalyticsRankingItem } from '@/lib/api';

const STATUS_LABELS: Record<string, string> = {
  NOVO: 'Novo', ANALISADO: 'Analisado', QUALIFICADO: 'Apto', DESQUALIFICADO: 'Desqualificado',
  CONTATADO: 'Mensagem enviada', RESPONDIDO: 'Respondeu', REUNIAO_MARCADA: 'Reunião marcada',
  REUNIAO_FEITA: 'Reunião realizada', PROPOSTA_ENVIADA: 'Proposta enviada', PERDIDO: 'Perdido',
};

export function ConsultantsCard({ consultants }: { consultants: AnalyticsConsultant[] }) {
  const maxAssigned = Math.max(1, ...consultants.map((c) => c.assigned_leads));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Desempenho por consultor</CardTitle>
        <CardDescription>Atribuição, contato e conversão de cada vendedor</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {consultants.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhum consultor no período.</p>
        )}
        {consultants.map((c) => {
          const pct = (c.assigned_leads / maxAssigned) * 100;
          return (
            <div key={c.user_id} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{c.name || 'Sem nome'}</span>
                <span className="text-muted-foreground">
                  {c.converted_leads} convertido{c.converted_leads !== 1 ? 's' : ''} · {c.conversion_rate}%
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full bg-primary transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-24 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                  {c.assigned_leads} atribuídos
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {c.contacted_leads} contatados · {c.meetings} reuniões · {c.proposals_sent} propostas
              </p>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export function CampaignsCard({ campaigns }: { campaigns: AnalyticsCampaign[] }) {
  const maxLeads = Math.max(1, ...campaigns.map((c) => c.leads));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Campanhas</CardTitle>
        <CardDescription>Resultado por campanha no período</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {campaigns.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhuma campanha no período.</p>
        )}
        {campaigns.map((c) => {
          const pct = (c.leads / maxLeads) * 100;
          return (
            <div key={c.id} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{c.name}</span>
                <span className="text-xs text-muted-foreground">
                  {c.qualified_leads} aptos · {c.meetings} reuniões · {c.converted_leads} convertidos
                </span>
              </div>
              <div className="relative h-2 overflow-hidden rounded-full bg-muted">
                <div className="absolute inset-y-0 left-0 rounded-full bg-primary" style={{ width: `${pct}%` }} />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{c.leads} leads</span>
                <span>conv. {c.conversion_rate}% · {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(c.revenue)}</span>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export function TopLeadsCard({ leads }: { leads: AnalyticsRankingItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Melhores oportunidades</CardTitle>
        <CardDescription>Leads com maior score no período</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {leads.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhum lead no período.</p>
        )}
        {leads.map((lead, i) => (
          <div key={lead.id} className="flex items-center gap-3 rounded-lg border p-3">
            <span className="w-6 shrink-0 text-center text-sm font-bold text-muted-foreground">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{lead.company_name}</p>
              <p className="truncate text-xs text-muted-foreground">
                {lead.city || 'Sem cidade'}{lead.state ? `, ${lead.state}` : ''}
                {lead.assigned_to_name ? ` · ${lead.assigned_to_name}` : ''}
              </p>
            </div>
            <div className="text-right">
              <span className="inline-flex min-w-9 justify-center rounded-md bg-emerald-100 px-1.5 py-0.5 text-sm font-bold text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                {lead.qualification_score}
              </span>
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                {STATUS_LABELS[lead.status] || lead.status}
              </p>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function ListCardSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-4 w-56" />
      </CardHeader>
      <CardContent className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-1.5">
            <div className="flex justify-between">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-4 w-16" />
            </div>
            <Skeleton className="h-2 w-full rounded-full" />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function ListCardError({ title, message }: { title: string; message: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 text-red-600">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="text-sm font-medium">Erro ao carregar</p>
        </div>
        <p className="mt-1 text-xs text-red-500">{message}</p>
      </CardContent>
    </Card>
  );
}
