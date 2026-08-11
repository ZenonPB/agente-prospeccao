'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import type { ForecastData } from '@/types';
import { DollarSign, TrendingUp, AlertTriangle } from 'lucide-react';

const LOST_REASON_LABELS: Record<string, string> = {
  PRECO: 'Preço / Orçamento',
  PRAZO: 'Prazo longo',
  NAO_RESPONDEU: 'Sem resposta / Sumiu',
  CONCORRENTE: 'Fechou com concorrente',
  OUTRO: 'Outro motivo',
  SEM_MOTIVO: 'Não especificado',
};

const STAGE_LABELS: Record<string, string> = {
  NOVO: 'Novo',
  ANALISADO: 'Analisado',
  QUALIFICADO: 'Apto',
  CONTATADO: 'Mensagem enviada',
  RESPONDIDO: 'Respondeu',
  REUNIAO_MARCADA: 'Reunião marcada',
  REUNIAO_FEITA: 'Reunião feita',
  PROPOSTA_ENVIADA: 'Proposta enviada',
};

function formatBRL(val: number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(val);
}

export function ForecastCard({ forecast }: { forecast: ForecastData }) {
  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base font-semibold">
          <span>Forecast & Oportunidades (Item 4.8)</span>
          <span className="text-xs font-normal text-muted-foreground">
            {forecast.open_leads_count} leads em aberto
          </span>
        </CardTitle>
        <CardDescription>
          Previsão ponderada pela probabilidade histórica de conversão de cada estágio do funil
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* KPI Row */}
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg border p-3.5 bg-muted/30">
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <DollarSign className="h-4 w-4 text-sky-600" />
              <span>Pipeline Total Em Aberto</span>
            </div>
            <p className="mt-2 text-xl font-bold tracking-tight">{formatBRL(forecast.pipeline_value)}</p>
          </div>

          <div className="rounded-lg border p-3.5 bg-muted/30">
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <TrendingUp className="h-4 w-4 text-emerald-600" />
              <span>Forecast Ponderado</span>
            </div>
            <p className="mt-2 text-xl font-bold tracking-tight text-emerald-600 dark:text-emerald-400">
              {formatBRL(forecast.forecast_weighted)}
            </p>
          </div>

          <div className="rounded-lg border p-3.5 bg-muted/30">
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <DollarSign className="h-4 w-4 text-teal-600" />
              <span>Receita Realizada (Fechados)</span>
            </div>
            <p className="mt-2 text-xl font-bold tracking-tight text-teal-600 dark:text-teal-400">
              {formatBRL(forecast.realized_revenue)}
            </p>
          </div>
        </div>

        {/* Stage Forecast Breakdown Table */}
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Detalhamento por Estágio
          </h4>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-xs">
              <thead className="border-b bg-muted/50 text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Estágio</th>
                  <th className="px-3 py-2 text-center">Leads</th>
                  <th className="px-3 py-2 text-center">Probabilidade</th>
                  <th className="px-3 py-2 text-right">Valor Total</th>
                  <th className="px-3 py-2 text-right">Valor Ponderado</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {forecast.pipeline_by_stage.map((s) => (
                  <tr key={s.stage} className="hover:bg-muted/20">
                    <td className="px-3 py-2 font-medium">{STAGE_LABELS[s.stage] || s.stage}</td>
                    <td className="px-3 py-2 text-center tabular-nums">{s.count}</td>
                    <td className="px-3 py-2 text-center font-mono">{Math.round(s.probability * 100)}%</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatBRL(s.total_value)}</td>
                    <td className="px-3 py-2 text-right font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
                      {formatBRL(s.weighted_value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Lost Reasons Breakdown */}
        {forecast.lost_reasons_breakdown.some((r) => r.count > 0) && (
          <div>
            <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
              <span>Motivos de Perda de Leads (PERDIDO)</span>
            </h4>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {forecast.lost_reasons_breakdown
                .filter((r) => r.count > 0)
                .map((r) => (
                  <div key={r.reason} className="flex items-center justify-between rounded-md border p-2.5 text-xs">
                    <span className="text-muted-foreground">{LOST_REASON_LABELS[r.reason] || r.reason}</span>
                    <span className="font-semibold tabular-nums">{r.count} lead(s)</span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
