export type ScoreBand = 'unevaluated' | 'low' | 'good' | 'hot';

export function getScoreBand(score?: number | null): ScoreBand {
  if (score == null || score <= 0) return 'unevaluated';
  if (score < 60) return 'low';
  if (score < 80) return 'good';
  return 'hot';
}

export const scoreBandBadge: Record<ScoreBand, string> = {
  unevaluated: 'bg-slate-100 text-slate-600 border border-slate-200',
  low: 'bg-red-100 text-red-700',
  good: 'bg-emerald-100 text-emerald-700',
  hot: 'bg-emerald-600 text-white',
};

export const SCORE_THRESHOLD_HINT = '≥ 60 = apto para contato';

export const priorityLabels: Record<string, string> = {
  HOT: 'Quente',
  WARM: 'Morno',
  COLD: 'Frio',
};
