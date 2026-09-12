'use client';

import { useEffect, useMemo, useState } from 'react';
import { Building2, Database, Loader2, Search } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useCompanySearch } from '@/hooks/use-search';
import { SEARCH_SIGNAL_OPTIONS } from '@/lib/commercial-labels';
import { signalLabel } from '@/lib/offers';
import type { CompanySearchFilters, CompanySearchResult } from '@/lib/search-api';

function splitList(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function numberOrUndefined(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const parsed = Number(value.replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : undefined;
}

function Field({ id, label, value, onChange, placeholder, type = 'text' }: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </div>
  );
}

export function CompanySearchPanel({ interpretedFilters }: { interpretedFilters?: CompanySearchFilters | null }) {
  const search = useCompanySearch();
  const [query, setQuery] = useState('');
  const [locations, setLocations] = useState('');
  const [industries, setIndustries] = useState('');
  const [cnaes, setCnaes] = useState('');
  const [technologies, setTechnologies] = useState('');
  const [signals, setSignals] = useState<string[]>([]);
  const [employeeMin, setEmployeeMin] = useState('');
  const [employeeMax, setEmployeeMax] = useState('');
  const [includeUnknown, setIncludeUnknown] = useState(false);

  useEffect(() => {
    if (!interpretedFilters) return;
    setQuery(interpretedFilters.query ?? '');
    setLocations((interpretedFilters.locations ?? []).join(', '));
    setIndustries((interpretedFilters.industries ?? []).join(', '));
    setCnaes((interpretedFilters.cnaes ?? []).join(', '));
    setTechnologies((interpretedFilters.technologies ?? []).join(', '));
    setSignals(interpretedFilters.signals ?? []);
    setEmployeeMin(interpretedFilters.employee_min?.toString() ?? '');
    setEmployeeMax(interpretedFilters.employee_max?.toString() ?? '');
    setIncludeUnknown(Boolean(interpretedFilters.include_unknown));
  }, [interpretedFilters]);

  const filters = useMemo<CompanySearchFilters>(() => ({
    query: query || undefined,
    locations: splitList(locations),
    industries: splitList(industries),
    cnaes: splitList(cnaes),
    technologies: splitList(technologies),
    signals,
    employee_min: numberOrUndefined(employeeMin),
    employee_max: numberOrUndefined(employeeMax),
    include_unknown: includeUnknown,
    limit: 50,
  }), [query, locations, industries, cnaes, technologies, signals, employeeMin, employeeMax, includeUnknown]);

  function toggleSignal(signal: string) {
    setSignals((current) => current.includes(signal) ? current.filter((item) => item !== signal) : [...current, signal]);
  }

  async function runSearch() {
    try {
      await search.mutateAsync(filters);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível buscar empresas.');
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Filtros de empresas</CardTitle>
          <CardDescription>Combine apenas os critérios importantes para esta prospecção. Informações ausentes não são tratadas como negativas.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Field id="company-query" label="Empresa ou termo" value={query} onChange={setQuery} placeholder="Nome, segmento ou domínio" />
            <Field id="company-location" label="Localização" value={locations} onChange={setLocations} placeholder="Araraquara, SP" />
            <Field id="company-industry" label="Segmentos" value={industries} onChange={setIndustries} placeholder="Metalúrgica, clínica" />
            <Field id="company-cnae" label="CNAE" value={cnaes} onChange={setCnaes} placeholder="Um ou mais códigos, separados por vírgula" />
            <Field id="company-tech" label="Tecnologias utilizadas" value={technologies} onChange={setTechnologies} placeholder="TOTVS, WordPress" />
            <div className="grid grid-cols-2 gap-3">
              <Field id="employees-min" label="Mín. funcionários" value={employeeMin} onChange={setEmployeeMin} type="number" />
              <Field id="employees-max" label="Máx. funcionários" value={employeeMax} onChange={setEmployeeMax} type="number" />
            </div>
          </div>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Sinais comerciais</legend>
            <p className="text-sm text-muted-foreground">Selecione apenas quando quiser exigir um indício específico.</p>
            <div className="flex flex-wrap gap-2">
              {SEARCH_SIGNAL_OPTIONS.map((signal) => {
                const selected = signals.includes(signal);
                return (
                  <Button key={signal} type="button" size="sm" variant={selected ? 'default' : 'outline'} aria-pressed={selected} onClick={() => toggleSignal(signal)}>
                    {signalLabel(signal)}
                  </Button>
                );
              })}
            </div>
            {signals.filter((signal) => !SEARCH_SIGNAL_OPTIONS.includes(signal as (typeof SEARCH_SIGNAL_OPTIONS)[number])).map((signal) => (
              <Badge key={signal} variant="secondary">{signalLabel(signal)}</Badge>
            ))}
          </fieldset>

          <div className="flex items-start gap-3 rounded-lg border bg-muted/20 p-3">
            <Switch id="include-unknown" checked={includeUnknown} onCheckedChange={(value) => setIncludeUnknown(value === true)} className="mt-0.5" />
            <div className="space-y-0.5">
              <Label htmlFor="include-unknown">Incluir empresas com informações incompletas</Label>
              <p className="text-xs text-muted-foreground">Útil para ampliar a busca sem fingir que um dado desconhecido atende ao critério.</p>
            </div>
          </div>

          <Button onClick={() => void runSearch()} disabled={search.isPending}>
            {search.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Search className="size-4" aria-hidden="true" />}
            {search.isPending ? 'Buscando...' : 'Buscar empresas'}
          </Button>
        </CardContent>
      </Card>

      <CompanyResults data={search.data} pending={search.isPending} />
    </div>
  );
}

function CompanyResults({ data, pending }: {
  data?: { companies: CompanySearchResult[]; total: number; unknown_count: number; candidate_scan_truncated: boolean };
  pending: boolean;
}) {
  if (pending) return <StateCard icon={<Loader2 className="size-5 animate-spin" aria-hidden="true" />} text="Consultando as empresas disponíveis..." />;
  if (!data) return <StateCard icon={<Database className="size-5" aria-hidden="true" />} text="Defina os filtros e faça a busca. Esta etapa usa somente dados que já estão no sistema." />;
  if (!data.companies.length) return <StateCard icon={<Building2 className="size-5" aria-hidden="true" />} text="Nenhuma empresa conhecida corresponde aos filtros atuais." />;

  return (
    <section aria-labelledby="company-results-title" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="company-results-title" className="text-lg font-semibold">{data.total} empresa{data.total === 1 ? '' : 's'} encontrada{data.total === 1 ? '' : 's'}</h2>
        {data.candidate_scan_truncated ? <Badge variant="outline">Há mais resultados possíveis — refine os filtros</Badge> : null}
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {data.companies.map((company) => (
          <article key={company.id} className="rounded-xl border bg-card p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="truncate font-semibold">{company.company_name}</h3>
                <p className="text-sm text-muted-foreground">{company.location || 'Localização não informada'}{company.category ? ` · ${company.category}` : ''}</p>
              </div>
              <Badge variant={company.match_state === 'UNKNOWN' ? 'outline' : 'secondary'}>
                {company.match_state === 'UNKNOWN' ? 'Informações incompletas' : 'Compatível'}
              </Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {company.technologies.slice(0, 4).map((item) => <Badge key={item} variant="outline">{item}</Badge>)}
              {company.signals.slice(0, 4).map((item) => <Badge key={item} variant="secondary">{signalLabel(item)}</Badge>)}
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-muted-foreground">Domínio</dt><dd className="truncate font-medium">{company.normalized_domain || 'Não informado'}</dd></div>
              <div><dt className="text-muted-foreground">Funcionários</dt><dd className="font-medium">{company.employees ?? 'Não informado'}</dd></div>
              <div><dt className="text-muted-foreground">CNAE</dt><dd className="truncate font-medium">{company.cnae[0] || 'Não informado'}</dd></div>
              <div><dt className="text-muted-foreground">Oportunidades conhecidas</dt><dd className="font-medium">{company.lead_count}</dd></div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}

function StateCard({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 text-center text-muted-foreground" role="status">
      {icon}
      <p className="max-w-xl text-sm">{text}</p>
    </div>
  );
}
