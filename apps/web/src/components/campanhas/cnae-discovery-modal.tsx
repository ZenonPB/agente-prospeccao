"use client";

import { useState, useCallback } from "react";
import { useCollectCnae } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Search, Building, Loader2, Info, Filter } from "lucide-react";
import { toast } from "sonner";

interface CnaeDiscoveryModalProps {
  campaignId: string;
  campaignName: string;
  onJobStarted?: (jobId: string) => void;
}

export function CnaeDiscoveryModal({ campaignId, campaignName, onJobStarted }: CnaeDiscoveryModalProps) {
  const [open, setOpen] = useState(false);
  const [cnaeCode, setCnaeCode] = useState("");
  const [cnpjsRaw, setCnpjsRaw] = useState("");
  const [maxLeads, setMaxLeads] = useState(10);
  const [porteCategory, setPorteCategory] = useState<string>("all");
  const collectCnae = useCollectCnae();

  const handleStartCollection = useCallback(async () => {
    const cnpjs = cnpjsRaw
      .split(/[\n,;]+/)
      .map((c) => c.trim())
      .filter((c) => c.length > 0);

    if (!cnaeCode && cnpjs.length === 0) {
      toast.error("Informe um código de CNAE ou ao menos um CNPJ para buscar");
      return;
    }

    try {
      const res = await collectCnae.mutateAsync({
        campaignId,
        cnaeCode: cnaeCode || undefined,
        cnpjs: cnpjs.length > 0 ? cnpjs : undefined,
        maxLeads,
        porteCategory: porteCategory !== "all" ? porteCategory : undefined,
      });

      toast.success("Coleta por CNAE iniciada em segundo plano!");
      setOpen(false);

      if (onJobStarted && res.job_id) {
        onJobStarted(res.job_id);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao iniciar busca por CNAE");
    }
  }, [campaignId, cnaeCode, cnpjsRaw, maxLeads, porteCategory, collectCnae, onJobStarted]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" />}>
        <Building className="mr-2 h-4 w-4" aria-hidden="true" />
        Buscar por Ramo de Atuação
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <Building className="h-5 w-5 text-primary" aria-hidden="true" />
            Buscar Empresas por Ramo de Atividade
          </DialogTitle>
          <DialogDescription>
            Encontre empresas na base da Receita Federal pelo seu ramo oficial para a campanha <strong>{campaignName}</strong>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-3 text-xs text-blue-900 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-200">
            <p className="flex items-center gap-1.5 font-medium mb-1">
              <Info className="h-4 w-4 text-blue-600 dark:text-blue-400" aria-hidden="true" />
              Fonte dos dados:
            </p>
            <p className="text-muted-foreground">
              Consultamos o cadastro oficial público de empresas (Receita Federal) com proteção automática contra limites de uso.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="cnae-input">Código do Ramo de Atividade (CNAE)</Label>
            <Input
              id="cnae-input"
              placeholder="Ex: 28.69-1-00 (Serviços de engenharia)"
              value={cnaeCode}
              onChange={(e) => setCnaeCode(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="cnpjs-input">Ou informe CNPJs específicos (um por linha)</Label>
            <Textarea
              id="cnpjs-input"
              rows={3}
              placeholder="00.000.000/0001-00&#10;11.111.111/0001-11"
              value={cnpjsRaw}
              onChange={(e) => setCnpjsRaw(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="max-leads">Quantidade máxima de empresas</Label>
            <Input
              id="max-leads"
              type="number"
              min={1}
              max={100}
              value={maxLeads}
              onChange={(e) => setMaxLeads(parseInt(e.target.value) || 10)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="porte-filter" className="flex items-center gap-1.5">
              <Filter className="h-3.5 w-3.5" aria-hidden="true" />
              Porte da Empresa (opcional)
            </Label>
            <Select value={porteCategory} onValueChange={(v) => setPorteCategory(v || "all")}>
              <SelectTrigger id="porte-filter">
                <SelectValue>
                  {(value) => {
                    const labels: Record<string, string> = {
                      all: "Todos os portes",
                      pequeno: "Pequeno (ME, EPP)",
                      medio: "Médio (LTDA, SLU)",
                      grande: "Grande (S.A.)",
                    };
                    return labels[value || "all"] || "Todos os portes";
                  }}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os portes</SelectItem>
                <SelectItem value="pequeno">Pequeno (ME, EPP)</SelectItem>
                <SelectItem value="medio">Médio (LTDA, SLU)</SelectItem>
                <SelectItem value="grande">Grande (S.A.)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancelar
          </Button>
          <Button onClick={handleStartCollection} disabled={collectCnae.isPending}>
            {collectCnae.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                Iniciando busca...
              </>
            ) : (
              <>
                <Search className="mr-2 h-4 w-4" aria-hidden="true" />
                Buscar Empresas
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}