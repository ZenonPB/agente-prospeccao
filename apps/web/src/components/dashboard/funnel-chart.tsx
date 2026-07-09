'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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

interface FunnelItem {
  name: string;
  value: number;
  color: string;
}

const funnelData: FunnelItem[] = [
  { name: 'Encontrados', value: 1234, color: '#3b82f6' },
  { name: 'Analisados', value: 980, color: '#8b5cf6' },
  { name: 'Aptos', value: 456, color: '#22c55e' },
  { name: 'Mensagem enviada', value: 89, color: '#f59e0b' },
  { name: 'Respondeu', value: 34, color: '#06b6d4' },
  { name: 'Reunião marcada', value: 12, color: '#ec4899' },
];

interface FunnelChartProps {
  onFilter?: (stage: string | null) => void;
  activeFilter?: string | null;
}

export function FunnelChart({ onFilter, activeFilter }: FunnelChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const handleClick = (data: any) => {
    if (data && data.activePayload && data.activePayload.length > 0) {
      const clickedName = data.activePayload[0].payload.name;
      if (onFilter) {
        onFilter(activeFilter === clickedName ? null : clickedName);
      }
    }
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || !payload.length) return null;
    const data = payload[0].payload;
    const idx = funnelData.findIndex(d => d.name === data.name);
    const prevValue = idx > 0 ? funnelData[idx - 1].value : null;
    const dropoff = prevValue ? Math.round((1 - data.value / prevValue) * 100) : null;

    return (
      <div className="rounded-lg border bg-background p-3 shadow-lg">
        <p className="font-medium text-foreground">{data.name}</p>
        <p className="text-sm text-foreground">{data.value.toLocaleString('pt-BR')} leads</p>
        {dropoff !== null && (
          <p className="text-xs text-muted-foreground">
            Queda de {dropoff}% vs etapa anterior
          </p>
        )}
        <p className="mt-1 text-xs text-muted-foreground">Clique para filtrar</p>
      </div>
    );
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
              <Tooltip content={<CustomTooltip />} />
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
        </div>
        {/* Legend */}
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
      </CardContent>
    </Card>
  );
}