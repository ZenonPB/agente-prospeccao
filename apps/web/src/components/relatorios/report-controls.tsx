'use client';

import { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Download, CalendarRange } from 'lucide-react';
import { toast } from 'sonner';
import type { AnalyticsPeriod } from '@/hooks/use-api';

const PRESETS = [
  { label: '30 dias', days: 30 },
  { label: '90 dias', days: 90 },
  { label: 'Tudo', days: 0 },
];

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export function ReportControls({
  period,
  onChange,
  onExport,
  exporting,
}: {
  period: AnalyticsPeriod;
  onChange: (p: AnalyticsPeriod) => void;
  onExport: () => void;
  exporting: boolean;
}) {
  const handlePreset = (days: number) => {
    if (days === 0) {
      onChange({});
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

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 flex-col items-stretch gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <span className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
          <CalendarRange className="h-4 w-4" />
          Período:
        </span>
        {PRESETS.map((p) => (
          <Button
            key={p.label}
            variant="outline"
            size="sm"
            onClick={() => handlePreset(p.days)}
            className={p.days === 0 && isAll ? 'bg-primary text-primary-foreground' : ''}
          >
            {p.label}
          </Button>
        ))}
        <div className="flex flex-col items-stretch gap-1.5 sm:flex-row sm:items-center">
          <Input
            type="date"
            value={period.from || ''}
            onChange={(e) => onChange({ ...period, from: e.target.value || undefined })}
            className="h-8 w-36"
            aria-label="Data inicial"
          />
          <span className="text-muted-foreground sm:inline">até</span>
          <Input
            type="date"
            value={period.to || ''}
            onChange={(e) => onChange({ ...period, to: e.target.value || undefined })}
            className="h-8 w-36"
            aria-label="Data final"
          />
        </div>
        <span className="text-xs text-muted-foreground">{rangeLabel}</span>
      </div>

      <Button onClick={onExport} disabled={exporting} className="min-h-11 sm:min-h-9">
        {exporting ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Download className="mr-2 h-4 w-4" />
        )}
        Exportar PDF
      </Button>
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
