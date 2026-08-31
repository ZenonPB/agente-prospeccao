"use client";

import { useState } from "react";
import { useAtualizarPlanilha } from "@/hooks/use-api";
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
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { FileSpreadsheet, Upload, Loader2, Download, CheckCircle2 } from "lucide-react";

export function CrmPlanilhaModal() {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [done, setDone] = useState(false);
  const atualizar = useAtualizarPlanilha();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".xlsx")) {
      toast.error("Selecione o arquivo .xlsx da planilha");
      return;
    }
    setFile(selected);
    setDone(false);
  };

  const handleEnviar = async () => {
    if (!file) {
      toast.error("Selecione a planilha antes de enviar");
      return;
    }
    try {
      const blob = await atualizar.mutateAsync(file);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Planilha_aprimorada_atualizada.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setDone(true);
      toast.success("Planilha atualizada com os seus leads. Verifique o download.");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Erro ao atualizar a planilha",
      );
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(val) => {
        setOpen(val);
        if (!val) {
          setFile(null);
          setDone(false);
        }
      }}
    >
      <DialogTrigger render={<Button variant="outline" />}>
        <FileSpreadsheet className="mr-2 h-4 w-4" aria-hidden="true" />
        Atualizar Planilha
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <FileSpreadsheet className="h-5 w-5 text-primary" aria-hidden="true" />
            Preencher minha planilha de CRM
          </DialogTitle>
          <DialogDescription>
            Envie a sua planilha (.xlsx). Os leads atribuídos a você entram na sua aba,
            com as datas de prospecção, contato e acompanhamentos já preenchidas.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {!done ? (
            <div className="space-y-2">
              <Label htmlFor="crm-planilha-file" className="cursor-pointer">
                <div className="flex flex-col items-center gap-2 rounded-lg border-2 border-dashed p-6 text-sm text-muted-foreground hover:bg-muted/40">
                  <Upload className="h-6 w-6 text-primary" aria-hidden="true" />
                  {file ? file.name : "Clique para escolher a planilha (.xlsx)"}
                </div>
              </Label>
              <input
                id="crm-planilha-file"
                type="file"
                accept=".xlsx"
                className="sr-only"
                onChange={handleFileChange}
              />
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-md bg-emerald-50 dark:bg-emerald-950/30 p-3 text-sm text-emerald-800 dark:text-emerald-300">
              <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" aria-hidden="true" />
              Planilha gerada. Baixe o arquivo atualizado nos seus downloads.
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Fechar
          </Button>
          {!done && (
            <Button onClick={handleEnviar} disabled={!file || atualizar.isPending}>
              {atualizar.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  Atualizando...
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" aria-hidden="true" />
                  Gerar e baixar
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}