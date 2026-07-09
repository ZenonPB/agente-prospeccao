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
    description: 'Score 88 - SECURITY_FIX',
    timestamp: '2 min atrás',
    lead_name: 'Tijuca Restaurante & Bar',
  },
  {
    id: '2',
    type: 'lead_collected',
    description: 'Coletado via Google Places',
    timestamp: '5 min atrás',
    lead_name: 'Restaurante Pau Seco',
  },
  {
    id: '3',
    type: 'contact_sent',
    description: 'E-mail enviado via Resend',
    timestamp: '15 min atrás',
    lead_name: 'Academia Fitness Center',
  },
  {
    id: '4',
    type: 'response_received',
    description: 'Resposta recebida - Interessado',
    timestamp: '1 hora atrás',
    lead_name: 'Clínica Saúde Integral',
  },
  {
    id: '5',
    type: 'meeting_scheduled',
    description: 'Reunião agendada para 15/07',
    timestamp: '2 horas atrás',
    lead_name: 'Indústria MetalWorks',
  },
];

const activityIcons = {
  lead_collected: '📋',
  lead_qualified: '✅',
  contact_sent: '📧',
  response_received: '💬',
  meeting_scheduled: '📅',
};

const activityColors = {
  lead_collected: 'bg-blue-100 text-blue-800',
  lead_qualified: 'bg-green-100 text-green-800',
  contact_sent: 'bg-yellow-100 text-yellow-800',
  response_received: 'bg-purple-100 text-purple-800',
  meeting_scheduled: 'bg-pink-100 text-pink-800',
};

export function ActivityTimeline() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Atividade Recente</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {activities.map((activity) => (
            <div key={activity.id} className="flex items-start gap-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-sm">
                {activityIcons[activity.type]}
              </div>
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{activity.lead_name}</span>
                  <Badge variant="secondary" className={activityColors[activity.type]}>
                    {activity.type.replace('_', ' ')}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">{activity.description}</p>
                <p className="text-xs text-muted-foreground">{activity.timestamp}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}