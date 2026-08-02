'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import type { AnalyticsTimelineItem } from '@/lib/api';

function formatDate(iso: string): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
}

const TOOLTIP_LABELS: Record<string, string> = {
  new_leads: 'Novos',
  meetings: 'Reuniões',
  closed: 'Fechados',
};

export function TimelineCard({ timeline }: { timeline: AnalyticsTimelineItem[] }) {
  const data = timeline.map((item) => ({ ...item, label: formatDate(item.date) }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Evolução temporal</CardTitle>
        <CardDescription>Novos leads, reuniões marcadas e fechados por dia</CardDescription>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Sem dados no período.
          </p>
        ) : (
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 5, right: 12, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                  stroke="hsl(var(--border))"
                  interval="preserveStartEnd"
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                  stroke="hsl(var(--border))"
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: 12,
                    border: '1px solid hsl(var(--border))',
                    background: 'hsl(var(--popover))',
                    fontSize: 12,
                  }}
                  labelFormatter={(_, payload) => {
                    const first = payload?.[0]?.payload as AnalyticsTimelineItem | undefined;
                    return first?.date ? formatDate(first.date) : '';
                  }}
                  formatter={(value, name) => [value, TOOLTIP_LABELS[String(name)] || String(name)]}
                />
                <Legend formatter={(value) => TOOLTIP_LABELS[String(value)] || String(value)} />
                <Bar dataKey="new_leads" fill="#0f766e" radius={[3, 3, 0, 0]} />
                <Bar dataKey="meetings" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                <Line type="monotone" dataKey="closed" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function TimelineSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-36" />
        <Skeleton className="h-4 w-56" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-[280px] w-full" />
      </CardContent>
    </Card>
  );
}
