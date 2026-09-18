'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/ui/empty-state';
import {
  Check,
  AlertTriangle,
  CircleDashed,
  Database,
  ChevronDown,
} from 'lucide-react';
import { useRegistryHealth } from '@/hooks/use-api';
import type { RegistryHealth } from '@/lib/api';

const STATUS_META: Record<
  RegistryHealth['status'],
  { label: string; className: string; Icon: typeof Check }
> = {
  healthy: {
    label: 'Funcionando normalmente',
    className: 'bg-emerald-100 text-emerald-700',
    Icon: Check,
  },
  degraded: {
    label: 'Atenção necessária',
    className: 'bg-amber-100 text-amber-700',
    Icon: AlertTriangle,
  },
  empty: {
    label: 'Base ainda sem dados',
    className: 'bg-slate-100 text-slate-600',
    Icon: Database,
  },
  unknown: {
    label: 'Ainda não sabemos',
    className: 'bg-slate-100 text-slate-600',
    Icon: CircleDashed,
  },
};

const FILE_STATUS: Record<string, string> = {
  PENDING: 'Em espera',
  RUNNING: 'Em andamento',
  COMPLETED: 'Concluído',
  FAILED: 'Com falha',
};

const TABLE_KIND: Record<string, string> = {
  estabelecimentos: 'Estabelecimentos',
  empresas: 'Empresas',
  cnaes: 'CNAEs',
  municipios: 'Municípios',
};

function formatDate(value: string | null): string {
  if (!value) return 'Ainda não sabemos';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Ainda não sabemos';
  return date.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric' });
}

export default function BaseEmpresasPage() {
  const { data, isLoading, isError, refetch } = useRegistryHealth();
  const [showDetails, setShowDetails] = useState(false);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-bold tracking-tight">Base de empresas</h2>
        <Skeleton className="h-40 rounded-xl" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-bold tracking-tight">Base de empresas</h2>
        <EmptyState
          title="Não foi possível verificar a base"
          description="Tente novamente em instantes."
          action={<Button onClick={() => refetch()}>Tentar novamente</Button>}
        />
      </div>
    );
  }

  const meta = STATUS_META[data.status];
  const StatusIcon = meta.Icon;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Base de empresas</h2>
        <p className="text-sm text-muted-foreground">
          Situação dos dados cadastrais que alimentam suas buscas.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Situação atual</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Status</span>
            <Badge className={meta.className}>
              <StatusIcon className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
              {meta.label}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Última atualização</span>
            <span className="text-sm font-medium">{formatDate(data.last_updated_at)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Empresas disponíveis</span>
            <span className="text-sm font-medium">
              {data.companies == null ? '—' : data.companies.toLocaleString('pt-BR')}
            </span>
          </div>
          <div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDetails((value) => !value)}
              aria-expanded={showDetails}
              className="gap-1 px-2 text-xs"
            >
              Ver detalhes técnicos
              <ChevronDown
                className={`h-3.5 w-3.5 transition-transform ${showDetails ? 'rotate-180' : ''}`}
                aria-hidden="true"
              />
            </Button>
            {showDetails && (
              <div className="mt-2 space-y-3 rounded-lg border bg-muted/30 p-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Referência</span>
                  <span className="font-medium">{data.snapshot_month ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Layout</span>
                  <span className="font-medium">{data.layout_version ?? '—'}</span>
                </div>
                {data.files.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Nenhum arquivo registrado para esta referência.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {data.files.map((file) => (
                      <li key={file.file_name} className="rounded-md border bg-card p-2.5 text-xs">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{file.file_name}</span>
                          <Badge variant="outline" className="text-[10px] font-normal">
                            {FILE_STATUS[file.status] ?? file.status}
                          </Badge>
                        </div>
                        <p className="mt-1 text-muted-foreground">
                          {TABLE_KIND[file.table_kind] ?? file.table_kind} ·{' '}
                          {file.rows_ok.toLocaleString('pt-BR')} linhas aproveitadas
                          {file.rows_rejected > 0 &&
                            ` · ${file.rows_rejected.toLocaleString('pt-BR')} rejeitadas`}
                        </p>
                        {file.sha256 && (
                          <p className="mt-0.5 text-muted-foreground" title={file.sha256}>
                            Verificação: {file.sha256.slice(0, 12)}…
                          </p>
                        )}
                        {file.error && (
                          <p className="mt-0.5 text-amber-700">{file.error}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
