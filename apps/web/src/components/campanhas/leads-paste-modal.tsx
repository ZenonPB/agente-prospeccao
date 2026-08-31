"use client";

import { useMemo, useState } from "react";
import { useOrgMembership, useOrgMembers, useCampaigns, useCrmExtract, useCrmBatchImport } from "@/hooks/use-api";
import { crmApi } from "@/lib/api";
import type { CrmItem } from "@/types";
import { Button } from "@/components/ui/button";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  ClipboardPaste, Loader2, Trash2, Download, CheckCircle2, AlertCircle, Sparkles,
} from "lucide-react";

type Step = "input" | "preview" | "done";

interface CrmPasteModalProps {
  onSuccess?: () => void;
}

export function CrmPasteModal({ onSuccess }: CrmPasteModalProps) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("input");
  const [rawText, setRawText] = useState("");
  const [consultantId, setConsultantId] = useState<string>("");
  const [campaignId, setCampaignId] = useState<string>("none");
  const [items, setItems] = useState<CrmItem[]>([]);
  const [result, setResult] = useState<{ inserted: number; duplicates: number; errors: string[] } | null>(null);

  const membership = useOrgMembership();
  const orgId = membership.data?.organization?.id;
  const members = useOrgMembers(orgId);
  const campaigns = useCampaigns();
  const extract = useCrmExtract();
  const importLeads = useCrmBatchImport();

  const consultantName = useMemo(
    () => members.data?.members.find((m) => m.user_id === consultantId)?.name ?? "todos",
    [members.data, consultantId],
  );

  const reset = () => {
    setStep("input");
    setRawText("");
    setItems([]);
    setResult(null);
  };

  const handleProcess = async () => {
    if (rawText.trim().length < 10) {
      toast.error("Cole o texto com os leads antes de analisar");
      return;
    }
    try {
      const res = await extract.mutateAsync(rawText);
      if (!res.items.length) {
        toast.error("Nenhum lead reconhecido no texto. Tente descrever nome + empresa.");
        return;
      }
      setItems(res.items);
      setStep("preview");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao analisar o texto");
    }
  };

  const handleConfirm = async () => {
    try {
      const res = await importLeads.mutateAsync({
        items,
        consultant_user_id: consultantId || undefined,
        campaign_id: campaignId === "none" ? undefined : campaignId,
      });
      setResult(res);
      setStep("done");
      toast.success(`${res.inserted} lead(s) inserido(s) no CRM`);
      onSuccess?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao inserir os leads");
    }
  };

  const handleDownload = async () => {
    try {
      const blob = await crmApi.exportXlsx(consultantId || undefined);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `crm_${consultantName.trim().replace(/\s+/g, "_").toLowerCase()}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Planilha CRM baixada.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao gerar a planilha");
    }
  };

  const updateItem = (idx: number, patch: Partial<CrmItem>) => {
    setItems((prev) => prev.map((item, i) => (i === idx ? { ...item, ...patch } : item)));
  };

  const removeItem = (idx: number) => {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(val) => {
        setOpen(val);
        if (!val) reset();
      }}
    >
      <DialogTrigger render={<Button variant="outline" />}>
        <ClipboardPaste className="mr-2 h-4 w-4" aria-hidden="true" />
        Lançar Leads
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <ClipboardPaste className="h-5 w-5 text-primary" aria-hidden="true" />
            Lançamento rápido de leads
          </DialogTitle>
          <DialogDescription>
            Cole suas anotações (LinkedIn, WhatsApp, reuniões) e a IA extrai os dados do CRM.
            Você confere e corrige tudo antes de inserir.
          </DialogDescription>
        </DialogHeader>

        {step === "input" && (
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="crm-consultant">Consultor</Label>
              <Select value={consultantId} onValueChange={(v) => setConsultantId(v || "")}>
                <SelectTrigger id="crm-consultant" className="w-full">
                  <SelectValue placeholder="Selecione o consultor" />
                </SelectTrigger>
                <SelectContent>
                  {(members.data?.members ?? []).map((m) => (
                    <SelectItem key={m.user_id} value={m.user_id}>
                      {m.name ?? m.email ?? m.user_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="crm-campaign">Vincular à campanha (opcional)</Label>
              <Select value={campaignId} onValueChange={(v) => setCampaignId(v || "none")}>
                <SelectTrigger id="crm-campaign" className="w-full">
                  <SelectValue placeholder="Sem campanha" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Sem campanha</SelectItem>
                  {(campaigns.data?.campaigns ?? []).map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="crm-raw-text">Texto com os leads</Label>
              <Textarea
                id="crm-raw-text"
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                rows={8}
                placeholder={`Ex.:\nFabio Prada Perez - Clinica de Psicologia Maua, prospectei 29/07, enviei pitch 03/08, é CEO, respondeu e recusou.\nJosi Andrade, Clínica Josi Andrade (só anotei)`}
              />
              <p className="text-xs text-muted-foreground">
                Pode colar vários leads de uma vez, em qualquer formato. As datas e os
                acompanhamentos são preenchidos automaticamente quando você não os informa.
              </p>
            </div>
          </div>
        )}

        {step === "preview" && (
          <div className="space-y-3 py-2">
            <p className="text-sm text-muted-foreground">
              <Sparkles className="mr-1 inline h-4 w-4 text-primary" aria-hidden="true" />
              Revise, edite o que quiser e remova linhas que não são leads antes de confirmar.
            </p>
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-2 py-2">Lead</th>
                    <th className="px-2 py-2">Empresa</th>
                    <th className="px-2 py-2">Cargo</th>
                    <th className="px-2 py-2">Respondeu?</th>
                    <th className="px-2 py-2">Observações</th>
                    <th className="px-2 py-2" aria-label="Ações" />
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, idx) => (
                    <tr key={idx} className="border-t">
                      <td className="px-2 py-1.5 min-w-40">
                        <Input aria-label="Nome do lead" value={item.lead} onChange={(e) => updateItem(idx, { lead: e.target.value })} className="h-8" />
                      </td>
                      <td className="px-2 py-1.5 min-w-40">
                        <Input aria-label="Empresa" value={item.empresa} onChange={(e) => updateItem(idx, { empresa: e.target.value })} className="h-8" />
                      </td>
                      <td className="px-2 py-1.5 min-w-24">
                        <Input aria-label="Cargo" value={item.cargo ?? ""} onChange={(e) => updateItem(idx, { cargo: e.target.value || null })} className="h-8" />
                      </td>
                      <td className="px-2 py-1.5 min-w-24">
                        <Input aria-label="Respondeu" value={item.respondeu ?? ""} onChange={(e) => updateItem(idx, { respondeu: (e.target.value || null) as CrmItem["respondeu"] })} className="h-8" />
                      </td>
                      <td className="px-2 py-1.5 min-w-48">
                        <Input aria-label="Observações" value={item.observacoes ?? ""} onChange={(e) => updateItem(idx, { observacoes: e.target.value || null })} className="h-8" />
                      </td>
                      <td className="px-2 py-1.5">
                        <Button variant="ghost" size="icon" onClick={() => removeItem(idx)} aria-label={`Remover lead ${item.lead}`}>
                          <Trash2 className="h-4 w-4 text-destructive" aria-hidden="true" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {step === "done" && result && (
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-3 text-center">
              <div className="rounded-lg border bg-card p-3">
                <p className="text-xs text-muted-foreground">Cadastrados</p>
                <p className="text-xl font-bold text-emerald-600">{result.inserted}</p>
              </div>
              <div className="rounded-lg border bg-card p-3">
                <p className="text-xs text-muted-foreground">Já cadastrados (ignorados)</p>
                <p className="text-xl font-bold text-amber-600">{result.duplicates}</p>
              </div>
            </div>
            {result.inserted > 0 && (
              <div className="flex items-center gap-2 rounded-md bg-emerald-50 dark:bg-emerald-950/30 p-3 text-sm text-emerald-800 dark:text-emerald-300">
                <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" aria-hidden="true" />
                <span>{result.inserted} lead(s) cadastrado(s) para {consultantName}. Os acompanhamentos já ficaram agendados.</span>
              </div>
            )}
            {result.errors.length > 0 && (
              <div className="space-y-1 rounded-md border bg-muted/30 p-2 text-xs">
                <p className="font-semibold text-destructive flex items-center gap-1">
                  <AlertCircle className="h-4 w-4" aria-hidden="true" />
                  Erros ({result.errors.length})
                </p>
                {result.errors.map((err, idx) => (
                  <p key={idx} className="text-muted-foreground">{err}</p>
                ))}
              </div>
            )}
          </div>
        )}

        <DialogFooter className="flex flex-wrap justify-between gap-2 sm:justify-between">
          <div>
            {step === "done" && (
              <Button variant="outline" onClick={handleDownload}>
                <Download className="mr-2 h-4 w-4" aria-hidden="true" />
                Baixar Excel
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            {step === "input" && (
              <Button variant="outline" onClick={() => setOpen(false)}>
                Cancelar
              </Button>
            )}
            {step === "preview" && (
              <Button variant="outline" onClick={() => setStep("input")}>
                Voltar
              </Button>
            )}
            {step === "input" && (
              <Button onClick={handleProcess} disabled={extract.isPending}>
                {extract.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                    Processando...
                  </>
                ) : (
                  "Analisar texto"
                )}
              </Button>
            )}
            {step === "preview" && (
              <Button onClick={handleConfirm} disabled={!items.length || importLeads.isPending}>
                {importLeads.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                    Inserindo...
                  </>
                ) : (
                  `Confirmar ${items.length} lead(s)`
                )}
              </Button>
            )}
            {step === "done" && (
              <Button onClick={reset}>Lançar mais leads</Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

