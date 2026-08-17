'use client';

import { use, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, AlertTriangle, Loader2, ShieldAlert } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import { useOrgMembership } from '@/hooks/use-api';
import {
  useAnalyticsConsultantDetail,
  useAnalyticsConsultantActivity,
  useLeads,
  type AnalyticsPeriod,
} from '@/hooks/use-api';
import { SalesRoleBadge } from '@/components/sales/sales-role-badge';
import { ConsultantKpis, ConsultantKpisSkeleton } from '@/components/relatorios/consultant-kpis';
import { FunnelEndToEndCard, FunnelEndToEndSkeleton } from '@/components/relatorios/funnel-e2e-card';

const STATUS_LABELS: Record<string, string> = {
  NOVO: 'Novo', ANALISADO: 'Analisado', QUALIFICADO: 'Apto', DESQUALIFICADO: 'Desqualificado',
  CONTATADO: 'Contatado', RESPONDIDO: 'Respondeu', REUNIAO_MARCADA: 'Reunião',
  REUNIAO_FEITA: 'Reunião realizada', PROPOSTA_ENVIADA: 'Proposta enviada', PERDIDO: 'Perdido',
};

const ACTIVITY_LABELS: Record<string, string> = {
  CREATED: 'Lead criado', ASSIGNED: 'Atribuído', UNASSIGNED: 'Desatribuído',
  STATUS_CHANGED: 'Status alterado', MESSAGE_GENERATED: 'Mensagem gerada',
  CONTACTED: 'Contato realizado', RESPONDED: 'Respondeu', MEETING_SCHEDULED: 'Reunião marcada',
  PROPOSAL_SENT: 'Proposta enviada', LOST: 'Perdido', CONVERTED: 'Convertido',
  CONTACT_ENRICHED: 'Contatos enriquecidos', NEGOTIATION_UPDATED: 'Negociação atualizada',
  POST_SALE: 'Pós-venda', WHATSAPP_SENT: 'WhatsApp acionado', LINKEDIN_ASSOCIATED: 'LinkedIn associado',
};

type PresetKey = '30d' | '90d' | 'all';

function PeriodPresets({
  value,
  onChange,
  period,
}: {
  value: PresetKey;
  onChange: (key: PresetKey, p: AnalyticsPeriod) => void;
  period: AnalyticsPeriod;
}) {
  const isoDaysAgo = (days: number) => {
    const d = new Date();
    d.setDate(d.getDate() - days);
    return d.toISOString().slice(0, 10);
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-medium text-muted-foreground">Período:</span>
      {([
        { key: '30d', label: '30 dias', days: 30 },
        { key: '90d', label: '90 dias', days: 90 },
        { key: 'all', label: 'Tudo', days: 0 },
      ] as { key: PresetKey; label: string; days: number }[]).map((p) => {
        const active = value === p.key && (p.days === 0 ? !period.from && !period.to : Boolean(period.from && period.to));
        return (
          <Button
            key={p.key}
            variant="outline"
            size="sm"
            className={active ? 'bg-primary text-primary-foreground' : ''}
            onClick={() => {
              if (p.days === 0) {
                onChange('all', {});
              } else {
                onChange(p.key, { from: isoDaysAgo(p.days), to: isoDaysAgo(0) });
              }
            }}
          >
            {p.label}
          </Button>
        );
      })}
    </div>
  );
}

