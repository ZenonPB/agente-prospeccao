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
      toast.error("Use um número inteiro entre 1 e 100.");
      return;
    }
    setPending(true);
    try {
      await patchSettings.mutateAsync({
        orgId,
        data: { qualification_threshold: thresholdNum },
      });
      toast.success("Nota mínima atualizada!");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Não foi possível salvar. Tente de novo.");
    } finally {
      setPending(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-5 w-5 text-muted-foreground" />
          Qualificação das empresas
        </CardTitle>
        <CardDescription>
          O sistema dá uma nota de 0 a 100 para cada empresa encontrada. Escolha a partir de
          qual nota você quer considerá-la uma boa oportunidade para contato.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLowThreshold && (
          <div className="flex gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
            <AlertTriangle className="h-5 w-5 text-destructive shrink-0" />
            <div className="space-y-1 flex-1">
              <p className="font-medium text-destructive">Nota muito baixa — atenção</p>
              <p className="text-sm text-muted-foreground">
                Com uma nota mínima baixa, é mais provável que empresas pouco adequadas ao que
                você vende sejam contatadas. Isso gasta seus e-mails e reduz a qualidade das
                conversas. Recomendamos manter o padrão (60) e só reduzir se você tiver bons
                resultados com empresas de nota mais baixa.
              </p>
            </div>
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="qualification_threshold">
            Nota mínima para entrar como oportunidade
          </Label>
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
              Padrão recomendado: <strong>{DEFAULT_THRESHOLD}</strong>
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {isLowThreshold
              ? "Atenção: valor bem abaixo do recomendado."
              : "Boa escolha — você está dentro do recomendado."}
          </p>
        </div>

        <Button onClick={handleSave} disabled={pending || !isValid}>
          {pending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Salvando...
            </>
          ) : (
            "Salvar nota mínima"
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