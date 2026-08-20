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
import { Loader2, Gauge, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { useMyOrganization, usePatchOrgSettings } from "@/hooks/use-api";
import type { OrgMembership } from "@/types";

const DEFAULT_THRESHOLD = 60;

type OrgInfo = NonNullable<OrgMembership>["organization"];

function ThresholdForm({
  org,
  orgId,
}: {
  org: OrgInfo;
  orgId: string;
}) {
  const patchSettings = usePatchOrgSettings();
  const [pending, setPending] = useState(false);
  const [threshold, setThreshold] = useState(() =>
    String(org.qualification_threshold ?? DEFAULT_THRESHOLD)
  );

  const thresholdNum = Number(threshold);
  const isLowThreshold = thresholdNum < 50;
  const isValid = Number.isInteger(thresholdNum) && thresholdNum >= 1 && thresholdNum <= 100;

  const handleSave = async () => {
    if (!isValid) {
      toast.error("O threshold deve ser um inteiro entre 1 e 100.");
      return;
    }
    setPending(true);
    try {
      await patchSettings.mutateAsync({
        orgId,
        data: { qualification_threshold: thresholdNum },
      });
      toast.success("Threshold de qualificação atualizado.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao salvar.");
    } finally {
      setPending(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-5 w-5 text-muted-foreground" />
          Threshold de Qualificação
        </CardTitle>
        <CardDescription>
          Limiar de score (0–100) para um lead ser classificado como QUALIFICADO e entrar
          na fila de outreach automático da organização.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLowThreshold && (
          <div className="flex gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
            <AlertTriangle className="h-5 w-5 text-destructive shrink-0" />
            <div className="space-y-1 flex-1">
              <p className="font-medium text-destructive">Threshold muito baixo</p>
              <p className="text-sm text-muted-foreground">
                Valores abaixo de 50 fazem leads com pouca aderência entrarem na cadência
                automática. Isso aumenta o risco de contatar empresas sem fit real,
                desperdiçar créditos de e-mail e prejudicar a reputação do domínio.
                Considere manter o padrão (60) ou ajustar apenas com base nos dados de
                conversão da sua campanha.
              </p>
            </div>
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="qualification_threshold">Score mínimo para QUALIFICADO</Label>
          <div className="flex items-center gap-3">
            <Input
              id="qualification_threshold"
              type="number"
              min="1"
              max="100"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              className="w-24"
              disabled={pending}
            />
            <span className="text-sm text-muted-foreground">
              Padrão: <strong>{DEFAULT_THRESHOLD}</strong>
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {isLowThreshold
              ? "⚠ Valor abaixo do recomendado — use com cautela."
              : "Valor dentro da faixa recomendada (50–80)."}
          </p>
        </div>

        <Button onClick={handleSave} disabled={pending || !isValid}>
          {pending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Salvando...
            </>
          ) : (
            "Salvar threshold"
          )}
        </Button>
      </CardContent>
    </Card>
  );
}

export function OrgThresholdSettings() {
  const orgQ = useMyOrganization();

  if (orgQ.isLoading) {
    return (
      <Card>
        <CardHeader>
          <div className="h-5 w-48 animate-pulse bg-muted" />
          <div className="h-4 w-64 animate-pulse bg-muted" />
        </CardHeader>
        <CardContent className="h-24 animate-pulse bg-muted" />
      </Card>
    );
  }

  if (orgQ.isError || !orgQ.data) {
    return null;
  }

  const isOwnerOrAdmin =
    orgQ.data.membership.role === "OWNER" ||
    orgQ.data.membership.role === "ADMIN";

  if (!isOwnerOrAdmin) {
    return null;
  }

  return (
    <ThresholdForm
      org={orgQ.data.organization}
      orgId={orgQ.data.organization.id}
      key={orgQ.data.organization.id}
    />
  );
}