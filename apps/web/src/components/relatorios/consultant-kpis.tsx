'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import type { AnalyticsConsultantDetail } from '@/lib/api';

const STAGE_LABELS: Record<string, string> = { RD: 'RD', ORCAMENTO: 'Orçamento', RP: 'RP' };
const OUTCOME_LABELS: Record<string, string> = {
  APROVADO: 'Aprovado', REPROVADO: 'Reprovado', EM_ANALISE: 'Em análise',
};
const CHANNEL_LABELS: Record<string, string> = {
  EMAIL: 'E-mail', WHATSAPP: 'WhatsApp', LINKEDIN: 'LinkedIn',
};

function KpiCard({
  label,
  value,
  suffix,
  hint,
}: {
  label: string;
  value: string;
  suffix?: string;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
        <p className="mt-1 font-heading text-xl font-bold tracking-tight">
          {value}
          {suffix && <span className="ml-0.5 text-sm font-medium text-muted-foreground">{suffix}</span>}
        </p>
        {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

function fmtBRL(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
}

export function ConsultantKpis({ detail }: { detail: AnalyticsConsultantDetail }) {
  const closeN = detail.close_days_n || 0;
  const cadN = detail.cadence_days_n || 0;
  return (
    <section className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard label="Leads em carteira" value={String(detail.assigned_leads)} />
        <KpiCard label="Pitch enviado" value={`${detail.pitch_rate}%`} hint={`${detail.pitch_sent} de ${detail.assigned_leads}`} />
        <KpiCard label="Resposta" value={`${detail.response_rate}%`} hint={`${detail.responded_leads} responderam`} />
        <KpiCard label="Contrato aprovado" value={`${detail.contract_approval_rate}%`} hint={`${detail.contracts_approved} de ${detail.contracts_total}`} />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard label="Ticket médio" value={fmtBRL(detail.ticket_medio)} hint={`${detail.ticket_count} conversões`} />
        <KpiCard
          label="Cadência (pitch→resposta)"
          value={detail.avg_cadence_days > 0 ? `${detail.avg_cadence_days}` : '—'}
          suffix={detail.avg_cadence_days > 0 ? ' dias' : ''}
          hint={cadN > 0 ? `média de ${cadN} leads` : 'sem resposta no período'}
        />
        <KpiCard
          label="Tempo até fechar"
          value={detail.avg_close_days > 0 ? `${detail.avg_close_days}` : '—'}
          suffix={detail.avg_close_days > 0 ? ' dias' : ''}
          hint={closeN > 0 ? `média de ${closeN} conversões` : 'sem conversão no período'}
        />
        <KpiCard label="Canal de contato" value="—" hint={
          detail.channel_distribution.map((c) => `${CHANNEL_LABELS[c.channel] ?? c.channel}: ${c.count}`).join(' · ')
        } />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Funil de negociação (RD / Orçamento / RP)</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {detail.negotiation_distribution.map((n) => (
              <Badge key={n.stage} variant="outline" className="bg-violet-50 text-violet-700 text-xs">
                {STAGE_LABELS[n.stage] ?? n.stage}: {n.count}
              </Badge>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Resultado de contrato</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {detail.contracts_by_outcome.map((o) => (
              <Badge
                key={o.outcome}
                variant="outline"
                className={
                  o.outcome === 'APROVADO'
                    ? 'bg-emerald-50 text-emerald-700 text-xs'
                    : o.outcome === 'REPROVADO'
                      ? 'bg-red-50 text-red-700 text-xs'
                      : 'bg-amber-50 text-amber-700 text-xs'
                }
              >
                {OUTCOME_LABELS[o.outcome] ?? o.outcome}: {o.count}
              </Badge>
            ))}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

export function ConsultantKpisSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {[1, 2, 3, 4].map((i) => (
        <Card key={i}>
          <CardContent className="p-4">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-2 h-6 w-16" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}