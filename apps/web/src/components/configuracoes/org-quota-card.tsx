"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Gauge, AlertTriangle, Loader2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { useOrgMembership, useOrgUsage, usePatchOrgSettings } from "@/hooks/use-api";
import type { ProviderUsageItem } from "@/types";

const KEY_LABELS: Record<string, string> = {
  GOOGLE_API_KEY: "Busca de Empresas (Google)",
  GROQ_API_KEY: "Processamento por IA (Groq)",
};

function barColor(pct: number): string {
  if (pct >= 80) return "bg-red-500";
  if (pct >= 60) return "bg-amber-500";
  return "bg-emerald-500";
}

function textColor(pct: number): string {
  if (pct >= 80) return "text-red-600";
  if (pct >= 60) return "text-amber-600";
  return "text-emerald-600";
}

function QuotaForm({ usage, orgId }: { usage: ProviderUsageItem[]; orgId: string }) {
  const patchSettings = usePatchOrgSettings();
  const [pending, setPending] = useState(false);
  const [limits, setLimits] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    usage.forEach((u) => {
      init[u.key_name] = String(u.limit);
    });
    return init;
  });

  const handleSave = async () => {
    const apiQuota: Record<string, number> = {};
    for (const u of usage) {
      const value = Number(limits[u.key_name]);
      if (!Number.isInteger(value) || value < 1) {
        toast.error(`Limite inválido para ${KEY_LABELS[u.key_name] ?? u.key_name}.`);
        return;
      }
      apiQuota[u.key_name] = value;
    }
    setPending(true);
    try {
      await patchSettings.mutateAsync({ orgId, data: { api_quota: apiQuota } });
      toast.success("Cotas de uso atualizadas.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao salvar cotas.");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="space-y-4">
      {usage.map((u) => {
        const label = KEY_LABELS[u.key_name] ?? u.key_name;
        const color = barColor(u.pct);
        return (
          <div key={u.key_name} className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{label}</span>
              <span className={`font-medium tabular-nums ${textColor(u.pct)}`}>
                {u.used}/{u.limit} · {u.pct}%
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full ${color}`}
                style={{ width: `${Math.min(100, u.pct)}%` }}
                role="progressbar"
                aria-valuenow={u.pct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${label}: ${u.pct}% da cota diária`}
              />
            </div>
            <div className="flex items-center gap-2 pt-1">
              <Label htmlFor={`quota-${u.key_name}`} className="text-[11px] text-muted-foreground">
                Limite diário
              </Label>
              <Input
                id={`quota-${u.key_name}`}
                type="number"
                min={1}
                className="h-7 w-24"
                value={limits[u.key_name]}
                onChange={(e) =>
                  setLimits((prev) => ({ ...prev, [u.key_name]: e.target.value }))
                }
              />
            </div>
          </div>
        );
      })}
      <div className="pt-1">
        <Button size="sm" disabled={pending} onClick={handleSave}>
          {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Salvar cotas
        </Button>
      </div>
    </div>
  );
}

export function OrgQuotaCard() {
  const { data: membership } = useOrgMembership();
  const orgId = membership?.organization?.id;
  const myRole = membership?.membership?.role;
  const canManage = myRole === "OWNER" || myRole === "ADMIN";
  const { data: usageData, isLoading } = useOrgUsage(orgId);

  const usage = usageData?.usage || [];
  const alert = usageData?.alert || false;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-5 w-5 text-muted-foreground" />
          Uso Diário de Buscas e Inteligência Artificial
        </CardTitle>
        <CardDescription>
          Acompanhe quantas buscas e análises por IA foram realizadas no dia de hoje.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {alert && (
          <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
            Atenção: uma ou mais cotas diárias passaram de 80%.
          </div>
        )}
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : usage.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma cota configurada para esta organização.
          </p>
        ) : canManage && orgId ? (
          <QuotaForm key={orgId} usage={usage} orgId={orgId} />
        ) : (
          <div className="space-y-3">
            {usage.map((u) => {
              const label = KEY_LABELS[u.key_name] ?? u.key_name;
              return (
                <div key={u.key_name} className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{label}</span>
                    <span className={`font-medium tabular-nums ${textColor(u.pct)}`}>
                      {u.used}/{u.limit} · {u.pct}%
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full rounded-full ${barColor(u.pct)}`}
                      style={{ width: `${Math.min(100, u.pct)}%` }}
                    />
                  </div>
                </div>
              );
            })}
            <p className="flex items-center gap-2 pt-1 text-xs text-muted-foreground">
              <ShieldCheck className="h-4 w-4 shrink-0" />
              Apenas o dono ou um administrador pode alterar os limites.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
