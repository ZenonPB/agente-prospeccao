'use client';

import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { TrendingUp, Target, Phone, CalendarDays, BadgeCheck, CircleDollarSign } from 'lucide-react';
import type { AnalyticsOverview } from '@/lib/api';

const META = [
  { key: 'total_leads', label: 'Clientes Encontrados', icon: Target, accent: 'text-sky-600 dark:text-sky-400' },
  { key: 'qualified_leads', label: 'Aptos para Contato', icon: BadgeCheck, accent: 'text-emerald-600 dark:text-emerald-400' },
  { key: 'contacted_leads', label: 'Mensagens Enviadas', icon: Phone, accent: 'text-amber-600 dark:text-amber-400' },
  { key: 'meetings_scheduled', label: 'Reuniões Agendadas', icon: CalendarDays, accent: 'text-violet-600 dark:text-violet-400' },
  { key: 'converted_leads', label: 'Vendas Realizadas', icon: TrendingUp, accent: 'text-teal-600 dark:text-teal-400' },
  { key: 'total_revenue', label: 'Faturamento Total', icon: CircleDollarSign, accent: 'text-rose-600 dark:text-rose-400' },
];

function formatValue(key: string, value: number): string {
  if (key === 'total_revenue') {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value);
  }
  return new Intl.NumberFormat('pt-BR').format(value);
}

export function ExecutiveKpis({ overview }: { overview: AnalyticsOverview }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {META.map((m) => {
        const Icon = m.icon;
        const value = (overview as unknown as Record<string, number>)[m.key] ?? 0;
        return (
          <Card key={m.key} className="min-w-0 p-4">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 space-y-1">
                <p className="text-[11px] font-medium leading-tight text-muted-foreground sm:text-xs">
                  {m.label}
                </p>
                <p className="truncate text-lg font-bold tracking-tight sm:text-2xl">
                  {formatValue(m.key, value)}
                </p>
              </div>
              <Icon className={`h-4 w-4 shrink-0 sm:h-5 sm:w-5 ${m.accent}`} />
            </div>
          </Card>
        );
      })}
    </div>
  );
}

export function ExecutiveKpisSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {Array.from({ length: 6 }).map((_, i) => (
        <Card key={i} className="min-w-0 p-4">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="mt-2 h-6 w-20 sm:h-7" />
        </Card>
      ))}
    </div>
  );
}