export function ConsultantProfile({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: membership, isLoading: loadingMembership } = useOrgMembership();
  const [period, setPeriod] = useState<AnalyticsPeriod>({});
  const [presetKey, setPresetKey] = useState<PresetKey>('all');
  const [search, setSearch] = useState('');

  const canView =
    membership?.membership?.role === 'OWNER' ||
    membership?.membership?.role === 'ADMIN' ||
    membership?.membership?.sales_role === 'ANALYST' ||
    membership?.membership?.sales_role === 'MANAGER';

  const detailQ = useAnalyticsConsultantDetail(id, period);
  const activityQ = useAnalyticsConsultantActivity(id, period, 50);
  const leadsQ = useLeads({ consultant_id: id, search: search || undefined, limit: 50 });

  if (loadingMembership) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!canView) {
    return (
      <div className="mx-auto max-w-xl pt-12">
        <Card className="border-destructive/20 bg-destructive/5">
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <ShieldAlert className="h-10 w-10 text-destructive" />
            <h1 className="text-lg font-semibold">Acesso restrito</h1>
            <p className="max-w-sm text-sm text-muted-foreground">
              Relatórios estão disponíveis apenas para analistas, gestores e administradores da organização.
            </p>
            <SalesRoleBadge role={membership?.membership?.sales_role} />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (detailQ.isError) {
    const status = (detailQ.error as { status?: number } | null)?.status;
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Inteligência" title="Consultor" description="" />
        <Card className="border-destructive/20 bg-destructive/5">
          <CardContent className="flex items-center gap-3 py-8">
            <AlertTriangle className="h-6 w-6 shrink-0 text-destructive" />
            <div>
              <p className="font-medium">
                {status === 404 ? 'Consultor não encontrado nesta organização.' : 'Não foi possível carregar o perfil.'}
              </p>
              <Link href="/relatorios" className="text-sm text-muted-foreground underline underline-offset-2">
                Voltar para relatórios
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const detail = detailQ.data;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inteligência · Desempenho por consultor"
        title={detail?.name || 'Consultor'}
        description={
          detail?.email
            ? `${detail.email}${detail.sales_role ? ` · ${detail.sales_role}` : ''}`
            : 'Carregando...'
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href="/relatorios" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Voltar para relatórios
        </Link>
        <PeriodPresets value={presetKey} period={period} onChange={(key, p) => { setPresetKey(key); setPeriod(p); }} />
      </div>

      {detailQ.isLoading ? (
        <ConsultantKpisSkeleton />
      ) : detail ? (
        <ConsultantKpis detail={detail} />
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        {detailQ.isLoading ? (
          <FunnelEndToEndSkeleton />
        ) : detail ? (
          <FunnelEndToEndCard funnel={detail.funnel} />
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Trilha recente</CardTitle>
          </CardHeader>
          <CardContent>
            {activityQ.isLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
              </div>
            ) : (activityQ.data?.activities || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhuma atividade registrada no período.</p>
            ) : (
              <ol className="relative space-y-4 border-l pl-5">
                {(activityQ.data?.activities || []).slice(0, 12).map((a) => (
                  <li key={a.id} className="relative">
                    <span className="absolute -left-[22px] flex h-3.5 w-3.5 items-center justify-center rounded-full border-2 border-background bg-primary" />
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-medium">{ACTIVITY_LABELS[a.action] || a.action}</span>
                      {a.status_from && a.status_to && (
                        <span className="text-xs text-muted-foreground">
                          {STATUS_LABELS[a.status_from] || a.status_from} → {STATUS_LABELS[a.status_to] || a.status_to}
                        </span>
                      )}
                    </div>
                    <Link
                      href={`/oportunidades/${a.lead_id}`}
                      className="mt-0.5 block truncate text-xs font-medium text-primary hover:underline"
                    >
                      {a.company_name}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {a.created_at ? new Date(a.created_at).toLocaleString('pt-BR') : '—'}
                      {a.detail ? ` · ${a.detail}` : ''}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Carteira do consultor</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative">
            <Input
              placeholder="Buscar empresa na carteira..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-10 pl-8"
              aria-label="Buscar empresa"
            />
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-xs">⌕</span>
          </div>

          {leadsQ.isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : leadsQ.isError ? (
            <p className="text-sm text-red-600">Erro ao carregar leads.</p>
          ) : (leadsQ.data?.leads || []).length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum lead na carteira com os filtros atuais.</p>
          ) : (
            <ul className="divide-y">
              {(leadsQ.data?.leads || []).map((lead) => (
                <li key={lead.id}>
                  <Link
                    href={`/oportunidades/${lead.id}`}
                    className="group flex flex-wrap items-center justify-between gap-2 py-2.5 hover:bg-muted/50"
                  >
                    <span className="truncate font-medium group-hover:text-primary">{lead.company_name}</span>
                    <span className="flex shrink-0 items-center gap-2">
                      {lead.qualification_score != null && (
                        <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                          {lead.qualification_score}
                        </Badge>
                      )}
                      <Badge variant="secondary" className="text-xs">
                        {STATUS_LABELS[lead.status] || lead.status}
                      </Badge>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}