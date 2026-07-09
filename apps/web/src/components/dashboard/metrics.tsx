'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, Target, Phone, Calendar, TrendingUp } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
}

export function MetricCard({ title, value, description, icon, trend }: MetricCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <div className="text-muted-foreground">{icon}</div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
        {trend && (
          <div className={`flex items-center text-xs ${trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : 'text-muted-foreground'}`}>
            <TrendingUp className="mr-1 h-3 w-3" />
            {trend === 'up' ? '+12%' : trend === 'down' ? '-5%' : '0%'}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function MetricsGrid() {
  // Mock data - replace with real API calls
  const metrics = [
    {
      title: 'Total de Leads',
      value: '1,234',
      description: '+120 este mês',
      icon: <Users className="h-4 w-4" />,
      trend: 'up' as const,
    },
    {
      title: 'Qualificados',
      value: '456',
      description: 'Score >= 60',
      icon: <Target className="h-4 w-4" />,
      trend: 'up' as const,
    },
    {
      title: 'Contatados',
      value: '89',
      description: 'Últimos 7 dias',
      icon: <Phone className="h-4 w-4" />,
      trend: 'neutral' as const,
    },
    {
      title: 'Reuniões',
      value: '12',
      description: 'Agendadas',
      icon: <Calendar className="h-4 w-4" />,
      trend: 'up' as const,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric) => (
        <MetricCard key={metric.title} {...metric} />
      ))}
    </div>
  );
}