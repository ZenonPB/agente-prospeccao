"use client";

import { useMemo, useRef, useState } from "react";
import { AlertCircle, CheckCircle2, ChevronLeft, ChevronRight, FileSpreadsheet, Info, Loader2, RotateCcw, Upload, XCircle } from "lucide-react";
import { toast } from "sonner";
import {
  useCancelImport,
  useConfirmImport,
  useImportDryRun,
  useImportJob,
  useImportRows,
  useRecoverImport,
  useUploadImport,
} from "@/hooks/use-api";
import type {
  ImportDryRunReport,
  ImportJob,
  ImportJobStatus,
  ImportMapping,
  ImportMappingField,
  ImportRowStatus,
} from "@/types";
import { importJobStatusLabel, isImportJobTerminal } from "@/types";
import { Badge } from "@/components/ui/badge";
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
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface CsvImportModalProps {
  campaignId: string;
  campaignName: string;
  onSuccess?: () => void;
}

type ImportStep = "upload" | "mapping" | "report";

const MAX_FILE_BYTES = 25 * 1024 * 1024;
const IGNORE_VALUE = "__ignore__";

const FIELD_LABELS: Record<ImportMappingField, string> = {
  name: "Nome da empresa",
  website: "Site",
  phone: "Telefone",
  whatsapp: "WhatsApp",
  email: "E-mail",
  city: "Cidade",
  state: "Estado/UF",
  address: "Endereço",
  cnpj: "CNPJ",
  category: "Categoria",
  contact_name: "Nome do contato",
  linkedin: "LinkedIn",
  instagram: "Instagram",
};

const FIELD_OPTIONS = Object.entries(FIELD_LABELS) as [ImportMappingField, string][];
const ROW_STATUS_LABELS: Record<ImportRowStatus, string> = {
  ACCEPTED: "Aceita",
  DUPLICATE: "Duplicada",
  REJECTED: "Rejeitada",
  FAILED: "Falhou",
};

