'use client';

import { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Download, CalendarRange, FilterX, Search } from 'lucide-react';
import { toast } from 'sonner';
import type {
  CommercialFilterKey,
  CommercialFilterSnapshot,
} from '@/lib/api';
import type { AnalyticsPeriod } from '@/hooks/use-api';

const PRESETS = [
  { label: '30 dias', days: 30 },
  { label: '90 dias', days: 90 },
  { label: 'Tudo', days: 0 },
];

const STATUS_OPTIONS = [
  { value: 'NOVO', label: 'Novo' },
  { value: 'ANALISADO', label: 'Analisado' },
  { value: 'QUALIFICADO', label: 'Qualificado' },
  { value: 'CONTATADO', label: 'Contatado' },
  { value: 'RESPONDIDO', label: 'Respondeu' },
  { value: 'REUNIAO_MARCADA', label: 'Reunião marcada' },
  { value: 'REUNIAO_FEITA', label: 'Reunião feita' },
  { value: 'PROPOSTA_ENVIADA', label: 'Proposta enviada' },
  { value: 'PERDIDO', label: 'Perdido' },
  { value: 'DESQUALIFICADO', label: 'Desqualificado' },
];

const SCORE_OPTIONS = [
  { value: '0-39', label: '0–39' },
  { value: '40-59', label: '40–59' },
  { value: '60-79', label: '60–79' },
  { value: '80-100', label: '80–100' },
];

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function selectClassName() {
  return 'h-8 min-w-36 rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30';
}

type FilterSetter = <K extends CommercialFilterKey>(
  key: K,
  value: CommercialFilterSnapshot[K],
) => void;

export function ReportControls({
  period,
  filters,
  onChange,
  onFilterChange,
  onClear,
  hasFilters,
  onExport,
  exporting,
  campaigns,
  consultants,
}: {
  period: AnalyticsPeriod;
  filters: CommercialFilterSnapshot;
  onChange: (p: AnalyticsPeriod) => void;
  onFilterChange: FilterSetter;
  onClear: () => void;
  hasFilters: boolean;
  onExport: () => void;
  exporting: boolean;
  campaigns: ReadonlyArray<{ id: string; name: string }>;
  consultants: ReadonlyArray<{ user_id: string; name: string; email?: string }>;
}) {
  const handlePreset = (days: number) => {
    if (days === 0) {
      onChange({ from: undefined, to: undefined });
      return;
    }
    onChange({ from: isoDaysAgo(days), to: new Date().toISOString().slice(0, 10) });
  };

  const isAll = !period.from && !period.to;
  const rangeLabel = useMemo(() => {
    if (isAll) return 'Todo o período';
    const f = period.from ? new Date(period.from + 'T00:00:00').toLocaleDateString('pt-BR') : 'início';
    const t = period.to ? new Date(period.to + 'T00:00:00').toLocaleDateString('pt-BR') : 'hoje';
    return `${f} — ${t}`;
  }, [period.from, period.to, isAll]);

  const activeCount = Object.values(filters).reduce(
    (count, value) => count + (Array.isArray(value) ? value.length : value ? 1 : 0),
    0,
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <div className="flex min-w-0 flex-col items-stretch gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <span className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
              <CalendarRange className="h-4 w-4" />
              Período:
            </span>
            {PRESETS.map((preset) => (
              <Button
                key={preset.label}
                variant="outline"
                size="sm"
                onClick={() => handlePreset(preset.days)}
                className={preset.days === 0 && isAll ? 'bg-primary text-primary-foreground' : ''}
              >
                {preset.label}
              </Button>
            ))}
            <div className="flex flex-col items-stretch gap-1.5 sm:flex-row sm:items-center">
              <Input
                type="date"
                value={period.from || ''}
                onChange={(event) => onChange({ ...period, from: event.target.value || undefined })}
                className="h-8 w-36"
                aria-label="Data inicial"
              />
              <span className="text-muted-foreground sm:inline">até</span>
              <Input
                type="date"
                value={period.to || ''}
                onChange={(event) => onChange({ ...period, to: event.target.value || undefined })}
                className="h-8 w-36"
                aria-label="Data final"
              />
            </div>
            <span className="text-xs text-muted-foreground">{rangeLabel}</span>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
            <label className="relative sm:col-span-2 xl:col-span-1">
              <span className="sr-only">Buscar empresa</span>
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input
                value={filters.search || ''}
                onChange={(event) => onFilterChange('search', event.target.value || undefined)}
                placeholder="Buscar empresa..."
                className="h-8 pl-8"
                aria-label="Buscar empresa"
              />
            </label>
            <label>
              <span className="sr-only">Campanha</span>
              <select
                value={filters.campaign_id || ''}
                onChange={(event) => onFilterChange('campaign_id', event.target.value || undefined)}
                className={selectClassName() + ' w-full'}
                aria-label="Campanha"
              >
                <option value="">Todas as campanhas</option>
                {campaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.name}</option>)}
              </select>
            </label>
            <label>
              <span className="sr-only">Consultor</span>
              <select
                value={filters.consultant_id || ''}
                onChange={(event) => onFilterChange('consultant_id', event.target.value || undefined)}
                className={selectClassName() + ' w-full'}
                aria-label="Consultor"
              >
                <option value="">Todos os consultores</option>
                {consultants.map((consultant) => <option key={consultant.user_id} value={consultant.user_id}>{consultant.name || consultant.email || 'Sem nome'}</option>)}
              </select>
            </label>
            <label>
              <span className="sr-only">Status</span>
              <select
                value={filters.status?.[0] || ''}
                onChange={(event) => onFilterChange('status', event.target.value ? [event.target.value] : undefined)}
                className={selectClassName() + ' w-full'}
                aria-label="Status do lead"
              >
                <option value="">Todos os status</option>
                {STATUS_OPTIONS.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}
              </select>
            </label>
            <label>
              <span className="sr-only">Faixa de score</span>
              <select
                value={filters.score_bucket?.[0] || ''}
                onChange={(event) => onFilterChange('score_bucket', event.target.value ? [event.target.value] : undefined)}
                className={selectClassName() + ' w-full'}
                aria-label="Faixa de score"
              >
                <option value="">Todas as faixas</option>
                {SCORE_OPTIONS.map((score) => <option key={score.value} value={score.value}>{score.label}</option>)}
              </select>
            </label>
          </div>
        </div>

        <Button onClick={onExport} disabled={exporting} className="min-h-11 sm:min-h-9">
          {exporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
          Exportar PDF
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground" aria-live="polite">
        <span>{hasFilters ? `${activeCount} filtro${activeCount === 1 ? '' : 's'} ativo${activeCount === 1 ? '' : 's'}` : 'Nenhum filtro adicional ativo'}</span>
        <Button type="button" variant="ghost" size="sm" onClick={onClear} disabled={!hasFilters} className="h-7 px-2 text-xs">
          <FilterX className="mr-1.5 h-3.5 w-3.5" />
          Limpar filtros
        </Button>
      </div>
    </div>
  );
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  toast.success('Relatório PDF baixado.');
}
