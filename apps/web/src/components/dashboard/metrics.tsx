'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, Target, Phone, Calendar, TrendingUp, TrendingDown } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  onClick?: () => void;
  active?: boolean;
}

export function MetricCard({ title, value, description, icon, trend, trendValue, onClick, active }: MetricCardProps) {
  return (
    <Card 
      className={`transition-all hover:shadow-md ${
        onClick ? 'cursor-pointer' : ''
      } ${active ? 'ring-2 ring-primary' : ''}`}
      onClick={onClick}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <div className="rounded-md bg-muted p-2">{icon}</div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
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

interface MetricsGridProps {
  onFilter?: (metric: string | null) => void;
  activeFilter?: string | null;
}

export function MetricsGrid({ onFilter, activeFilter }: MetricsGridProps) {
  const metrics = [
    {
      id: 'total',
      title: 'Encontrados',
      value: '1.234',
      description: 'leads capturados',
      icon: <Users className="h-4 w-4 text-muted-foreground" />,
      trend: 'up' as const,
      trendValue: '+120 este mês',
    },
    {
      id: 'qualified',
      title: 'Aptos para contato',
      value: '456',
      description: 'score de aptidão >= 60',
      icon: <Target className="h-4 w-4 text-muted-foreground" />,
      trend: 'up' as const,
      trendValue: '+32 esta semana',
    },
    {
      id: 'contacted',
      title: 'Mensagens enviadas',
      value: '89',
      description: 'últimos 7 dias',
      icon: <Phone className="h-4 w-4 text-muted-foreground" />,
      trend: 'neutral' as const,
      trendValue: 'estável',
    },
    {
      id: 'meetings',
      title: 'Reuniões marcadas',
      value: '12',
      description: 'agendadas',
      icon: <Calendar className="h-4 w-4 text-muted-foreground" />,
      trend: 'up' as const,
      trendValue: '+3 esta semana',
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric) => (
        <MetricCard
          key={metric.id}
          {...metric}
          onClick={() => onFilter?.(activeFilter === metric.id ? null : metric.id)}
          active={activeFilter === metric.id}
        />
      ))}
    </div>
  );
}