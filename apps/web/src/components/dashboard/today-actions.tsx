'use client';

import { useMemo } from 'react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Loader2, UserPlus, CalendarClock, Target, AlertTriangle } from 'lucide-react';
import { useLeads, useAssignLead, useSlaAlerts } from '@/hooks/use-api';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';

function endOfTodayIso(): string {
  const d = new Date();
  d.setHours(23, 59, 59, 999);
  return d.toISOString();
}

function formatDue(date?: string): string {
  if (!date) return '';
  const due = new Date(date);
  const diffDays = Math.floor((due.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) {
    return `atrasado há ${Math.abs(diffDays)} dia${Math.abs(diffDays) !== 1 ? 's' : ''}`;
  }
  if (diffDays === 0) return 'hoje';
  return `em ${diffDays} dia${diffDays !== 1 ? 's' : ''}`;
}

function ActionsSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2].map((i) => (
        <div key={i} className="flex items-center gap-3 rounded-lg border p-3">
          <Skeleton className="h-8 w-8 rounded-full" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function TodayActions() {
  const { data: session } = useSession();
  const currentUserId = (session?.user as { id?: string } | undefined)?.id;
  const assignLead = useAssignLead();
  const dueIso = useMemo(() => endOfTodayIso(), []);

  const { data: overdueData, isLoading: loadingDue } = useLeads({
    next_action_before: dueIso,
    limit: 5,
  });
  const { data: unassignedData, isLoading: loadingUnassigned } = useLeads({
    status: 'QUALIFICADO',
    assigned: 'none',
    limit: 5,
  });
  const { data: slaData, isLoading: loadingSla } = useSlaAlerts(5);

  const overdue = overdueData?.leads || [];
  const unassigned = unassignedData?.leads || [];
  const slaAlerts = slaData?.alerts || [];
  const loading = loadingDue || loadingUnassigned || loadingSla;

  const onAssignToMe = (leadId: string) => {
    if (!currentUserId) return;
    assignLead.mutate(
      { id: leadId, assignedToId: currentUserId },
      {
        onSuccess: () => toast.success('Lead atribuído a você.'),
        onError: () => toast.error('Não foi possível atribuir o lead.'),
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ações de hoje</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {loading ? (
          <ActionsSkeleton />
        ) : (
          <>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="flex items-center gap-1.5 text-sm font-medium">
                  <CalendarClock className="h-4 w-4 text-amber-600" aria-hidden="true" />
                  Follow-up vencido / hoje
                </p>
                <Badge variant="secondary" className="text-xs">
                  {overdue.length}
                </Badge>
              </div>
              {overdue.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhuma ação marcada para hoje.</p>
              ) : (
                <div className="space-y-2">
                  {overdue.map((lead) => (
                    <Link
                      key={lead.id}
                      href={`/oportunidades/${lead.id}`}
                      className="flex items-center justify-between gap-2 rounded-lg border p-3 transition-colors hover:border-primary hover:bg-muted/50"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{lead.company_name}</p>
                        <p className="text-xs text-muted-foreground">{formatDue(lead.next_action_at)}</p>
                      </div>
                      {lead.qualification_score != null && (
                        <Badge className="bg-emerald-100 text-emerald-700 text-xs shrink-0">
                          {lead.qualification_score}
                        </Badge>
                      )}
                    </Link>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="flex items-center gap-1.5 text-sm font-medium">
                  <Target className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                  Aptos sem dono
                </p>
                <Badge variant="secondary" className="text-xs">
                  {unassigned.length}
                </Badge>
              </div>
              {unassigned.length === 0 ? (
                <p className="text-sm text-muted-foreground">Todos os aptos estão atribuídos.</p>
              ) : (
                <div className="space-y-2">
                  {unassigned.map((lead) => (
                    <div
                      key={lead.id}
                      className="flex items-center justify-between gap-2 rounded-lg border p-3"
                    >
                      <Link
                        href={`/oportunidades/${lead.id}`}
                        className="min-w-0 flex-1 transition-colors hover:text-primary"
                      >
                        <p className="truncate text-sm font-medium">{lead.company_name}</p>
                        <p className="text-xs text-muted-foreground">
                          {lead.category || 'Sem categoria'} • {lead.city || '—'}
                        </p>
                      </Link>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 shrink-0 gap-1 text-[11px]"
                        disabled={assignLead.isPending && assignLead.variables?.id === lead.id}
                        onClick={() => onAssignToMe(lead.id)}
                      >
                        {assignLead.isPending && assignLead.variables?.id === lead.id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <UserPlus className="h-3 w-3" />
                        )}
                        Atribuir a mim
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="flex items-center gap-1.5 text-sm font-medium">
                  <AlertTriangle className="h-4 w-4 text-red-500" aria-hidden="true" />
                  Leads parados (SLA)
                </p>
                <Badge variant="destructive" className="text-xs">
                  {slaAlerts.length}
                </Badge>
              </div>
              {slaAlerts.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhum lead parado (SLA) — tudo em dia.</p>
              ) : (
                <div className="space-y-2">
                  {slaAlerts.map((alert) => (
                    <Link
                      key={alert.id}
                      href={`/oportunidades/${alert.id}`}
                      className="flex items-center justify-between gap-2 rounded-lg border border-red-100 p-3 transition-colors hover:border-primary hover:bg-muted/50"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{alert.company_name}</p>
                        <p className="text-xs text-muted-foreground">{alert.alert_label}</p>
                      </div>
                      {alert.qualification_score != null && (
                        <Badge className="bg-emerald-100 text-emerald-700 text-xs shrink-0">
                          {alert.qualification_score}
                        </Badge>
                      )}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
