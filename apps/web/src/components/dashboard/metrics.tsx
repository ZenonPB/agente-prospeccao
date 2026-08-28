'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, Target, Phone, Calendar, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react';
import { useLeadStats } from '@/hooks/use-api';
import { Skeleton } from '@/components/ui/skeleton';
import { AnimatedNumber, Reveal } from '@/components/ui/motion';

interface MetricCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon: React.ReactNode;
  iconClassName?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  onClick?: () => void;
  active?: boolean;
}

export function MetricCard({ title, value, description, icon, iconClassName, trend, trendValue, onClick, active }: MetricCardProps) {
  const interactive = Boolean(onClick);
  return (
    <Card
      className={`card-lift ${
        interactive ? 'cursor-pointer hover:ring-primary/40' : ''
      } ${active ? 'ring-2 ring-primary' : ''}`}
      onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick?.();
              }
            }
          : undefined
      }
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <div className={`rounded-lg p-2 transition-colors ${iconClassName ?? 'bg-primary/10 text-primary'}`}>{icon}</div>
      </CardHeader>
      <CardContent>
        <div className="font-heading text-2xl font-semibold tracking-tight">
          {typeof value === 'number' ? <AnimatedNumber value={value} /> : value}
        </div>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
        {trend && trendValue && (
          <div className={`mt-1 flex items-center text-xs font-medium ${
            trend === 'up' ? 'text-emerald-600' : trend === 'down' ? 'text-red-600' : 'text-muted-foreground'
          }`}>
            {trend === 'up' ? (
              <TrendingUp className="mr-1 h-3 w-3" />
            ) : trend === 'down' ? (
              <TrendingDown className="mr-1 h-3 w-3" />
            ) : null}
            {trendValue}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MetricCardSkeleton() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-8 rounded-md" />
      </CardHeader>
      <CardContent>
        <Skeleton className="mb-1 h-7 w-16" />
        <Skeleton className="h-3 w-20" />
      </CardContent>
    </Card>
  );
}

interface MetricsGridProps {
  onFilter?: (metric: string | null) => void;
  activeFilter?: string | null;
}

export function MetricsGrid({ onFilter, activeFilter }: MetricsGridProps) {
  const { data: stats, isLoading, isError, error } = useLeadStats();

  if (isError) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="border-red-200 bg-red-50/50">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-red-600">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <p className="text-sm font-medium">Erro ao carregar</p>
              </div>
              <p className="mt-1 text-xs text-red-500">
                {error instanceof Error ? error.message : 'Tente novamente mais tarde'}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <MetricCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  const metrics = [
    {
      id: 'total',
      title: 'Encontradas',
      value: stats?.total || 0,
      description: 'empresas capturadas nas buscas',
      icon: <Users className="h-4 w-4" />,
      iconClassName: 'bg-sky-500/10 text-sky-600 dark:text-sky-400',
    },
    {
      id: 'qualified',
      title: 'Prontas para contato',
      value: stats?.qualified_count || 0,
      description: `bem avaliadas pela IA (${stats?.qualified_pct || 0}%)`,
      icon: <Target className="h-4 w-4" />,
      iconClassName: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    },
    {
      id: 'contacted',
      title: 'Em conversa',
      value: (stats?.contacted_count) || 0,
      description: 'aguardando resposta',
      icon: <Phone className="h-4 w-4" />,
      iconClassName: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
    },
    {
      id: 'meetings',
      title: 'Reuniões marcadas',
      value: stats?.meetings_count || 0,
      description: 'resultados do time',
      icon: <Calendar className="h-4 w-4" />,
      iconClassName: 'bg-violet-500/10 text-violet-600 dark:text-violet-400',
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric, i) => (
        <Reveal key={metric.id} delay={i * 70}>
          <MetricCard
            {...metric}
            onClick={() => onFilter?.(activeFilter === metric.id ? null : metric.id)}
            active={activeFilter === metric.id}
          />
        </Reveal>
      ))}
    </div>
  );
}
