'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface Activity {
  id: string;
  type: 'lead_collected' | 'lead_qualified' | 'contact_sent' | 'response_received' | 'meeting_scheduled';
  description: string;
  timestamp: string;
  lead_name?: string;
}

const activities: Activity[] = [
  {
    id: '1',
    type: 'lead_qualified',
    description: 'Empresa com site com problemas de segurança',
    timestamp: '2 min atrás',
    lead_name: 'Tijuca Restaurante & Bar',
  },
  {
    id: '2',
    type: 'lead_collected',
    description: 'Encontrada no Google Maps',
    timestamp: '5 min atrás',
    lead_name: 'Restaurante Pau Seco',
  },
  {
    id: '3',
    type: 'contact_sent',
    description: 'E-mail de apresentação enviado',
    timestamp: '15 min atrás',
    lead_name: 'Academia Fitness Center',
  },
  {
    id: '4',
    type: 'response_received',
    description: 'Respondeu — quer saber mais',
    timestamp: '1 hora atrás',
    lead_name: 'Clínica Saúde Integral',
  },
  {
    id: '5',
    type: 'meeting_scheduled',
    description: 'Reunião marcada para 15/07 às 14h',
    timestamp: '2 horas atrás',
    lead_name: 'Indústria MetalWorks',
  },
];

const activityConfig = {
  lead_collected: { icon: '📋', label: 'Encontrado', color: 'bg-blue-100 text-blue-700' },
  lead_qualified: { icon: '✅', label: 'Apto', color: 'bg-emerald-100 text-emerald-700' },
  contact_sent: { icon: '📧', label: 'Mensagem enviada', color: 'bg-amber-100 text-amber-700' },
  response_received: { icon: '💬', label: 'Respondeu', color: 'bg-purple-100 text-purple-700' },
  meeting_scheduled: { icon: '📅', label: 'Reunião', color: 'bg-pink-100 text-pink-700' },
};

export function ActivityTimeline() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Atividade Recente</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {activities.map((activity) => {
            const config = activityConfig[activity.type];
            return (
              <div key={activity.id} className="flex items-start gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-lg">
                  {config.icon}
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{activity.lead_name}</span>
                    <Badge variant="secondary" className={config.color}>
                      {config.label}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{activity.description}</p>
                  <p className="text-xs text-muted-foreground">{activity.timestamp}</p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}