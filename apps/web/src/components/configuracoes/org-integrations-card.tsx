"use client";

import { useState } from "react";
import { Plug, Calendar, Send, Loader2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useOrgMembership, usePatchOrgSettings } from "@/hooks/use-api";
import { toast } from "sonner";

export function OrgIntegrationsCard() {
  const { data: membership } = useOrgMembership();
  const orgId = membership?.organization?.id;
  const myRole = membership?.membership?.role;
  const canManage = myRole === "OWNER" || myRole === "ADMIN";

  const patch = usePatchOrgSettings();
  const initialUrl = membership?.organization?.webhook_url ?? "";
  const initialScheduling = membership?.organization?.scheduling_url ?? "";
  const [webhookUrl, setWebhookUrl] = useState(initialUrl);
  const [webhookSecret, setWebhookSecret] = useState("");
  const [schedulingUrl, setSchedulingUrl] = useState(initialScheduling);

  const save = async () => {
    if (!orgId) return;
    try {
      await patch.mutateAsync({
        orgId,
        data: {
          webhook_url: webhookUrl.trim() || null,
          webhook_secret: webhookSecret.trim() || undefined,
          scheduling_url: schedulingUrl.trim() || null,
        },
      });
      toast.success("Integrações atualizadas.");
      setWebhookSecret("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao salvar.");
    }
  };

  if (!canManage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plug className="h-5 w-5 text-muted-foreground" />
            Integrações
          </CardTitle>
          <CardDescription>
            Webhook de saída e link de agendamento. Apenas owner/admin configura.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Fale com um administrador para configurar as integrações da sua organização.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Plug className="h-5 w-5 text-muted-foreground" />
          Integrações
        </CardTitle>
        <CardDescription>
          Webhook genérico de saída (eventos de lead) e link de agendamento injetado no outreach.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-sm font-medium flex items-center gap-2">
                <Send className="h-4 w-4 text-muted-foreground" />
                Webhook de saída
              </Label>
              <p className="mt-0.5 text-xs text-muted-foreground">
                POST JSON em <code>webhook_url</code> quando há lead criado, status alterado ou conversão.
                Cabeçalho <code>X-Webhook-Secret</code> + <code>X-Webhook-Event</code>.
              </p>
            </div>
            {membership?.organization?.webhook_configured ? (
              <Badge variant="secondary">Ativo</Badge>
            ) : (
              <Badge variant="outline">Desativado</Badge>
            )}
          </div>
          <Input
            placeholder="https://exemplo.com/webhook/prospeccao"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
          />
          <Input
            type="password"
            placeholder="Segredo compartilhado (opcional, mas recomendado)"
            value={webhookSecret}
            onChange={(e) => setWebhookSecret(e.target.value)}
            autoComplete="off"
          />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-sm font-medium flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                Link de agendamento
              </Label>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Cal.com, Calendly ou similar. Injetado no outreach como CTA preferencial.
              </p>
            </div>
            {membership?.organization?.scheduling_url ? (
              <Badge variant="secondary">Ativo</Badge>
            ) : (
              <Badge variant="outline">Desativado</Badge>
            )}
          </div>
          <Input
            placeholder="https://cal.com/equipe/reuniao-prospeccao"
            value={schedulingUrl}
            onChange={(e) => setSchedulingUrl(e.target.value)}
          />
        </div>

        <div className="flex justify-end">
          <Button onClick={save} disabled={patch.isPending}>
            {patch.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Salvar integrações
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
