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
import { ShieldCheck, Loader2, Clock } from "lucide-react";
import { toast } from "sonner";
import { useOrgMembership, usePatchOrgSettings } from "@/hooks/use-api";
import type { OrgMembership } from "@/types";

type OrgInfo = NonNullable<OrgMembership>["organization"];

function SlaForm({
  org,
  orgId,
}: {
  org: OrgInfo;
  orgId: string;
}) {
  const patchSettings = usePatchOrgSettings();
  const [pending, setPending] = useState(false);
  // Inicialização lazy (sem setState em effect) — remonta via key={org.id}.
  const [qualified, setQualified] = useState(() => String(org.sla_qualified_no_contact_days ?? 5));
  const [responded, setResponded] = useState(() => String(org.sla_responded_no_next_action_days ?? 2));
  const [opened, setOpened] = useState(() => String(org.sla_opened_no_response_days ?? 2));

  const validDays = (v: string) => {
    const n = Number(v);
    return Number.isInteger(n) && n >= 1 && n <= 120;
  };

  const handleSave = async () => {
    if (!validDays(qualified) || !validDays(responded) || !validDays(opened)) {
      toast.error("Os prazos devem ser inteiros entre 1 e 120 dias.");
      return;
    }
    setPending(true);
    try {
      await patchSettings.mutateAsync({
        orgId,
        data: {
          sla_qualified_no_contact_days: Number(qualified),
          sla_responded_no_next_action_days: Number(responded),
          sla_opened_no_response_days: Number(opened),
        },
      });
      toast.success("Prazos de atendimento salvos.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao salvar os prazos.");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center gap-2">
        <Clock className="h-4 w-4 text-muted-foreground" />
        <p className="text-sm font-medium">Prazos de atendimento</p>
      </div>
      <p className="text-xs text-muted-foreground">
        Regras que alimentam o painel &quot;Ações de hoje&quot;. Um lead que cruza o
        prazo de uma regra vira alerta para o consultor.
      </p>
      <div className="grid grid-cols-1 gap-3 pt-1 sm:grid-cols-3">
        <div className="space-y-1">
          <Label htmlFor="sla-qualified">Apto sem contato (dias)</Label>
          <Input
            id="sla-qualified"
            type="number"
            min={1}
            max={120}
            value={qualified}
            onChange={(e) => setQualified(e.target.value)}
          />
          <p className="text-[11px] leading-tight text-muted-foreground">
            QUALIFICADO que não recebeu nenhum contato dentro deste prazo.
          </p>
        </div>
        <div className="space-y-1">
          <Label htmlFor="sla-responded">Respondeu sem passo (dias)</Label>
          <Input
            id="sla-responded"
            type="number"
            min={1}
            max={120}
            value={responded}
            onChange={(e) => setResponded(e.target.value)}
          />
          <p className="text-[11px] leading-tight text-muted-foreground">
            RESPONDIDO sem próxima ação agendada (ou vencida) neste prazo.
          </p>
        </div>
        <div className="space-y-1">
          <Label htmlFor="sla-opened">Abriu sem responder (dias)</Label>
          <Input
            id="sla-opened"
            type="number"
            min={1}
            max={120}
            value={opened}
            onChange={(e) => setOpened(e.target.value)}
          />
          <p className="text-[11px] leading-tight text-muted-foreground">
            Abriu a mensagem (tracking) e não respondeu dentro deste prazo.
          </p>
        </div>
      </div>
      <div className="pt-1">
        <Button size="sm" disabled={pending} onClick={handleSave}>
          {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Salvar prazos
        </Button>
      </div>
    </div>
  );
}

export function OrgSlaSettings() {
  const { data: membership } = useOrgMembership();
  const orgId = membership?.organization?.id;
  const myRole = membership?.membership?.role;
  const canManage = myRole === "OWNER" || myRole === "ADMIN";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5 text-muted-foreground" />
          Prazos de atendimento
        </CardTitle>
        <CardDescription>
          Lembretes automáticos para leads que ficam esquecidos
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {canManage && orgId && membership?.organization ? (
          <SlaForm
            key={membership.organization.id}
            org={membership.organization}
            orgId={orgId}
          />
        ) : (
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            Apenas o dono ou um administrador pode alterar esta configuração.
          </p>
        )}
      </CardContent>
    </Card>
  );
}