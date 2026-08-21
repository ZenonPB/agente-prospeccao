'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { LeadActivityItem } from '@/types';

const statusLabels: Record<string, string> = {
  NOVO: 'Novo',
  ANALISADO: 'Analisado',
  QUALIFICADO: 'Apto para contato',
  DESQUALIFICADO: 'Desqualificado',
  CONTATADO: 'Contatado',
  RESPONDIDO: 'Respondeu',
  REUNIAO_MARCADA: 'Reunião marcada',
  REUNIAO_FEITA: 'Reunião realizada',
  PROPOSTA_ENVIADA: 'Proposta enviada',
  PERDIDO: 'Perdido',
};

const activityLabels: Record<string, string> = {
  CREATED: 'Lead criado',
  ASSIGNED: 'Atribuído a consultor',
  UNASSIGNED: 'Lead desatribuído',
  STATUS_CHANGED: 'Status alterado',
  MESSAGE_GENERATED: 'Mensagem gerada',
  CONTACTED: 'Contato realizado',
  RESPONDED: 'Lead respondeu',
  MEETING_SCHEDULED: 'Reunião marcada',
  PROPOSAL_SENT: 'Proposta enviada',
  LOST: 'Lead perdido',
  CONVERTED: 'Conversão registrada',
  CONTACT_ENRICHED: 'Decisores enriquecidos',
  LINKEDIN_ASSOCIATED: 'Perfil LinkedIn associado',
};

interface ActivitiesTabProps {
  activities: LeadActivityItem[];
}

export function ActivitiesTab({ activities }: ActivitiesTabProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Trilha de atividades</CardTitle>
      </CardHeader>
      <CardContent>
        {activities.length > 0 ? (
          <ol className="relative space-y-4 border-l pl-6">
            {activities.map((activity) => (
              <li key={activity.id} className="relative">
                <span className="absolute -left-[31px] flex h-4 w-4 items-center justify-center rounded-full border-2 border-background bg-primary" />
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium">{activityLabels[activity.action] || activity.action}</span>
                  {activity.user_name && (
                    <span className="text-xs text-muted-foreground">por {activity.user_name}</span>
                  )}
                  <span className="ml-auto text-xs text-muted-foreground">
                    {new Date(activity.created_at).toLocaleString('pt-BR')}
                  </span>
                </div>
                {activity.status_from && activity.status_to && (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {statusLabels[activity.status_from] || activity.status_from} → {statusLabels[activity.status_to] || activity.status_to}
                  </p>
                )}
                {activity.detail && (
                  <p className="mt-0.5 text-xs text-muted-foreground">{activity.detail}</p>
                )}
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">
            Nenhuma atividade registrada ainda.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
