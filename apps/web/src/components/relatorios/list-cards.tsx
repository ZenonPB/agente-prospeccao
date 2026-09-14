'use client';

import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import type { AnalyticsConsultant, AnalyticsCampaign, AnalyticsRankingItem } from '@/lib/api';
import { cn } from '@/lib/utils';

const STATUS_LABELS: Record<string, string> = {
  NOVO: 'Novo', ANALISADO: 'Analisado', QUALIFICADO: 'Apto', DESQUALIFICADO: 'Desqualificado',
  CONTATADO: 'Mensagem enviada', RESPONDIDO: 'Respondeu', REUNIAO_MARCADA: 'Reunião marcada',
  REUNIAO_FEITA: 'Reunião realizada', PROPOSTA_ENVIADA: 'Proposta enviada', PERDIDO: 'Perdido',
};

function attainmentColor(value: number): string {
  if (value >= 100) return 'text-emerald-600 dark:text-emerald-400';
  if (value >= 60) return 'text-amber-600 dark:text-amber-400';
  return 'text-destructive';
}

export function ConsultantsCard({ consultants, activeConsultantId, onConsultantFilter }: {
  consultants: AnalyticsConsultant[];
  activeConsultantId?: string;
  onConsultantFilter?: (id: string) => void;
}) {
  const maxAssigned = Math.max(1, ...consultants.map((c) => c.assigned_leads));
  return (
    <Card>
      <CardHeader><CardTitle>Desempenho por consultor</CardTitle><CardDescription>{onConsultantFilter ? 'Clique em um consultor para filtrar todos os indicadores.' : 'Atribuição, pitch, resposta e contrato'}</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        {consultants.length === 0 ? <p className="text-sm text-muted-foreground">Nenhum consultor no período.</p> : null}
        {consultants.map((c) => {
          const pct = (c.assigned_leads / maxAssigned) * 100;
          const hasTarget = c.meetings_target > 0 || c.revenue_target > 0;
          const selected = activeConsultantId === c.user_id;
          return (
            <div key={c.user_id} className={cn('rounded-lg border p-2', selected && 'border-primary/50 bg-primary/5')}>
              <button type="button" disabled={!onConsultantFilter} onClick={() => onConsultantFilter?.(c.user_id)} className="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2 text-sm"><span className="font-medium">{c.name || 'Sem nome'}</span><span className="text-muted-foreground">{c.converted_leads} convertido{c.converted_leads !== 1 ? 's' : ''} · {c.conversion_rate}%</span></div>
                  <div className="flex items-center gap-3"><div className="relative h-2 flex-1 overflow-hidden rounded-full bg-muted"><div className="absolute inset-y-0 left-0 rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} /></div><span className="w-24 text-right text-xs tabular-nums text-muted-foreground">{c.assigned_leads} atribuídos</span></div>
                  <p className="text-xs text-muted-foreground">{c.contacted_leads} contatados · {c.meetings} reuniões · {c.proposals_sent} propostas{c.revenue_realized > 0 ? ` · R$ ${c.revenue_realized.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : ''}</p>
                  {hasTarget ? <p className="flex flex-wrap gap-x-3 text-xs font-medium">{c.meetings_attainment != null ? <span className={attainmentColor(c.meetings_attainment)}>Reuniões: {c.meetings}/{c.meetings_target} ({c.meetings_attainment}%)</span> : null}{c.revenue_attainment != null ? <span className={attainmentColor(c.revenue_attainment)}>Receita: {c.revenue_attainment}% da meta</span> : null}</p> : null}
                </div>
              </button>
              <Link href={`/relatorios/consultores/${c.user_id}`} className="mt-1 inline-block text-xs text-primary hover:underline">Ver perfil detalhado</Link>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export function CampaignsCard({ campaigns, activeCampaignId, onCampaignFilter }: {
  campaigns: AnalyticsCampaign[];
  activeCampaignId?: string;
  onCampaignFilter?: (id: string) => void;
}) {
  const maxLeads = Math.max(1, ...campaigns.map((c) => c.leads));
  return (
    <Card><CardHeader><CardTitle>Campanhas</CardTitle><CardDescription>{onCampaignFilter ? 'Clique em uma campanha para cruzar o filtro.' : 'Resultado por campanha no período'}</CardDescription></CardHeader><CardContent className="space-y-3">
      {campaigns.length === 0 ? <p className="text-sm text-muted-foreground">Nenhuma campanha no período.</p> : null}
      {campaigns.map((c) => { const pct = (c.leads / maxLeads) * 100; const selected = activeCampaignId === c.id; return (
        <button key={c.id} type="button" disabled={!onCampaignFilter} onClick={() => onCampaignFilter?.(c.id)} className={cn('w-full space-y-1.5 rounded-lg p-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', onCampaignFilter && 'hover:bg-muted/40', selected && 'bg-primary/5 ring-1 ring-primary/40')} aria-pressed={onCampaignFilter ? selected : undefined}>
          <div className="flex items-center justify-between gap-2 text-sm"><span className="font-medium">{c.name}</span><span className="text-xs text-muted-foreground">{c.qualified_leads} aptos · {c.meetings} reuniões · {c.converted_leads} convertidos</span></div>
          <div className="relative h-2 overflow-hidden rounded-full bg-muted"><div className="absolute inset-y-0 left-0 rounded-full bg-primary" style={{ width: `${pct}%` }} /></div>
          <div className="flex justify-between text-xs text-muted-foreground"><span>{c.leads} leads</span><span>conv. {c.conversion_rate}% · {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(c.revenue)}</span></div>
        </button>
      ); })}
    </CardContent></Card>
  );
}

export function TopLeadsCard({ leads }: { leads: AnalyticsRankingItem[] }) {
  return <Card><CardHeader><CardTitle>Melhores oportunidades</CardTitle><CardDescription>Leads com maior score no período</CardDescription></CardHeader><CardContent className="space-y-2">{leads.length === 0 ? <p className="text-sm text-muted-foreground">Nenhum lead no período.</p> : null}{leads.map((lead, i) => <Link key={lead.id} href={`/oportunidades/${lead.id}`} className="flex items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/40"><span className="w-6 text-center text-sm font-bold text-muted-foreground">{i + 1}</span><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{lead.company_name}</p><p className="truncate text-xs text-muted-foreground">{lead.city || 'Sem cidade'}{lead.state ? `, ${lead.state}` : ''}{lead.assigned_to_name ? ` · ${lead.assigned_to_name}` : ''}</p></div><div className="text-right"><span className="inline-flex min-w-9 justify-center rounded-md bg-emerald-100 px-1.5 py-0.5 text-sm font-bold text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">{lead.qualification_score}</span><p className="mt-0.5 text-[11px] text-muted-foreground">{STATUS_LABELS[lead.status] || lead.status}</p></div></Link>)}</CardContent></Card>;
}

export function ListCardSkeleton() { return <Card><CardHeader><Skeleton className="h-5 w-40" /><Skeleton className="h-4 w-56" /></CardHeader><CardContent className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="space-y-1.5"><div className="flex justify-between"><Skeleton className="h-4 w-40" /><Skeleton className="h-4 w-16" /></div><Skeleton className="h-2 w-full rounded-full" /></div>)}</CardContent></Card>; }
