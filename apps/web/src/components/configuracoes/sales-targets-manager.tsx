"use client";

import { useState, useMemo } from "react";
import { useSalesTargets, useUpsertSalesTarget, useDeleteSalesTarget } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Target, Plus, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import type { OrganizationMember } from "@/types";

function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

export function SalesTargetsManager({ orgId, members }: { orgId: string; members: OrganizationMember[] }) {
  const month = currentMonth();
  const { data, isLoading } = useSalesTargets(orgId, month);
  const upsert = useUpsertSalesTarget();
  const remove = useDeleteSalesTarget();

  const [open, setOpen] = useState(false);
  const [userId, setUserId] = useState("");
  const [meetingsTarget, setMeetingsTarget] = useState("0");
  const [revenueTarget, setRevenueTarget] = useState("0");
  const [pending, setPending] = useState(false);

  const targets = useMemo(() => data?.targets || [], [data]);
  const targetByUser = useMemo(() => {
    const map: Record<string, (typeof targets)[number]> = {};
    targets.forEach((t) => (map[t.user_id] = t));
    return map;
  }, [targets]);

  const handleSave = () => {
    if (!userId) {
      toast.error("Selecione um consultor.");
      return;
    }
    setPending(true);
    upsert.mutate(
      {
        orgId,
        data: {
          user_id: userId,
          month,
          meetings_target: parseInt(meetingsTarget || "0", 10) || 0,
          revenue_target: parseFloat(revenueTarget || "0") || 0,
        },
      },
      {
        onSuccess: () => {
          toast.success("Meta de vendas salva.");
          setOpen(false);
        },
        onError: (err) => toast.error(err instanceof Error ? err.message : "Erro ao salvar meta."),
        onSettled: () => setPending(false),
      }
    );
  };

  return (
    <Card>
      <CardHeader className="flex-col items-stretch gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <CardTitle className="flex items-center gap-2">
            <Target className="h-4 w-4 text-amber-500" />
            Metas de vendas ({month})
          </CardTitle>
          <CardDescription>
            Meta mensal de reuniões e receita por consultor — aparece no relatório como atingimento.
          </CardDescription>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger render={<Button size="sm" className="h-11 w-full gap-1 sm:h-9 sm:w-auto"><Plus className="h-4 w-4" /> Nova meta</Button>} />
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Definir meta de vendas</DialogTitle>
              <DialogDescription>
                Meta mensal para {month}. O gestor acompanha o atingimento no relatório.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="target-user">Consultor</Label>
                <select
                  id="target-user"
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={userId}
                  onChange={(e) => {
                    const id = e.target.value;
                    setUserId(id);
                    const existing = targetByUser[id];
                    setMeetingsTarget(existing ? String(existing.meetings_target) : "0");
                    setRevenueTarget(existing ? String(existing.revenue_target) : "0");
                  }}
                >
                  <option value="">Selecione...</option>
                  {members.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.name || m.email || m.user_id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="target-meetings">Meta de reuniões</Label>
                  <Input
                    id="target-meetings"
                    type="number"
                    min="0"
                    value={meetingsTarget}
                    onChange={(e) => setMeetingsTarget(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="target-revenue">Meta de receita (R$)</Label>
                  <Input
                    id="target-revenue"
                    type="number"
                    min="0"
                    step="0.01"
                    value={revenueTarget}
                    onChange={(e) => setRevenueTarget(e.target.value)}
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" className="h-11" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button className="h-11" onClick={handleSave} disabled={pending}>
                {pending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Salvar meta
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : targets.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma meta definida para este mês. Clique em &quot;Nova meta&quot; para começar.
          </p>
        ) : (
          targets.map((t) => (
            <div key={t.id} className="flex min-w-0 items-center justify-between gap-3 rounded-lg border px-3 py-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{t.name || t.email || t.user_id}</p>
                <p className="text-xs text-muted-foreground">
                  {t.meetings_target} reuniões · R$ {t.revenue_target.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                </p>
              </div>
              <AlertDialog>
                <AlertDialogTrigger render={<Button variant="ghost" size="icon" className="h-11 w-11 shrink-0 text-destructive hover:bg-destructive/10" />}>
                  <Trash2 className="h-4 w-4" />
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Remover meta de {t.name || t.email}?</AlertDialogTitle>
                    <AlertDialogDescription>
                      A meta deste consultor para {t.month} será excluída.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancelar</AlertDialogCancel>
                    <AlertDialogAction
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      onClick={() =>
                        remove.mutate(
                          { orgId, targetId: t.id },
                          {
                            onSuccess: () => toast.success("Meta removida."),
                            onError: (err) => toast.error(err instanceof Error ? err.message : "Erro ao remover meta."),
                          }
                        )
                      }
                    >
                      Remover
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
