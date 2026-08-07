"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Send, Loader2, ShieldCheck, Gauge } from "lucide-react";
import { toast } from "sonner";
import { useOrgMembership, usePatchOrgSettings } from "@/hooks/use-api";
import type { OrgMembership } from "@/types";

const DEFAULT_LIMIT = 40;

type OrgInfo = NonNullable<OrgMembership>["organization"];

function ThrottleForm({
  org,
  orgId,
}: {
  org: OrgInfo;
  orgId: string;
}) {
  const patchSettings = usePatchOrgSettings();
  const [pending, setPending] = useState(false);
  // Inicialização lazy a partir dos dados já carregados da org (sem setState em
  // effect): o componente é remontado via `key={org.id}` ao trocar de org.
  const [limit, setLimit] = useState(() => String(org.daily_email_limit ?? DEFAULT_LIMIT));
  const [windowStart, setWindowStart] = useState(() => org.send_window_start ?? "09:00");
  const [windowEnd, setWindowEnd] = useState(() => org.send_window_end ?? "17:00");
  const [emailFrom, setEmailFrom] = useState(() => org.email_from ?? "");

  const sendsToday = org.sends_today ?? 0;
  const limitNum = Number.isInteger(Number(limit)) ? Number(limit) : DEFAULT_LIMIT;
  const usagePercent = Math.min(100, Math.round((sendsToday / Math.max(1, limitNum)) * 100));

  const handleSave = async () => {
    if (!Number.isInteger(Number(limit)) || Number(limit) < 1 || Number(limit) > 500) {
      toast.error("O limite diário deve ser um inteiro entre 1 e 500.");
      return;
    }
    setPending(true);
    try {
      await patchSettings.mutateAsync({
        orgId,
        data: {
          daily_email_limit: Number(limit),
          send_window_start: windowStart,
          send_window_end: windowEnd,
          email_from: emailFrom.trim() || "",
        },
      });
      toast.success("Configurações de envio salvas.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao salvar configuração.");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center gap-2">
        <Gauge className="h-4 w-4 text-muted-foreground" />
        <p className="text-sm font-medium">Throttling de envio (warmup)</p>
      </div>
      <p className="text-xs text-muted-foreground">
        O envio automático respeita um limite diário e uma janela de espalhamento
        (fuso do servidor) para não disparar rajadas e queimar a reputação do remetente.
      </p>
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">
            Envios hoje: {sendsToday} / {limitNum}
          </span>
          <span className={usagePercent >= 90 ? "font-medium text-destructive" : "text-muted-foreground"}>
            {usagePercent}%
          </span>
        </div>
        <Progress value={usagePercent} aria-label="Envios diários utilizados" />
      </div>
      <div className="grid grid-cols-1 gap-3 pt-1 sm:grid-cols-3">
        <div className="space-y-1">
          <Label htmlFor="daily-limit">Limite diário</Label>
          <Input
            id="daily-limit"
            type="number"
            min={1}
            max={500}
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="window-start">Janela início</Label>
          <Input
            id="window-start"
            type="time"
            value={windowStart}
            onChange={(e) => setWindowStart(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="window-end">Janela fim</Label>
          <Input
            id="window-end"
            type="time"
            value={windowEnd}
            onChange={(e) => setWindowEnd(e.target.value)}
          />
        </div>
      </div>
      <div className="space-y-1 pt-1">
        <Label htmlFor="org-email-from">Remetente da organização</Label>
        <Input
          id="org-email-from"
          type="email"
          placeholder="vendas@empresa.com.br"
          value={emailFrom}
          onChange={(e) => setEmailFrom(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          Cada consultor pode ter o próprio remetente (definido na tela de membros).
          Este é o remetente padrão da org quando o consultor não tem um dedicado.
        </p>
      </div>
      <div className="pt-1">
        <Button size="sm" disabled={pending} onClick={handleSave}>
          {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Salvar configurações
        </Button>
      </div>
    </div>
  );
}

export function OrgSendSettings() {
  const { data: membership } = useOrgMembership();
  const patchSettings = usePatchOrgSettings();
  const orgId = membership?.organization?.id;
  const autoSend = membership?.organization?.auto_send_email ?? false;
  const myRole = membership?.membership?.role;
  const canManage = myRole === "OWNER" || myRole === "ADMIN";

  const [pending, setPending] = useState(false);

  const handleToggle = async (checked: boolean) => {
    if (!orgId) return;
    setPending(true);
    try {
      await patchSettings.mutateAsync({ orgId, data: { auto_send_email: checked } });
      toast.success(
        checked
          ? "Envio automático de follow-ups ativado."
          : "Envio automático desativado — humano-no-loop.",
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao atualizar configuração.");
    } finally {
      setPending(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Send className="h-5 w-5 text-muted-foreground" />
          Envio de follow-ups
        </CardTitle>
        <CardDescription>
          Como a cadência de dias 0/3/7/14 é enviada por esta organização
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <p className="text-sm font-medium">Envio automático por e-mail</p>
            <p className="text-xs text-muted-foreground">
              Ao ligar, o sistema envia os follow-ups quando a data agendada vence
              (via SMTP). Desligado (padrão), o consultor revisa e envia cada etapa
              manualmente — humano no loop.
            </p>
          </div>
          {canManage ? (
            pending ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : (
              <Switch
                checked={autoSend}
                onCheckedChange={handleToggle}
                aria-label="Ativar envio automático de follow-ups"
              />
            )
          ) : (
            <ShieldCheck className="h-5 w-5 shrink-0 text-muted-foreground" />
          )}
        </div>

        {canManage && orgId && membership?.organization && (
          <ThrottleForm
            key={membership.organization.id}
            org={membership.organization}
            orgId={orgId}
          />
        )}

        {!canManage && (
          <p className="text-xs text-muted-foreground">
            Apenas o dono ou um administrador pode alterar esta configuração.
          </p>
        )}
      </CardContent>
    </Card>
  );
}