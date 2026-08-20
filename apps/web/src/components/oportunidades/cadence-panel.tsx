"use client";

import { useCallback } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CalendarClock, Send, Play, Ban, Loader2, ShieldAlert, Eye, MousePointerClick } from "lucide-react";
import { toast } from "sonner";
import {
  useLeadCadence,
  useStartCadence,
  useSendCadenceStep,
  useOptOutLead,
} from "@/hooks/use-api";
import type { FollowUpItem } from "@/types";

const STATUS_BADGE: Record<string, { label: string; variant: "outline" | "secondary" | "default" | "destructive" }> = {
  PENDING: { label: "Agendado", variant: "outline" },
  SENT: { label: "Enviado", variant: "secondary" },
  SKIPPED: { label: "Pulado", variant: "outline" },
  CANCELLED: { label: "Cancelado", variant: "outline" },
};

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export function CadencePanel({ leadId }: { leadId: string }) {
  const { data, isLoading, refetch } = useLeadCadence(leadId);
  const startCadence = useStartCadence();
  const sendStep = useSendCadenceStep();
  const optOut = useOptOutLead();

  const followUps: FollowUpItem[] = data?.follow_ups || [];
  const optOutActive = data?.opt_out || false;

  const handleStart = useCallback(async () => {
    try {
      const result = await startCadence.mutateAsync(leadId);
      const days = result?.schedule?.length === 4 ? result.schedule : null;
      toast.success(
        days
          ? `Mensagens geradas e agendadas (dias ${days.join(", ")}).`
          : "Mensagens geradas e agendadas.",
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao gerar as mensagens.");
    }
  }, [leadId, startCadence]);

  const handleSend = useCallback(
    async (step: string) => {
      try {
        await sendStep.mutateAsync({ id: leadId, step });
        toast.success("Etapa enviada.");
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Erro ao enviar etapa.");
      }
    },
    [leadId, sendStep],
  );

  const handleOptOut = useCallback(async () => {
    try {
      await optOut.mutateAsync(leadId);
      toast.success("Registrado: esta empresa não receberá mais mensagens.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Não foi possível registrar. Tente de novo.");
    }
  }, [leadId, optOut]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-muted-foreground" />
          Mensagens de acompanhamento
        </CardTitle>
        <CardDescription>
          Etapas programadas para acompanhar a empresa — cada uma mostra a data agendada abaixo
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-6 w-20" />
              </div>
            ))}
          </div>
        ) : optOutActive ? (
          <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            Esta empresa pediu para não receber mensagens — o acompanhamento está pausado.
          </div>
        ) : followUps.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed p-4 text-center">
            <p className="text-sm text-muted-foreground">
              Nenhuma mensagem agendada ainda. Gere e agende as mensagens de acompanhamento.
            </p>
            <Button
              size="sm"
              onClick={handleStart}
              disabled={startCadence.isPending}
            >
              {startCadence.isPending ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-1.5 h-4 w-4" />
              )}
              Gerar mensagens
            </Button>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {followUps.map((fu) => {
                const badge = STATUS_BADGE[fu.status || "PENDING"];
                const isSent = fu.status === "SENT";
                const isPending = fu.status === "PENDING";
                return (
                  <div
                    key={fu.id}
                    className="flex items-center justify-between gap-3 rounded-lg border p-2.5"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{fu.label}</p>
                      <p className="text-xs text-muted-foreground">
                        Agendado {formatDate(fu.scheduled_at)}
                        {isSent && fu.sent_at ? ` · enviado ${formatDate(fu.sent_at)}` : ""}
                      </p>
                      {isSent && (fu.opened_at || fu.clicked_at) && (
                        <div className="mt-1 flex items-center gap-2 text-xs">
                          {fu.opened_at && (
                            <span className="inline-flex items-center gap-1 text-emerald-600">
                              <Eye className="h-3 w-3" /> abriu
                            </span>
                          )}
                          {fu.clicked_at && (
                            <span className="inline-flex items-center gap-1 text-emerald-600">
                              <MousePointerClick className="h-3 w-3" /> clicou
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant={badge.variant}>{badge.label}</Badge>
                      {isPending && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSend(fu.step)}
                          disabled={sendStep.isPending}
                        >
                          {sendStep.isPending ? (
                            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Send className="mr-1 h-3.5 w-3.5" />
                          )}
                          Enviar
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="flex items-center justify-between pt-1">
              <button
                type="button"
                onClick={() => refetch()}
                className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
              >
                Atualizar
              </button>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={handleOptOut}
                disabled={optOut.isPending}
              >
                <Ban className="mr-1 h-3.5 w-3.5" />
                Não enviar mais mensagens
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
