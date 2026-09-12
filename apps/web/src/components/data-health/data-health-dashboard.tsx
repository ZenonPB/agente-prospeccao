'use client';

import { useMemo } from 'react';
import { AlertTriangle, CheckCircle2, DatabaseZap, Loader2, RefreshCw, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { useDataHealth, useRefreshPlan } from '@/hooks/use-data-intelligence';
import type { DataHealthItem, ProviderHealth } from '@/lib/data-intelligence-api';

const ISSUE_LABELS: Record<string, string> = {
  stale: 'Dados desatualizados',
  invalid_email: 'E-mails inválidos',
  missing_phone: 'Sem telefone',
  missing_email: 'Sem e-mail',
  missing_decision_maker: 'Sem decisor',
  identity_risk: 'Identidade incompleta',
};

const PROVIDER_HEALTH_LABELS: Record<ProviderHealth['health'], string> = {
  healthy: 'Saudável',
  degraded: 'Degradado',
  disabled: 'Desativado',
  quota_exceeded: 'Cota esgotada',
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
        toast.info('Não há campanhas elegíveis para refresh agora.');
      } else {
        toast.success(`${queued} refresh${queued === 1 ? '' : 'es'} agendado${queued === 1 ? '' : 's'}${reused ? ` · ${reused} já estava(m) na fila` : ''}.`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível agendar o refresh.');
    }
  }

  if (health.isLoading) {
    return (
      <div className="flex min-h-56 items-center justify-center" role="status" aria-live="polite">
        <Loader2 className="size-5 animate-spin" aria-hidden="true" />
        <span className="ml-2 text-sm text-muted-foreground">Analisando saúde dos dados...</span>
      </div>
    );
  }

  if (health.isError) {
    return (
      <EmptyState
        icon={<AlertTriangle className="size-6" aria-hidden="true" />}
        title="Não foi possível carregar a saúde dos dados"
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
            <CardDescription>Saúde geral</CardDescription>
            <CardTitle className="text-3xl">{data.health_rate}%</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
            <ShieldCheck className="size-4" aria-hidden="true" />
            {data.healthy} de {data.total} registros sem bloqueadores críticos
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Registros avaliados</CardDescription>
            <CardTitle className="text-3xl">{data.total}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">Workspace atual, sem misturar tenants</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Precisam de atenção</CardDescription>
            <CardTitle className="text-3xl">{data.total - data.healthy}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">Ordenados por prioridade comercial de refresh</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Atualização</CardDescription>
            <CardTitle className="text-base">Sob demanda</CardTitle>
          </CardHeader>
          <CardContent>
            <Button className="w-full" onClick={() => void enqueueRefresh()} disabled={refreshPlan.isPending}>
              {refreshPlan.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
              {refreshPlan.isPending ? 'Agendando...' : 'Agendar refresh prioritário'}
            </Button>
          </CardContent>
        </Card>
      </div>

      {issueCards.length > 0 && (
        <section aria-labelledby="health-issues-title" className="space-y-3">
          <h2 id="health-issues-title" className="text-base font-semibold">Principais problemas</h2>
          <div className="flex flex-wrap gap-2">
            {issueCards.map(([key, count]) => (
              <Badge key={key} variant="secondary" className="px-3 py-1.5">
                {ISSUE_LABELS[key] ?? key}: {count}
              </Badge>
            ))}
          </div>
        </section>
      )}

      {data.provider_health.length > 0 && (
        <section aria-labelledby="provider-health-title" className="space-y-3">
          <div>
            <h2 id="provider-health-title" className="text-base font-semibold">Saúde dos providers</h2>
            <p className="text-sm text-muted-foreground">Últimos 7 dias. Falha, cota esgotada, desativado e sucesso permanecem estados distintos.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.provider_health.map((provider) => (
              <Card key={provider.provider}>
                <CardContent className="flex items-center justify-between gap-4 pt-6">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{provider.provider}</p>
                    <p className="text-xs text-muted-foreground">{provider.total} execuções · {provider.failure_rate}% falhas</p>
                  </div>
                  <Badge variant={providerTone(provider.health)}>{PROVIDER_HEALTH_LABELS[provider.health]}</Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <DatabaseZap className="size-5 text-primary" aria-hidden="true" />
            <CardTitle>Fila de qualidade dos dados</CardTitle>
          </div>
          <CardDescription>
            Priorização considera oportunidades abertas, próxima ação, dados vencidos, decisor ausente e risco de identidade.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.items.length === 0 ? (
            <EmptyState
              icon={<CheckCircle2 className="size-6" aria-hidden="true" />}
              title="Nenhum registro para revisar"
              description="A base deste workspace ainda está vazia ou totalmente saudável."
            />
          ) : (
            <div className="space-y-3">
              {data.items.slice(0, 50).map((item) => (
                <article key={item.lead_id} className="rounded-xl border bg-card p-4" aria-label={`Saúde dos dados de ${item.company_name}`}>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="truncate font-medium">{item.company_name}</h3>
                        <Badge variant={healthTone(item)}>Prioridade {item.refresh_priority}</Badge>
                        {item.opportunity_count > 0 && <Badge variant="outline">{item.opportunity_count} oportunidade{item.opportunity_count === 1 ? '' : 's'}</Badge>}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-muted-foreground">
                        {item.stale_keys.map((key) => <Badge key={`stale-${key}`} variant="secondary">Vencido: {key}</Badge>)}
                        {item.missing_decision_maker && <Badge variant="secondary">Sem decisor</Badge>}
                        {item.missing_email && <Badge variant="outline">Sem e-mail</Badge>}
                        {item.missing_phone && <Badge variant="outline">Sem telefone</Badge>}
                        {item.email_invalid && <Badge variant="destructive">E-mail suprimido</Badge>}
                        {item.identity_risk && <Badge variant="destructive">Identidade incompleta</Badge>}
                      </div>
                    </div>
                    <div className="text-left text-xs text-muted-foreground sm:text-right">
                      <div>Telefone: {item.phone_verification.state}</div>
                      <div>Cobertura desconhecida: {item.unknown_keys.length}</div>
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
