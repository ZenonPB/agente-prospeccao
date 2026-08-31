"use client";

import { useState, useCallback } from "react";
import * as XLSX from "xlsx";
import { useAtualizarPlanilha } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { toast } from "sonner";
import { FileSpreadsheet, Upload, Loader2, Download, CheckCircle2, AlertTriangle, Plus } from "lucide-react";

type Mode = "select" | "create";

export function CrmPlanilhaModal() {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [sheetNames, setSheetNames] = useState<string[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<string>("");
  const [mode, setMode] = useState<Mode>("select");
  const [newSheetName, setNewSheetName] = useState("");
  const [done, setDone] = useState(false);
  const atualizar = useAtualizarPlanilha();

  const readSheetNames = useCallback(async (f: File) => {
    try {
      const buffer = await f.arrayBuffer();
      const wb = XLSX.read(buffer, { type: "array", sheetRows: 0 });
      const names = wb.SheetNames.filter((n) => n.trim().length > 0);
      setSheetNames(names);
      if (names.length > 0) {
        setSelectedSheet(names[0]);
        setMode("select");
      } else {
        setMode("create");
      }
    } catch {
      toast.error("Não foi possível ler as abas da planilha. Verifique o arquivo.");
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".xlsx")) {
      toast.error("Selecione o arquivo .xlsx da planilha");
      return;
    }
    setFile(selected);
    setDone(false);
    setSelectedSheet("");
    setNewSheetName("");
    readSheetNames(selected);
  };

  const effectiveSheetName = mode === "create" ? newSheetName.trim() : selectedSheet;
  const isCreating = mode === "create" && effectiveSheetName.length > 0;
  const sheetExists = sheetNames.includes(effectiveSheetName);
  const canSubmit = file && effectiveSheetName.length > 0 && (mode === "select" || (mode === "create" && newSheetName.trim().length > 0));

  const handleEnviar = async () => {
    if (!file || !canSubmit) {
      toast.error("Selecione a planilha e a aba antes de enviar");
      return;
    }
    try {
      const blob = await atualizar.mutateAsync({
        file,
        abaName: effectiveSheetName,
        criarAba: isCreating,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Planilha_aprimorada_${effectiveSheetName}.xlsx`;
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

  const resetState = () => {
    setFile(null);
    setSheetNames([]);
    setSelectedSheet("");
    setMode("select");
    setNewSheetName("");
    setDone(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(val) => {
        setOpen(val);
        if (!val) resetState();
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
            Envie a sua planilha (.xlsx). Os leads atribuídos a você entram na aba selecionada,
            com as datas de prospecção, contato e acompanhamentos já preenchidas.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {!done ? (
            <>
              {/* File picker */}
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

              {/* Sheet selection — only after file is loaded */}
              {file && sheetNames.length > 0 && (
                <div className="space-y-3 rounded-md border p-3">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <FileSpreadsheet className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                    Selecione a aba
                  </div>

                  <div className="flex gap-2">
                    <Button
                      variant={mode === "select" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setMode("select")}
                    >
                      Aba existente
                    </Button>
                    <Button
                      variant={mode === "create" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setMode("create")}
                    >
                      <Plus className="mr-1 h-3 w-3" aria-hidden="true" />
                      Nova aba
                    </Button>
                  </div>

                  {mode === "select" ? (
                    <Select value={selectedSheet} onValueChange={(v) => setSelectedSheet(v ?? "")}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Selecione uma aba..." />
                      </SelectTrigger>
                      <SelectContent>
                        {sheetNames.map((name) => (
                          <SelectItem key={name} value={name}>
                            {name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <div className="space-y-2">
                      <Input
                        placeholder="Nome da nova aba"
                        value={newSheetName}
                        onChange={(e) => setNewSheetName(e.target.value)}
                      />
                      {newSheetName.trim().length > 0 && sheetExists && (
                        <div className="flex items-center gap-2 rounded-md bg-amber-50 dark:bg-amber-950/30 p-2 text-xs text-amber-800 dark:text-amber-300">
                          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                          Já existe uma aba com esse nome. Os dados serão adicionados a ela.
                        </div>
                      )}
                      {newSheetName.trim().length > 0 && !sheetExists && (
                        <div className="flex items-center gap-2 rounded-md bg-blue-50 dark:bg-blue-950/30 p-2 text-xs text-blue-800 dark:text-blue-300">
                          <Plus className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                          Uma nova aba será criada com o header padrão.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
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
            <Button onClick={handleEnviar} disabled={!file || !canSubmit || atualizar.isPending}>
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
