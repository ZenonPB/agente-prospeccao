"use client";

import { useState, useCallback } from "react";
import { useImportCsv } from "@/hooks/use-api";
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
import { FileSpreadsheet, Upload, CheckCircle2, AlertCircle, Loader2, Info } from "lucide-react";
import { toast } from "sonner";
import type { CsvImportResult } from "@/types";

interface CsvImportModalProps {
  campaignId: string;
  campaignName: string;
  onSuccess?: () => void;
}

export function CsvImportModal({ campaignId, campaignName, onSuccess }: CsvImportModalProps) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<CsvImportResult | null>(null);
  const importCsv = useImportCsv();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      if (!selected.name.endsWith(".csv")) {
        toast.error("Selecione um arquivo .csv válido");
        return;
      }
      setFile(selected);
      setResult(null);
    }
  };

  const handleUpload = useCallback(async () => {
    if (!file) {
      toast.error("Selecione um arquivo para importar");
      return;
    }

    try {
      const res = await importCsv.mutateAsync({ campaignId, file });
      setResult(res);
      toast.success(`${res.imported_count} leads importados com sucesso!`);
      if (onSuccess) onSuccess();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao importar arquivo CSV");
    }
  }, [file, campaignId, importCsv, onSuccess]);

  const handleReset = () => {
    setFile(null);
    setResult(null);
  };

  return (
    <Dialog open={open} onOpenChange={(val) => { setOpen(val); if (!val) handleReset(); }}>
      <DialogTrigger render={<Button variant="outline" />}>
        <FileSpreadsheet className="mr-2 h-4 w-4" aria-hidden="true" />
        Importar CSV
      </DialogTrigger>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <FileSpreadsheet className="h-5 w-5 text-primary" aria-hidden="true" />
            Importar Leads por CSV
          </DialogTitle>
          <DialogDescription>
            Adicione sua própria lista de empresas para a campanha <strong>{campaignName}</strong>.
          </DialogDescription>
        </DialogHeader>

        {!result ? (
          <div className="space-y-4 py-3">
            <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-3 text-xs text-blue-900 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-200">
              <p className="flex items-center gap-1.5 font-medium mb-1">
                <Info className="h-4 w-4 text-blue-600 dark:text-blue-400" aria-hidden="true" />
                Formato esperado do CSV:
              </p>
              <p className="text-muted-foreground">
                Colunas aceitas (vírgula ou ponto-e-vírgula): <strong>Nome/Empresa</strong> (obrigatório), <strong>Site/Website</strong>, <strong>Telefone</strong>, <strong>Cidade</strong>, <strong>Estado/UF</strong>, <strong>CNPJ</strong>, <strong>Endereço</strong>.
              </p>
            </div>

            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 p-6 text-center hover:bg-muted/50 transition-colors">
              <Upload className="mb-2 h-8 w-8 text-muted-foreground" aria-hidden="true" />
              <label htmlFor="csv-file-input" className="cursor-pointer">
                <span className="text-sm font-medium text-primary hover:underline">
                  Clique para selecionar o arquivo
                </span>
                <input
                  id="csv-file-input"
                  type="file"
                  accept=".csv"
                  className="sr-only"
                  onChange={handleFileChange}
                />
              </label>
              <p className="mt-1 text-xs text-muted-foreground">
                {file ? file.name : "Formatos aceitos: .csv (UTF-8 ou Latin-1)"}
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4 py-3">
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-lg border bg-card p-3">
                <p className="text-xs text-muted-foreground">Importados</p>
                <p className="text-xl font-bold text-emerald-600">{result.imported_count}</p>
              </div>
              <div className="rounded-lg border bg-card p-3">
                <p className="text-xs text-muted-foreground">Duplicados</p>
                <p className="text-xl font-bold text-amber-600">{result.duplicate_count}</p>
              </div>
              <div className="rounded-lg border bg-card p-3">
                <p className="text-xs text-muted-foreground">Erros</p>
                <p className="text-xl font-bold text-destructive">{result.error_count}</p>
              </div>
            </div>

            {result.imported_count > 0 && (
              <div className="flex items-center gap-2 rounded-md bg-emerald-50 dark:bg-emerald-950/30 p-3 text-sm text-emerald-800 dark:text-emerald-300">
                <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" aria-hidden="true" />
                <span>
                  {result.imported_count} novo(s) lead(s) adicionado(s) à campanha. Você pode iniciar a qualificação/reanálise no painel da campanha.
                </span>
              </div>
            )}

            {result.errors.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-destructive flex items-center gap-1">
                  <AlertCircle className="h-4 w-4" aria-hidden="true" />
                  Detalhes dos erros ({result.errors.length}):
                </p>
                <div className="max-h-36 overflow-y-auto rounded-md border bg-muted/30 p-2 text-xs space-y-1">
                  {result.errors.map((err, idx) => (
                    <p key={idx} className="text-muted-foreground">
                      Linha {err.line}: <span className="text-foreground">{err.reason}</span>
                    </p>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="flex justify-between sm:justify-between">
          {result ? (
            <Button variant="outline" onClick={handleReset}>
              Importar outro arquivo
            </Button>
          ) : (
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
          )}

          {!result && (
            <Button onClick={handleUpload} disabled={!file || importCsv.isPending}>
              {importCsv.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  Processando...
                </>
              ) : (
                "Importar"
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}