'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingDown, BrainCircuit } from 'lucide-react';
import type { ScoreFeedbackMetrics } from '@/lib/api';

function DeviationSparkline({ weekly }: { weekly: ScoreFeedbackMetrics['weekly'] }) {
  const max = Math.max(1, ...weekly.map((w) => w.avg_deviation));
  return (
    <div className="flex h-16 items-end gap-1.5" aria-hidden="true">
      {weekly.slice(-16).map((w) => (
        <div
          key={w.week}
          title={`${w.week}: desvio médio ${w.avg_deviation} pts (${w.feedbacks} correções)`}
          className="w-4 rounded-sm bg-violet-300 transition-all"
          style={{ height: `${Math.max(6, (w.avg_deviation / max) * 64)}px` }}
        />
      ))}
    </div>
  );
}

export function ConvergenceCard({ metrics }: { metrics: ScoreFeedbackMetrics }) {
  const weekly = metrics.weekly;
  const trend =
    weekly.length >= 2
      ? weekly[weekly.length - 1].avg_deviation - weekly[0].avg_deviation
      : null;

  return (
    <Card data-tour="relatorios-convergencia">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-violet-600" />
          Convergência IA × Time
        </CardTitle>
        <CardDescription>
          Desvio médio entre o score da IA e o score do consultor — quanto menor, mais a IA aprendeu com as correções.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-6">
          <div>
            <p className="text-3xl font-bold tabular-nums">
              {metrics.overall_avg != null ? `${metrics.overall_avg} pts` : '—'}
            </p>
            <p className="text-xs text-muted-foreground">desvio médio geral</p>
          </div>
          <div>
            <p className="text-3xl font-bold tabular-nums">{metrics.total_feedbacks}</p>
            <p className="text-xs text-muted-foreground">correções registradas</p>
          </div>
          {trend != null && (
            <div className="flex items-center gap-1.5 text-sm">
              <TrendingDown
                className={`h-4 w-4 ${trend <= 0 ? 'text-emerald-600' : 'text-amber-600'}`}
              />
              <span className={trend <= 0 ? 'text-emerald-700' : 'text-amber-700'}>
                {trend <= 0 ? 'IA convergindo com o time' : 'desvio crescendo — revise os critérios'}
              </span>
            </div>
          )}
        </div>
        {weekly.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground">Desvio médio por semana</p>
            <DeviationSparkline weekly={weekly} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