function makeIdempotencyKey(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}:${crypto.randomUUID()}`;
  }
  return `${prefix}:${Date.now()}:${Math.random().toString(36).slice(2)}`;
}

function normalizeSuggestedMapping(headers: string[], suggested?: ImportMapping): ImportMapping {
  const used = new Set<ImportMappingField>();
  return headers.reduce<ImportMapping>((result, header) => {
    const candidate = suggested?.[header] ?? null;
    if (candidate && !used.has(candidate)) {
      result[header] = candidate;
      used.add(candidate);
    } else {
      result[header] = null;
    }
    return result;
  }, {});
}

function mappingError(headers: string[], mapping: ImportMapping): string | null {
  if (headers.some((header) => !(header in mapping))) {
    return "Escolha um destino ou Ignorar para todas as colunas.";
  }
  const selected = headers.map((header) => mapping[header]).filter((value): value is ImportMappingField => Boolean(value));
  const duplicate = selected.find((field, index) => selected.indexOf(field) !== index);
  if (duplicate) {
    return `O campo “${FIELD_LABELS[duplicate]}” foi escolhido mais de uma vez.`;
  }
  if (!selected.includes("name")) {
    return "A coluna Nome da empresa é obrigatória para continuar.";
  }
  return null;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function statusClass(status: ImportJobStatus): string {
  if (status === "SUCCEEDED") return "bg-emerald-100 text-emerald-800";
  if (status === "PARTIAL") return "bg-amber-100 text-amber-800";
  if (status === "FAILED") return "bg-red-100 text-red-800";
  if (status === "CANCELLED") return "bg-slate-100 text-slate-700";
  if (status === "RUNNING" || status === "QUEUED" || status === "CANCEL_REQUESTED") return "bg-blue-100 text-blue-800";
  return "bg-muted text-muted-foreground";
}

function reportFromJob(job: ImportJob, localReport: ImportDryRunReport | null): ImportDryRunReport | null {
  if (job.dry_run_report) return job.dry_run_report;
  if (localReport) return localReport;
  if (job.status === "PREVIEWED") return null;
  return {
    accepted: job.accepted_rows,
    duplicate: job.duplicate_rows,
    rejected: job.rejected_rows,
    failed: job.failed_rows,
    total_rows: job.total_rows,
    errors: [],
  };
}

export function CsvImportModal({ campaignId, campaignName, onSuccess }: CsvImportModalProps) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<ImportStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [importId, setImportId] = useState<string | undefined>();
  const [jobSnapshot, setJobSnapshot] = useState<ImportJob | null>(null);
  const [mapping, setMapping] = useState<ImportMapping>({});
  const [dryRunReport, setDryRunReport] = useState<ImportDryRunReport | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [rowStatus, setRowStatus] = useState<ImportRowStatus | undefined>();
  const [rowsOffset, setRowsOffset] = useState(0);
  const uploadKeyRef = useRef<string>(makeIdempotencyKey("historical-import-upload"));
  const confirmKeyRef = useRef<string>(makeIdempotencyKey("historical-import-confirm"));

  const jobQuery = useImportJob(importId, open);
  const currentJob = jobQuery.data && (!jobSnapshot || jobQuery.data.expected_version >= jobSnapshot.expected_version)
    ? jobQuery.data
    : jobSnapshot;
  const headers = currentJob?.headers ?? [];
  const previewRows = currentJob?.preview_rows ?? [];
  const mappingProblem = mappingError(headers, mapping);
  const report = currentJob ? reportFromJob(currentJob, dryRunReport) : null;
  const showRows = Boolean(currentJob && ["SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"].includes(currentJob.status));
  const rowsQuery = useImportRows(importId, rowStatus, rowsOffset, showRows && open);
  const uploadMutation = useUploadImport();
  const dryRunMutation = useImportDryRun();
  const confirmMutation = useConfirmImport();
  const cancelMutation = useCancelImport();
  const recoverMutation = useRecoverImport();

  const progress = useMemo(() => {
    if (!currentJob || currentJob.total_rows === 0) return 0;
    const processed = currentJob.total_rows - currentJob.unprocessed_rows;
    return Math.max(0, Math.min(100, Math.round((processed / currentJob.total_rows) * 100)));
  }, [currentJob]);

  const resetFlow = () => {
    setStep("upload");
    setFile(null);
    setFileError(null);
    setImportId(undefined);
    setJobSnapshot(null);
    setMapping({});
    setDryRunReport(null);
    setActionError(null);
    setRowStatus(undefined);
    setRowsOffset(0);
    uploadKeyRef.current = makeIdempotencyKey("historical-import-upload");
    confirmKeyRef.current = makeIdempotencyKey("historical-import-confirm");
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    if (!selected) return;
    const extension = selected.name.toLowerCase().split(".").pop();
    if (extension !== "csv" && extension !== "xlsx") {
      setFile(null);
      setFileError("Selecione um arquivo .csv ou .xlsx.");
      return;
    }
    if (selected.size > MAX_FILE_BYTES) {
      setFile(null);
      setFileError("O arquivo excede o limite de 25 MiB.");
      return;
    }
    setFile(selected);
    setFileError(null);
    setActionError(null);
  };

  const handleUpload = async () => {
    if (!file) {
      setFileError("Selecione um arquivo .csv ou .xlsx para continuar.");
      return;
    }
    setActionError(null);
    try {
      const uploaded = await uploadMutation.mutateAsync({ campaignId, file, idempotencyKey: uploadKeyRef.current });
      setImportId(uploaded.id);
      setJobSnapshot(uploaded);
      setMapping(normalizeSuggestedMapping(uploaded.headers ?? [], uploaded.suggested_mapping));
      setStep("mapping");
    } catch (error) {
      setActionError(errorMessage(error, "Não foi possível preparar a prévia."));
    }
  };

  const handleDryRun = async () => {
    if (!currentJob || mappingProblem) return;
    setActionError(null);
    try {
      const result = await dryRunMutation.mutateAsync({
        importId: currentJob.id,
        mapping,
        expectedVersion: currentJob.expected_version,
      });
      setJobSnapshot(result.job);
      setDryRunReport(result.report);
      setStep("report");
      setRowsOffset(0);
    } catch (error) {
      setActionError(errorMessage(error, "Não foi possível simular a importação."));
    }
  };

  const handleConfirm = async () => {
    if (!currentJob || !dryRunReport || mappingProblem) return;
    setActionError(null);
    try {
      const confirmed = await confirmMutation.mutateAsync({
        importId: currentJob.id,
        campaignId: currentJob.campaign_id ?? campaignId,
        mapping,
        mappingVersion: currentJob.mapping_version,
        expectedVersion: currentJob.expected_version,
        idempotencyKey: confirmKeyRef.current,
      });
      setJobSnapshot(confirmed);
      setStep("report");
      toast.success("Importação confirmada e enviada para processamento.");
      onSuccess?.();
    } catch (error) {
      setActionError(errorMessage(error, "Não foi possível confirmar a importação."));
    }
  };

  const handleCancel = async () => {
    if (!currentJob) return;
    setActionError(null);
    try {
      const cancelled = await cancelMutation.mutateAsync({
        importId: currentJob.id,
        campaignId: currentJob.campaign_id ?? campaignId,
        expectedVersion: currentJob.expected_version,
      });
      setJobSnapshot(cancelled);
      setStep("report");
    } catch (error) {
      setActionError(errorMessage(error, "Não foi possível cancelar a importação."));
    }
  };

  const handleRecover = async () => {
    if (!currentJob) return;
    setActionError(null);
    try {
      const recovered = await recoverMutation.mutateAsync({
        importId: currentJob.id,
        campaignId: currentJob.campaign_id ?? campaignId,
        expectedVersion: currentJob.expected_version,
      });
      setJobSnapshot(recovered);
      setRowsOffset(0);
    } catch (error) {
      setActionError(errorMessage(error, "Não foi possível retomar a importação."));
    }
  };

  const busy = uploadMutation.isPending || dryRunMutation.isPending || confirmMutation.isPending || cancelMutation.isPending || recoverMutation.isPending;
  const canCancel = currentJob && ["PREVIEWED", "QUEUED", "RUNNING"].includes(currentJob.status);
  const canRecover = currentJob && ["FAILED", "PARTIAL"].includes(currentJob.status) && currentJob.attempts < 3;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" />}>
        <FileSpreadsheet className="mr-2 h-4 w-4" aria-hidden="true" />
        Importar Planilha (CSV/XLSX)
      </DialogTrigger>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <FileSpreadsheet className="h-5 w-5 text-primary" aria-hidden="true" />
            Importação histórica
          </DialogTitle>
          <DialogDescription>
            Envie uma planilha para <strong>{campaignName}</strong>, confira o mapeamento e só confirme depois da simulação.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2 text-xs" aria-label="Etapas da importação">
          {(["upload", "mapping", "report"] as ImportStep[]).map((item, index) => (
            <div key={item} className="flex items-center gap-2">
              <Badge variant={step === item ? "default" : "outline"}>{index + 1}</Badge>
              <span className={step === item ? "font-medium text-foreground" : "text-muted-foreground"}>
                {item === "upload" ? "Arquivo" : item === "mapping" ? "Colunas e prévia" : "Simulação e resultado"}
              </span>
              {index < 2 && <span className="text-muted-foreground">/</span>}
            </div>
          ))}
        </div>

        {actionError && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive" role="alert" aria-live="assertive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{actionError}</span>
          </div>
        )}

        {step === "upload" && (
          <div className="space-y-4 py-2">
            <div className="rounded-lg border border-blue-200 bg-blue-50/60 p-3 text-sm text-blue-950 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-100">
              <p className="flex items-center gap-2 font-medium"><Info className="h-4 w-4" aria-hidden="true" />Antes de começar</p>
              <p className="mt-1 text-xs text-muted-foreground">Aceitamos CSV em UTF-8 (com ou sem BOM) e XLSX. Limite: 25 MiB. O arquivo é apenas lido para gerar uma prévia; nenhuma URL será acessada.</p>
            </div>
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 p-8 text-center">
              <Upload className="mb-3 h-9 w-9 text-muted-foreground" aria-hidden="true" />
              <Label htmlFor="historical-import-file" className="cursor-pointer text-sm font-medium text-primary hover:underline">Escolher arquivo CSV ou XLSX</Label>
              <input id="historical-import-file" type="file" accept=".csv,.xlsx" className="sr-only" onChange={handleFileChange} />
              <p className="mt-2 max-w-md text-xs text-muted-foreground">{file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MiB` : "O limite de tamanho é verificado antes do upload."}</p>
            </div>
            {fileError && <p className="text-sm text-destructive" role="alert">{fileError}</p>}
          </div>
        )}

        {step === "mapping" && currentJob && (
          <div className="grid min-h-0 gap-5 py-2 lg:grid-cols-[1fr_1.15fr]">
            <section className="min-w-0 space-y-3" aria-labelledby="import-preview-title">
              <div>
                <h3 id="import-preview-title" className="font-semibold">Prévia segura</h3>
                <p className="text-xs text-muted-foreground">{currentJob.total_rows.toLocaleString("pt-BR")} linhas · {headers.length} colunas · {currentJob.source_filename}</p>
              </div>
              {previewRows.length === 0 ? (
                <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">Nenhuma linha de prévia disponível.</div>
              ) : (
                <div className="max-h-80 overflow-auto rounded-md border">
                  <Table>
                    <TableCaption>Primeiras linhas do arquivo, sem execução de código ou HTML.</TableCaption>
                    <TableHeader><TableRow>{headers.map((header) => <TableHead key={header}>{header}</TableHead>)}</TableRow></TableHeader>
                    <TableBody>{previewRows.slice(0, 8).map((row, rowIndex) => <TableRow key={`${rowIndex}-${row.join("|")}`}>{headers.map((header, columnIndex) => <TableCell key={`${header}-${columnIndex}`} className="max-w-48 truncate">{row[columnIndex] || "—"}</TableCell>)}</TableRow>)}</TableBody>
                  </Table>
                </div>
              )}
            </section>
            <section className="min-w-0 space-y-3" aria-labelledby="import-mapping-title">
              <div>
                <h3 id="import-mapping-title" className="font-semibold">Para onde vai cada coluna?</h3>
                <p className="text-xs text-muted-foreground">Cada destino pode ser usado uma vez. Colunas sem uso devem ficar em Ignorar.</p>
              </div>
              <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
                {headers.map((header) => (
                  <div key={header} className="grid items-center gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <Label htmlFor={`mapping-${header}`} className="min-w-0 truncate text-xs" title={header}>{header}{mapping[header] === "name" && <span className="ml-1 text-destructive" aria-label="obrigatório">*</span>}</Label>
                    <Select value={mapping[header] ?? IGNORE_VALUE} onValueChange={(value: string | null) => setMapping((previous) => ({ ...previous, [header]: value && value !== IGNORE_VALUE ? value as ImportMappingField : null }))}>
                      <SelectTrigger id={`mapping-${header}`} className="w-full" aria-label={`Destino da coluna ${header}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={IGNORE_VALUE}>Ignorar</SelectItem>
                        {FIELD_OPTIONS.map(([field, label]) => {
                          const usedByAnotherColumn = Object.entries(mapping).some(([otherHeader, target]) => otherHeader !== header && target === field);
                          return <SelectItem key={field} value={field} disabled={usedByAnotherColumn}>{label}{field === "name" ? " · obrigatório" : ""}</SelectItem>;
                        })}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
              {mappingProblem && <p className="text-sm text-destructive" role="alert">{mappingProblem}</p>}
            </section>
          </div>
        )}

        {step === "report" && currentJob && (
          <div className="space-y-4 py-2">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/20 p-3">
              <div>
                <p className="text-sm font-medium">{currentJob.source_filename}</p>
                <p className="text-xs text-muted-foreground" aria-live="polite">{currentJob.status === "RUNNING" || currentJob.status === "QUEUED" ? "Acompanhe enquanto o processamento avança." : "Relatório da importação"}</p>
              </div>
              <Badge className={statusClass(currentJob.status)}>{importJobStatusLabel(currentJob.status)}</Badge>
            </div>
            {!isImportJobTerminal(currentJob.status) && currentJob.status !== "PREVIEWED" && (
              <div className="space-y-2" aria-live="polite">
                <div className="flex justify-between text-xs"><span>Processamento</span><span>{progress}% · {Math.max(0, currentJob.total_rows - currentJob.unprocessed_rows).toLocaleString("pt-BR")} de {currentJob.total_rows.toLocaleString("pt-BR")}</span></div>
                <Progress value={progress} aria-label={`Processamento da importação: ${progress}%`} />
              </div>
            )}
            {currentJob.status === "CANCEL_REQUESTED" && <p className="text-sm text-muted-foreground" role="status">O cancelamento foi solicitado e será concluído pelo processador.</p>}
            {currentJob.error_message && <p className="text-sm text-destructive" role="alert">{currentJob.error_message}</p>}
            {report && <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {(["accepted", "duplicate", "rejected", "failed"] as const).map((key) => <div key={key} className="rounded-md border bg-card p-3 text-center"><p className="text-xs text-muted-foreground">{key === "accepted" ? "Aceitas" : key === "duplicate" ? "Duplicadas" : key === "rejected" ? "Rejeitadas" : "Falhas"}</p><p className="text-xl font-bold tabular-nums">{report[key]}</p></div>)}
            </div>}
            {currentJob.status === "PARTIAL" && <div className="flex items-start gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />A importação terminou parcialmente. Os registros aceitos foram processados; revise as linhas com problema.</div>}
            {currentJob.status === "SUCCEEDED" && <div className="flex items-center gap-2 rounded-md bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300"><CheckCircle2 className="h-4 w-4" aria-hidden="true" />Importação concluída. Os leads estão disponíveis na campanha.</div>}
            {report && report.errors.length > 0 && <div className="space-y-2"><h3 className="text-sm font-semibold">Problemas encontrados na simulação</h3><div className="max-h-32 overflow-y-auto rounded-md border p-2 text-xs">{report.errors.map((item) => <p key={`${item.line_number}-${item.reason_code}`} className="py-1 text-muted-foreground">Linha {item.line_number}: <span className="text-foreground">{item.message || item.reason_code || "Não especificado"}</span></p>)}</div></div>}
            {showRows && <section className="space-y-2" aria-labelledby="import-row-results-title"><div className="flex flex-wrap items-center justify-between gap-2"><h3 id="import-row-results-title" className="text-sm font-semibold">Resultados por linha</h3><Select value={rowStatus ?? "all"} onValueChange={(value: string | null) => { setRowStatus(value === "all" ? undefined : value as ImportRowStatus); setRowsOffset(0); }}><SelectTrigger className="w-40" aria-label="Filtrar resultados por status"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Todos os status</SelectItem>{Object.entries(ROW_STATUS_LABELS).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div>{rowsQuery.isLoading ? <p className="py-4 text-sm text-muted-foreground">Carregando resultados...</p> : rowsQuery.isError ? <p className="py-4 text-sm text-destructive" role="alert">Não foi possível carregar os resultados por linha.</p> : rowsQuery.data?.rows.length ? <div className="overflow-auto rounded-md border"><Table><TableCaption>Resultados processados nesta importação.</TableCaption><TableHeader><TableRow><TableHead>Linha</TableHead><TableHead>Status</TableHead><TableHead>Motivo</TableHead><TableHead>Mensagem</TableHead></TableRow></TableHeader><TableBody>{rowsQuery.data.rows.map((row) => <TableRow key={row.line_number}><TableCell>{row.line_number}</TableCell><TableCell><Badge variant="outline">{ROW_STATUS_LABELS[row.status]}</Badge></TableCell><TableCell>{row.reason_code || "—"}</TableCell><TableCell className="max-w-72 truncate">{row.message || "—"}</TableCell></TableRow>)}</TableBody></Table></div> : <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">Ainda não há resultados de linhas para este filtro.</p>}<div className="flex items-center justify-end gap-2"><Button variant="outline" size="sm" onClick={() => setRowsOffset((value) => Math.max(0, value - 25))} disabled={rowsOffset === 0 || rowsQuery.isFetching}><ChevronLeft className="h-4 w-4" aria-hidden="true" />Anterior</Button><span className="text-xs text-muted-foreground">Linhas {rowsOffset + 1}–{rowsOffset + (rowsQuery.data?.rows.length ?? 0)}</span><Button variant="outline" size="sm" onClick={() => setRowsOffset((value) => value + 25)} disabled={!rowsQuery.data?.has_more || rowsQuery.isFetching}>Próxima<ChevronRight className="h-4 w-4" aria-hidden="true" /></Button></div></section>}
          </div>
        )}

        <DialogFooter className="flex flex-wrap justify-between gap-2 sm:justify-between">
          <div className="flex flex-wrap gap-2">
            {currentJob && canCancel && <Button variant="destructive" onClick={handleCancel} disabled={busy}><XCircle className="h-4 w-4" aria-hidden="true" />Cancelar</Button>}
            {currentJob && canRecover && <Button variant="outline" onClick={handleRecover} disabled={busy}><RotateCcw className="h-4 w-4" aria-hidden="true" />Retomar ({currentJob.attempts}/3)</Button>}
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            {currentJob && (isImportJobTerminal(currentJob.status) || currentJob.status === "CANCEL_REQUESTED") && <Button variant="outline" onClick={resetFlow}>Nova importação</Button>}
            {step === "upload" && <><Button variant="outline" onClick={() => setOpen(false)}>Fechar</Button><Button onClick={handleUpload} disabled={!file || busy}>{uploadMutation.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />Preparando...</> : "Gerar prévia"}</Button></>}
            {step === "mapping" && <><Button variant="outline" onClick={() => setStep("upload")} disabled={busy}>Voltar</Button><Button onClick={handleDryRun} disabled={Boolean(mappingProblem) || busy}>{dryRunMutation.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />Simulando...</> : "Executar simulação"}</Button></>}
            {step === "report" && currentJob?.status === "PREVIEWED" && <Button onClick={handleConfirm} disabled={!dryRunReport || Boolean(mappingProblem) || busy}>{confirmMutation.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />Confirmando...</> : "Confirmar importação"}</Button>}
            {step === "report" && currentJob && currentJob.status !== "PREVIEWED" && !isImportJobTerminal(currentJob.status) && <Button variant="outline" onClick={() => setOpen(false)}>Continuar em segundo plano</Button>}
            {step === "report" && currentJob && isImportJobTerminal(currentJob.status) && <Button onClick={() => setOpen(false)}>Fechar</Button>}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
