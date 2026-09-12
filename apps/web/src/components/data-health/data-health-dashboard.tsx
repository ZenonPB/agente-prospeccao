'use client';

import { useMemo } from 'react';
import { AlertTriangle, CheckCircle2, DatabaseZap, Loader2, RefreshCw, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { useDataHealth, useRefreshPlan } from '@/hooks/use-data-intelligence';
import {
  freshnessLabel,
  phoneStateLabel,
  providerLabel,
} from '@/lib/commercial-labels';
import type { DataHealthItem, ProviderHealth } from '@/lib/data-intelligence-api';

const ISSUE_LABELS: Record<string, string> = {
  stale: 'Dados desatualizados',
  invalid_email: 'E-mails bloqueados para envio',
  missing_phone: 'Sem telefone',
  missing_email: 'Sem e-mail',
  missing_decision_maker: 'Sem decisor identificado',
  identity_risk: 'Identidade da empresa incompleta',
};

const SOURCE_HEALTH_LABELS: Record<ProviderHealth['health'], string> = {
  healthy: 'Funcionando normalmente',
  degraded: 'Com falhas recentes',
  disabled: 'Desativada',
  quota_exceeded: 'Limite de uso atingido',
};

function healthTone(item: DataHealthItem) {
  if (item.email_invalid || item.identity_risk) return 'destructive' as const;
  if (item.stale_keys.length || item.missing_decision_maker) return 'secondary' as const;
  return 'outline' as const;
}

function providerTone(health: ProviderHealth['health']) {
  if (health === 'degraded' || health === 'quota_exceeded') return 'destructive' as const;
  if (health === 'disabled') return 'secondary' as const;
  return 'outline' as const;
}

export function DataHealthDashboard() {
  const health = useDataHealth(200);
  const refreshPlan = useRefreshPlan();

  const issueCards = useMemo(() => {
    if (!health.data) return [];
    return Object.entries(health.data.issues)
      .filter(([, count]) => count > 0)
      .sort((a, b) => b[1] - a[1]);
  }, [health.data]);

  async function enqueueRefresh() {
    try {
      const result = await refreshPlan.mutateAsync({ limit: 50, enqueue: true });
      const queued = result.jobs.filter((job) => job.status === 'queued').length;
      const reused = result.jobs.filter((job) => job.status === 'already_pending').length;
      if (queued === 0 && reused === 0) {
        toast.info('Não há dados prioritários para atualizar agora.');
      } else {
        const reusedText = reused ? ` · ${reused} já estava${reused === 1 ? '' : 'm'} na fila` : '';
        toast.success(`${queued} atualização${queued === 1 ? '' : 'ões'} agendada${queued === 1 ? '' : 's'}${reusedText}.`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível agendar as atualizações.');
    }
  }

  if (health.isLoading) {
    return (
      <div className="flex min-h-56 items-center justify-center" role="status" aria-live="polite">
        <Loader2 className="size-5 animate-spin" aria-hidden="true" />
        <span className="ml-2 text-sm text-muted-foreground">Analisando a qualidade dos dados...</span>
      </div>
    );
  }

  if (health.isError) {
    return (
      <EmptyState
        icon={<AlertTriangle className="size-6" aria-hidden="true" />}
        title="Não foi possível analisar a qualidade dos dados"
        description={health.error instanceof Error ? health.error.message : 'Tente novamente em instantes.'}
        action={<Button onClick={() => void health.refetch()}>Tentar novamente</Button>}
      />
    );
  }

  const data = health.data;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Qualidade dos registros analisados</CardDescription>
            <CardTitle className="text-3xl">{data.health_rate}%</CardTitle>
          </CardHeader>
          <CardContent className="flex items-start gap-2 text-sm text-muted-foreground">
            <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>{data.healthy} de {data.analyzed} registros analisados sem bloqueadores importantes</span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Cobertura desta análise</CardDescription>
            <CardTitle className="text-3xl">{data.coverage_rate}%</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {data.analyzed} de {data.organization_total} registros da organização
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Precisam de atenção</CardDescription>
            <CardTitle className="text-3xl">{data.analyzed - data.healthy}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Priorizados por oportunidade, próxima ação e qualidade dos dados
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Atualização prioritária</CardDescription>
            <CardTitle className="text-base">Sob demanda</CardTitle>
          </CardHeader>
          <CardContent>
            <Button className="w-full" onClick={() => void enqueueRefresh()} disabled={refreshPlan.isPending}>
              {refreshPlan.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
              {refreshPlan.isPending ? 'Agendando...' : 'Atualizar dados prioritários'}
            </Button>
          </CardContent>
        </Card>
      </div>

      {data.sample_truncated ? (
        <div className="rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground" role="note">
          Para manter a tela rápida, esta visão detalha os {data.analyzed} registros com maior prioridade entre {data.organization_total} no total. A porcentagem de qualidade acima se refere somente aos registros analisados.
        </div>
      ) : null}

      {issueCards.length > 0 ? (
        <section aria-labelledby="health-issues-title" className="space-y-3">
          <h2 id="health-issues-title" className="text-base font-semibold">Principais pontos de atenção</h2>
          <div className="flex flex-wrap gap-2">
            {issueCards.map(([key, count]) => (
              <Badge key={key} variant="secondary" className="px-3 py-1.5">
                {ISSUE_LABELS[key] ?? key}: {count}
              </Badge>
            ))}
          </div>
        </section>
      ) : null}

      {data.provider_health.length > 0 ? (
        <section aria-labelledby="provider-health-title" className="space-y-3">
          <div>
            <h2 id="provider-health-title" className="text-base font-semibold">Confiabilidade das fontes</h2>
            <p className="text-sm text-muted-foreground">Resumo dos últimos sete dias para identificar fontes que precisam de atenção.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.provider_health.map((provider) => (
              <Card key={provider.provider}>
                <CardContent className="flex items-center justify-between gap-4 pt-6">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{providerLabel(provider.provider)}</p>
                    <p className="text-xs text-muted-foreground">{provider.total} consulta{provider.total === 1 ? '' : 's'} · {provider.failure_rate}% com falha</p>
                  </div>
                  <Badge variant={providerTone(provider.health)}>{SOURCE_HEALTH_LABELS[provider.health]}</Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      ) : null}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <DatabaseZap className="size-5 text-primary" aria-hidden="true" />
            <CardTitle>Registros que merecem revisão</CardTitle>
          </div>
          <CardDescription>
            A ordem considera oportunidades abertas, ações próximas, informações desatualizadas e ausência de decisores.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.items.length === 0 ? (
            <EmptyState
              icon={<CheckCircle2 className="size-6" aria-hidden="true" />}
              title="Nenhum registro para revisar"
              description="A organização ainda não possui registros ou todos os itens analisados estão em boas condições."
            />
          ) : (
            <div className="space-y-3">
              {data.items.slice(0, 50).map((item) => (
                <article key={item.lead_id} className="rounded-xl border bg-card p-4" aria-label={`Qualidade dos dados de ${item.company_name}`}>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="truncate font-medium">{item.company_name}</h3>
                        <Badge variant={healthTone(item)}>Prioridade {item.refresh_priority}</Badge>
                        {item.opportunity_count > 0 ? <Badge variant="outline">{item.opportunity_count} oportunidade{item.opportunity_count === 1 ? '' : 's'}</Badge> : null}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-muted-foreground">
                        {item.stale_keys.map((key) => <Badge key={`stale-${key}`} variant="secondary">Desatualizado: {freshnessLabel(key)}</Badge>)}
                        {item.missing_decision_maker ? <Badge variant="secondary">Sem decisor identificado</Badge> : null}
                        {item.missing_email ? <Badge variant="outline">Sem e-mail</Badge> : null}
                        {item.missing_phone ? <Badge variant="outline">Sem telefone</Badge> : null}
                        {item.email_invalid ? <Badge variant="destructive">E-mail bloqueado para envio</Badge> : null}
                        {item.identity_risk ? <Badge variant="destructive">Identidade da empresa incompleta</Badge> : null}
                      </div>
                    </div>
                    <div className="text-left text-xs text-muted-foreground sm:text-right">
                      <div>Telefone: {phoneStateLabel(item.phone_verification.state)}</div>
                      <div>Informações ainda não confirmadas: {item.unknown_keys.length}</div>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
