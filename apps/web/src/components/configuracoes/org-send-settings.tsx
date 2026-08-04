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
import { Send, Loader2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { useOrgMembership, usePatchOrgSettings } from "@/hooks/use-api";

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
      <CardContent className="space-y-4">
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
        {!canManage && (
          <p className="text-xs text-muted-foreground">
            Apenas o dono ou um administrador pode alterar esta configuração.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
