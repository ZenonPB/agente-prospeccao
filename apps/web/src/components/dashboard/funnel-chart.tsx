'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts';
import { useMetrics } from '@/hooks/use-api';
import { Skeleton } from '@/components/ui/skeleton';

interface FunnelItem {
  name: string;
  value: number;
  color: string;
}

const STAGE_COLORS: Record<string, string> = {
  'NOVO': '#3b82f6',
  'ANALISADO': '#8b5cf6',
  'QUALIFICADO': '#22c55e',
  'CONTATADO': '#f59e0b',
  'RESPONDIDO': '#06b6d4',
  'REUNIAO_MARCADA': '#ec4899',
  'DESQUALIFICADO': '#ef4444',
  'PERDIDO': '#6b7280',
};

const STAGE_LABELS: Record<string, string> = {
  'NOVO': 'Encontrados',
  'ANALISADO': 'Analisados',
  'QUALIFICADO': 'Aptos',
  'CONTATADO': 'Mensagem enviada',
  'RESPONDIDO': 'Respondeu',
  'REUNIAO_MARCADA': 'Reunião marcada',
  'DESQUALIFICADO': 'Desqualificados',
  'PERDIDO': 'Perdidos',
};

interface FunnelChartProps {
  onFilter?: (stage: string | null) => void;
  activeFilter?: string | null;
}

function FunnelSkeleton() {
  const bars = [
    { label: 'Encontrados', width: 'w-full' },
    { label: 'Analisados', width: 'w-3/4' },
    { label: 'Aptos', width: 'w-2/3' },
    { label: 'Mensagem enviada', width: 'w-1/2' },
    { label: 'Respondeu', width: 'w-2/5' },
    { label: 'Reunião marcada', width: 'w-1/3' },
  ];

  return (
    <div className="space-y-4">
      {bars.map((bar) => (
        <div key={bar.label} className="flex items-center gap-3">
          <Skeleton className="h-4 w-24 shrink-0" />
          <Skeleton className={`h-6 ${bar.width}`} />
        </div>
      ))}
    </div>
  );
}

interface TooltipPayloadItem {
  payload: FunnelItem;
  value: number;
  name: string;
}

interface TooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}

function FunnelTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0].payload;
  return (
    <div className="rounded-lg border bg-background p-3 shadow-lg">
      <p className="font-medium text-foreground">{data.name}</p>
      <p className="text-sm text-foreground">{data.value.toLocaleString('pt-BR')} leads</p>
      <p className="mt-1 text-xs text-muted-foreground">Clique para filtrar</p>
    </div>
  );
}

export function FunnelChart({ onFilter, activeFilter }: FunnelChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const { data: metrics, isLoading, isError, error } = useMetrics();

  if (isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Funil de Resultados</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-red-600">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <p className="text-sm font-medium">Erro ao carregar funil</p>
          </div>
          <p className="mt-1 text-xs text-red-500">
            {error instanceof Error ? error.message : 'Tente novamente mais tarde'}
          </p>
        </CardContent>
      </Card>
    );
  }

  const funnelData: FunnelItem[] = metrics?.funnel
    ? metrics.funnel.map((item) => ({
        name: STAGE_LABELS[item.stage] || item.stage,
        value: item.count,
        color: STAGE_COLORS[item.stage] || '#6b7280',
      }))
    : [];

  const handleClick = (nextState: unknown) => {
    const typed = nextState as { activePayload?: { payload: FunnelItem }[] };
    if (typed?.activePayload?.length) {
      const clickedName = typed.activePayload[0].payload.name;
      onFilter?.(activeFilter === clickedName ? null : clickedName);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Funil de Resultados</CardTitle>
          {activeFilter && (
            <button
              onClick={() => onFilter?.(null)}
              className="text-sm text-primary hover:underline"
            >
              Limpar filtro
            </button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          {isLoading ? (
            <div className="flex h-full items-center justify-center">
              <FunnelSkeleton />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={funnelData}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
                onClick={handleClick}
                style={{ cursor: 'pointer' }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
                <XAxis
                  type="number"
                  tick={{ fill: 'hsl(var(--foreground))', fontSize: 12 }}
                  stroke="hsl(var(--muted-foreground))"
                />
                <YAxis
                  dataKey="name"
                  type="category"
                  width={95}
                  tick={{ fill: 'hsl(var(--foreground))', fontSize: 12 }}
                  stroke="hsl(var(--muted-foreground))"
                />
                <Tooltip content={<FunnelTooltip />} />
                <Bar
                  dataKey="value"
                  radius={[0, 4, 4, 0]}
                  onMouseEnter={(_, index) => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                >
                  {funnelData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.color}
                      opacity={activeFilter && activeFilter !== entry.name ? 0.3 : 1}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        {funnelData.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {funnelData.map((entry) => (
              <button
                key={entry.name}
                onClick={() => onFilter?.(activeFilter === entry.name ? null : entry.name)}
                className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors ${
                  activeFilter === entry.name
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                }`}
              >
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
                {entry.name}
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
