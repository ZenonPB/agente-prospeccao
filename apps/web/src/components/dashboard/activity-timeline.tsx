'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useLeads } from '@/hooks/use-api';

const statusConfig: Record<string, { icon: string; label: string; color: string }> = {
  NOVO: { icon: '📋', label: 'Encontrado', color: 'bg-blue-100 text-blue-700' },
  ANALISADO: { icon: '🔍', label: 'Analisado', color: 'bg-purple-100 text-purple-700' },
  QUALIFICADO: { icon: '✅', label: 'Apto', color: 'bg-emerald-100 text-emerald-700' },
  DESQUALIFICADO: { icon: '❌', label: 'Desqualificado', color: 'bg-gray-100 text-gray-700' },
  CONTATADO: { icon: '📧', label: 'Mensagem enviada', color: 'bg-amber-100 text-amber-700' },
  RESPONDIDO: { icon: '💬', label: 'Respondeu', color: 'bg-purple-100 text-purple-700' },
  REUNIAO_MARCADA: { icon: '📅', label: 'Reunião', color: 'bg-pink-100 text-pink-700' },
  PERDIDO: { icon: '🚫', label: 'Perdido', color: 'bg-red-100 text-red-700' },
};

export function ActivityTimeline() {
  const { data, isLoading } = useLeads({ limit: 5 });

  const leads = data?.leads || [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Leads Recentes</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="py-4 text-center text-sm text-muted-foreground">Carregando...</p>
        ) : leads.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            Nenhum lead encontrado ainda. Crie uma campanha para começar.
          </p>
        ) : (
          <div className="space-y-4">
            {leads.map((lead) => {
              const config = statusConfig[lead.status] || { icon: '📋', label: lead.status, color: 'bg-muted text-muted-foreground' };
              return (
                <div key={lead.id} className="flex items-start gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-lg">
                    {config.icon}
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{lead.company_name}</span>
                      <Badge variant="secondary" className={config.color}>
                        {config.label}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {lead.category || 'Sem categoria'} • {lead.city || 'Não informado'}{lead.state ? `, ${lead.state}` : ''}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(lead.created_at).toLocaleDateString('pt-BR', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
