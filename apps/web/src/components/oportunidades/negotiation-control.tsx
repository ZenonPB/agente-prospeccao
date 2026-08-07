"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Handshake } from "lucide-react";
import { toast } from "sonner";
import { usePatchNegotiation } from "@/hooks/use-api";
import type { NegotiationStage, ContractOutcome } from "@/types";

const STAGE_OPTIONS: { value: NegotiationStage; label: string }[] = [
  { value: "RD", label: "RD — Reunião de demonstração" },
  { value: "ORCAMENTO", label: "Orçamento" },
  { value: "RP", label: "RP — Reunião de proposta" },
];

const OUTCOME_OPTIONS: { value: ContractOutcome; label: string }[] = [
  { value: "EM_ANALISE", label: "Em análise" },
  { value: "APROVADO", label: "Aprovado" },
  { value: "REPROVADO", label: "Reprovado" },
];

function labelFor<T extends string>(options: { value: T; label: string }[], value: T | ""): string {
  return options.find((o) => o.value === value)?.label ?? "—";
}

export function NegotiationControl({
  leadId,
  initialStage,
  initialOutcome,
}: {
  leadId: string;
  initialStage?: NegotiationStage | null;
  initialOutcome?: ContractOutcome | null;
}) {
  const patch = usePatchNegotiation();
  const [stage, setStage] = useState<NegotiationStage | "">(initialStage ?? "");
  const [outcome, setOutcome] = useState<ContractOutcome | "">(initialOutcome ?? "");

  const handleSave = async () => {
    try {
      await patch.mutateAsync({
        id: leadId,
        data: {
          negotiation_stage: stage || null,
          contract_outcome: outcome || null,
        },
      });
      toast.success("Negociação atualizada.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao atualizar negociação.");
    }
  };

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center gap-2">
        <Handshake className="h-4 w-4 text-muted-foreground" />
        <p className="text-sm font-medium">Negociação</p>
      </div>
      <p className="text-xs text-muted-foreground">
        Progresso do funil interno de vendas e resultado final do contrato.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="neg-stage">Estágio</Label>
          <Select value={stage} onValueChange={(v) => setStage((v || "") as NegotiationStage | "")}>
            <SelectTrigger id="neg-stage" className="w-full">
              <SelectValue>{labelFor(STAGE_OPTIONS, stage)}</SelectValue>
            </SelectTrigger>
            <SelectContent align="start">
              <SelectItem value="">Sem estágio</SelectItem>
              {STAGE_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="neg-outcome">Contrato</Label>
          <Select value={outcome} onValueChange={(v) => setOutcome((v || "") as ContractOutcome | "")}>
            <SelectTrigger id="neg-outcome" className="w-full">
              <SelectValue>{labelFor(OUTCOME_OPTIONS, outcome)}</SelectValue>
            </SelectTrigger>
            <SelectContent align="start">
              <SelectItem value="">Sem resultado</SelectItem>
              {OUTCOME_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <Button size="sm" onClick={handleSave} disabled={patch.isPending}>
        {patch.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        Salvar negociação
      </Button>
    </div>
  );
}