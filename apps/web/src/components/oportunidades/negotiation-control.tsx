"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Handshake, Banknote } from "lucide-react";
import { toast } from "sonner";
import { usePatchNegotiation, useRegisterConversion } from "@/hooks/use-api";
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
  const register = useRegisterConversion();
  const [stage, setStage] = useState<NegotiationStage | "">(initialStage ?? "");
  const [outcome, setOutcome] = useState<ContractOutcome | "">(initialOutcome ?? "");
  const [value, setValue] = useState("");

  const handleSave = async () => {
    try {
      const isApproved = outcome === "APROVADO";
      const normalizedValue = value.trim() ? Number(value.replace(",", ".")) : null;
      const hasValue = normalizedValue !== null && !Number.isNaN(normalizedValue) && normalizedValue > 0;

      if (isApproved && hasValue) {
        await register.mutateAsync({
          id: leadId,
          data: { contract_value: normalizedValue },
        });
      }

      await patch.mutateAsync({
        id: leadId,
        data: {
          negotiation_stage: stage || null,
          contract_outcome: outcome || null,
        },
      });

      toast.success(
        isApproved && hasValue
          ? "Negociação atualizada e receita registrada."
          : isApproved
            ? "Negociação aprovada. Registre o valor do contrato para alimentar a Receita Realizada."
            : "Negociação atualizada.",
      );
      setValue("");
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
      {outcome === "APROVADO" && (
        <div className="space-y-1.5">
          <Label htmlFor="neg-value">Valor do contrato (R$)</Label>
          <div className="relative">
            <Banknote className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="neg-value"
              type="number"
              min="0"
              step="0.01"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Ex.: 3.500,00"
              className="pl-9"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Registra a conversão e alimenta a Receita Realizada dos relatórios.
          </p>
        </div>
      )}
      <Button size="sm" onClick={handleSave} disabled={patch.isPending || register.isPending}>
        {patch.isPending || register.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : null}
        Salvar negociação
      </Button>
    </div>
  );
}