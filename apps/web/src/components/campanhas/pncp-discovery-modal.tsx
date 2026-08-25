"use client";

import { useState, useCallback } from "react";
import { useCollectPncp } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Search, Landmark, Loader2, Info } from "lucide-react";
import { toast } from "sonner";

interface PncpDiscoveryModalProps {
  campaignId: string;
  campaignName: string;
  onJobStarted?: (jobId: string) => void;
}

const PERIOD_OPTIONS = [
  { value: "7", label: "Últimos 7 dias" },
  { value: "15", label: "Últimos 15 dias" },
  { value: "30", label: "Últimos 30 dias" },
  { value: "60", label: "Últimos 60 dias" },
  { value: "90", label: "Últimos 90 dias" },
];

export function PncpDiscoveryModal({ campaignId, campaignName, onJobStarted }: PncpDiscoveryModalProps) {
  const [open, setOpen] = useState(false);
  const [daysBack, setDaysBack] = useState("30");
  const [uf, setUf] = useState("");
  const [keyword, setKeyword] = useState("");
  const [maxLeads, setMaxLeads] = useState(10);
  const collectPncp = useCollectPncp();

  const handleStartCollection = useCallback(async () => {
    const ufClean = uf.trim().toUpperCase();

    if (ufClean && !/^[A-Z]{2}$/.test(ufClean)) {
      toast.error("Informe a sigla do estado com 2 letras (ex: SP)");
      return;
    }

    try {
      const res = await collectPncp.mutateAsync({
        campaignId,
        daysBack: parseInt(daysBack, 10) || 30,
        uf: ufClean || undefined,
        keyword: keyword.trim() || undefined,
        maxLeads,
      });

      toast.success("Busca de licitações iniciada em segundo plano!");
      setOpen(false);

      if (onJobStarted && res.job_id) {
        onJobStarted(res.job_id);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao iniciar busca no PNCP");
    }
  }, [campaignId, daysBack, uf, keyword, maxLeads, collectPncp, onJobStarted]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" />}>
        <Landmark className="mr-2 h-4 w-4" aria-hidden="true" />
        Buscar em Licitações
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <Landmark className="h-5 w-5 text-primary" aria-hidden="true" />
            Empresas que vencem licitações
          </DialogTitle>
          <DialogDescription>
            Encontre fornecedores de contratos públicos no portal nacional do governo para a campanha{" "}
            <strong>{campaignName}</strong>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-3 text-xs text-blue-900 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-200">
            <p className="mb-1 flex items-center gap-1.5 font-medium">
              <Info className="h-4 w-4 text-blue-600 dark:text-blue-400" aria-hidden="true" />
              Fonte dos dados:
            </p>
            <p className="text-muted-foreground">
              Consultamos o PNCP (Portal Nacional de Contratações Públicas) — dados abertos oficiais, sem custo e
              sem necessidade de cadastro. Empresa que venceu contrato com o poder público tem porte e setor
              comprovados.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="pncp-period">Período de publicação dos contratos</Label>
            <Select value={daysBack} onValueChange={(v) => setDaysBack(v || "30")}>
              <SelectTrigger id="pncp-period">
                <SelectValue>
                  {(value) =>
                    PERIOD_OPTIONS.find((o) => o.value === value)?.label ?? "Últimos 30 dias"
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {PERIOD_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="pncp-uf">Estado do contratante (opcional)</Label>
            <Input
              id="pncp-uf"
              placeholder="Ex: SP"
              maxLength={2}
              value={uf}
              onChange={(e) => setUf(e.target.value)}
              onBlur={() => setUf((v) => v.trim().toUpperCase())}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="pncp-keyword">Palavra-chave no objeto do contrato (opcional)</Label>
            <Input
              id="pncp-keyword"
              placeholder="Ex: usinagem, manutenção, site"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="pncp-max-leads">Quantidade máxima de empresas</Label>
            <Input
              id="pncp-max-leads"
              type="number"
              min={1}
              max={100}
              value={maxLeads}
              onChange={(e) => setMaxLeads(parseInt(e.target.value) || 10)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancelar
          </Button>
          <Button onClick={handleStartCollection} disabled={collectPncp.isPending}>
            {collectPncp.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                Iniciando busca...
              </>
            ) : (
              <>
                <Search className="mr-2 h-4 w-4" aria-hidden="true" />
                Buscar Fornecedores
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
