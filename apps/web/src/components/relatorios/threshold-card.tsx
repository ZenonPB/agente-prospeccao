'use client';

import { useState } from 'react';
import { CheckCircle2, Loader2, Sliders } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAnalyticsThresholdSuggestion, useMyOrganization, usePatchOrgSettings, type AnalyticsPeriod } from '@/hooks/use-api';
import { toast } from 'sonner';

interface Props {
  period: AnalyticsPeriod;
}

export function ThresholdCard({ period }: Props) {
  const suggestionQ = useAnalyticsThresholdSuggestion(period);
  const orgQ = useMyOrganization();
  const patch = usePatchOrgSettings();
  const [pending, setPending] = useState(false);

  if (suggestionQ.isLoading || orgQ.isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-6 w-3/4" />
        </CardContent>
      </Card>
    );
  }

  if (suggestionQ.isError || !suggestionQ.data || !orgQ.data) {
    return null;
  }

  const suggestion = suggestionQ.data;
  const orgId = orgQ.data.organization.id;
  const current = orgQ.data.organization.qualification_threshold ?? 60;
  const recommended = suggestion.recommended_threshold;
  const isOwnerOrAdmin =
    orgQ.data.membership.role === 'OWNER' || orgQ.data.membership.role === 'ADMIN';
  const delta = recommended - current;

  const apply = async () => {
    setPending(true);
    try {
      await patch.mutateAsync({ orgId, data: { qualification_threshold: recommended } });
      toast.success(`Threshold atualizado para ${recommended}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Falha ao atualizar.');
    } finally {
      setPending(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sliders className="h-4 w-4 text-muted-foreground" />
          Threshold de qualificação
        </CardTitle>
        <CardDescription>
          Limiar de score para um lead entrar na fila de outreach da sua organização.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Atual</p>
            <p className="text-3xl font-bold tabular-nums">{current}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Sugerido</p>
            <p className="text-3xl font-bold tabular-nums text-emerald-600">{recommended}</p>
          </div>
          <div className="text-sm text-muted-foreground">
            {delta === 0
              ? 'Threshold atual já está calibrado.'
              : delta > 0
                ? `Subir ${delta} ponto${delta === 1 ? '' : 's'} para reduzir falsos positivos.`
                : `Descer ${Math.abs(delta)} ponto${Math.abs(delta) === 1 ? '' : 's'} para incluir mais leads.`}
          </div>
        </div>

        <p className="text-sm text-muted-foreground">{suggestion.rationale}</p>

        {suggestion.candidates.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Candidatos (F1)</p>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {suggestion.candidates.map((c) => {
                const isBest = c.threshold === recommended;
                return (
                  <div
                    key={c.threshold}
                    className={
                      'flex items-center justify-between rounded-md border px-3 py-1.5 text-sm ' +
                      (isBest ? 'border-emerald-300 bg-emerald-50 dark:bg-emerald-900/20' : 'border-border')
                    }
                  >
                    <span className="font-medium tabular-nums">≥ {c.threshold}</span>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {c.qualified} qualificados · F1 {c.f1}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="flex items-center gap-2">
          {isOwnerOrAdmin ? (
            <Button onClick={apply} disabled={pending || delta === 0 || patch.isPending}>
              {pending || patch.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="mr-2 h-4 w-4" />
              )}
              {delta === 0 ? 'Já está calibrado' : `Aplicar threshold ${recommended}`}
            </Button>
          ) : (
            <p className="text-xs text-muted-foreground">
              Apenas owner/admin pode aplicar o threshold sugerido.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
