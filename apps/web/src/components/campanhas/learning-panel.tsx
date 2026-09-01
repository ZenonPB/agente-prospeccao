'use client';

import { Sparkles, RefreshCw, X, BrainCircuit, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  useCampaignLearning,
  useSynthesizeLearning,
  useDiscardLearningRule,
  useReanalyzeCampaign,
} from '@/hooks/use-api';

function DeviationBars({ weekly }: { weekly: { week: string; avg_deviation: number }[] }) {
  if (weekly.length === 0) return null;
  const max = Math.max(1, ...weekly.map((w) => w.avg_deviation));
  return (
    <div className="flex items-end gap-1.5" aria-hidden="true">
      {weekly.slice(-12).map((w) => (
        <div
          key={w.week}
          title={`${w.week}: desvio médio ${w.avg_deviation}`}
          className="w-3 rounded-sm bg-violet-200 transition-all"
          style={{ height: `${Math.max(8, (w.avg_deviation / max) * 48)}px` }}
        />
      ))}
    </div>
  );
}

export function LearningPanel({ campaignId }: { campaignId: string }) {
  const learningQ = useCampaignLearning(campaignId);
  const synthesize = useSynthesizeLearning();
  const discardRule = useDiscardLearningRule();
  const reanalyze = useReanalyzeCampaign();

  const learning = learningQ.data;
  const hasPending = (learning?.pending_feedbacks ?? 0) > 0;

  const handleSynthesize = async () => {
    try {
      const out = await synthesize.mutateAsync(campaignId);
      toast.success(
        `IA aprendeu: ${out.compiled} feedback${out.compiled === 1 ? '' : 's'} viraram ${out.rules.length} regra${out.rules.length === 1 ? '' : 's'}.`,
      );
    } catch {
      toast.error('Não foi possível sintetizar os aprendizados agora.');
    }
  };

  const handleReevaluate = async () => {
    try {
      const out = await reanalyze.mutateAsync({ campaign_id: campaignId });
      toast.success(`Reavaliação na fila: ${out.leads_to_reanalyze} leads com as regras atualizadas.`);
    } catch {
      toast.error('Não foi possível agendar a reavaliação.');
    }
  };

  const handleDiscard = async (ruleIndex: number) => {
    try {
      await discardRule.mutateAsync({ campaignId, ruleIndex });
      toast.success('Regra descartada — não afeta mais o scoring.');
    } catch {
      toast.error('Não foi possível descartar a regra.');
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:space-y-0">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-violet-600" />
            Aprendizados da IA
          </CardTitle>
          <CardDescription>
            Regras que a IA aprendeu com as correções de score do time — aplicadas como contexto no próximo scoring.
          </CardDescription>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleSynthesize}
            disabled={synthesize.isPending || !hasPending}
            className="gap-1.5 text-xs"
          >
            {synthesize.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 text-violet-600" />}
            Sintetizar aprendizados
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleReevaluate}
            disabled={reanalyze.isPending || (learning?.rules.length ?? 0) === 0}
            className="gap-1.5 text-xs"
          >
            {reanalyze.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Aplicar e reavaliar
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {learningQ.isLoading ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Carregando aprendizados…</p>
        ) : learningQ.isError || !learning ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Não foi possível carregar os aprendizados.
          </p>
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <Badge variant="secondary" className="text-xs">
                {learning.total_feedbacks} correções do time
              </Badge>
              {hasPending && (
                <Badge className="bg-violet-100 text-xs text-violet-700">
                  {learning.pending_feedbacks} aguardando síntese
                </Badge>
              )}
              {learning.deviation.overall_avg != null && (
                <span>
                  desvio médio IA × time: <strong className="text-foreground">{learning.deviation.overall_avg}</strong> pts
                </span>
              )}
            </div>

            {learning.deviation.weekly.length > 1 && (
              <div className="space-y-1.5">
                <p className="text-xs text-muted-foreground">
                  Convergência por semana (barras menores = IA mais alinhada com o time)
                </p>
                <DeviationBars weekly={learning.deviation.weekly} />
              </div>
            )}

            {learning.rules.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                Ainda não há regras aprendidas. Corrija scores no kanban e sintetize aqui.
              </p>
            ) : (
              <ul className="space-y-2">
                {learning.rules.map((rule, index) => (
                  <li
                    key={`${index}-${rule.slice(0, 12)}`}
                    className="flex items-start justify-between gap-3 rounded-md border bg-muted/30 px-3 py-2"
                  >
                    <p className="text-sm">{rule}</p>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-6 w-6 shrink-0 text-muted-foreground hover:text-destructive"
                      aria-label={`Descartar regra: ${rule}`}
                      onClick={() => handleDiscard(index)}
                      disabled={discardRule.isPending}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
