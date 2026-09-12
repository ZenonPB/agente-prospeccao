'use client';

import { useMemo, useState } from 'react';
import { Building2, Database, Loader2, MailCheck, Search, Sparkles, Users } from 'lucide-react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useCompanySearch, useInterpretSearch, usePeopleSearch } from '@/hooks/use-search';
import type {
  CompanySearchFilters,
  CompanySearchResult,
  PeopleSearchFilters,
  PeopleSearchResult,
  SearchIntent,
  SearchTarget,
} from '@/lib/search-api';

function splitList(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function numberOrUndefined(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const parsed = Number(value.replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : undefined;
}

function statusLabel(status: string) {
  if (status === 'actionable') return 'Pronto para contato';
  if (status === 'review') return 'Revisar dados';
  return 'Baixa acionabilidade';
}

export function SearchWorkspace() {
  const [tab, setTab] = useState<SearchTarget>('companies');
  const [naturalQuery, setNaturalQuery] = useState('');
  const [intent, setIntent] = useState<SearchIntent | null>(null);
  const interpret = useInterpretSearch();
  const companySearch = useCompanySearch();
  const peopleSearch = usePeopleSearch();

  const [companyQuery, setCompanyQuery] = useState('');
  const [locations, setLocations] = useState('');
  const [industries, setIndustries] = useState('');
  const [cnaes, setCnaes] = useState('');
  const [technologies, setTechnologies] = useState('');
  const [signals, setSignals] = useState('');
  const [employeeMin, setEmployeeMin] = useState('');
  const [employeeMax, setEmployeeMax] = useState('');
  const [includeUnknown, setIncludeUnknown] = useState(false);

  const [peopleQuery, setPeopleQuery] = useState('');
  const [peopleCompany, setPeopleCompany] = useState('');
  const [domain, setDomain] = useState('');
  const [titles, setTitles] = useState('');
  const [seniorities, setSeniorities] = useState('');
  const [buyerRoles, setBuyerRoles] = useState('');
  const [peopleLocations, setPeopleLocations] = useState('');
  const [emailStatus, setEmailStatus] = useState<PeopleSearchFilters['email_status']>('any');
  const [minActionable, setMinActionable] = useState('');

  const companyFilters = useMemo<CompanySearchFilters>(() => ({
    query: companyQuery || undefined,
    locations: splitList(locations),
    industries: splitList(industries),
    cnaes: splitList(cnaes),
    technologies: splitList(technologies),
    signals: splitList(signals),
    employee_min: numberOrUndefined(employeeMin),
    employee_max: numberOrUndefined(employeeMax),
    include_unknown: includeUnknown,
    limit: 50,
  }), [companyQuery, locations, industries, cnaes, technologies, signals, employeeMin, employeeMax, includeUnknown]);

  const peopleFilters = useMemo<PeopleSearchFilters>(() => ({
    query: peopleQuery || undefined,
    company: peopleCompany || undefined,
    domain: domain || undefined,
    titles: splitList(titles),
    seniorities: splitList(seniorities),
    buyer_roles: splitList(buyerRoles).map((item) => item.toUpperCase()),
    locations: splitList(peopleLocations),
    email_status: emailStatus,
    min_actionable_score: numberOrUndefined(minActionable),
    limit: 50,
  }), [peopleQuery, peopleCompany, domain, titles, seniorities, buyerRoles, peopleLocations, emailStatus, minActionable]);

  function applyIntent(next: SearchIntent) {
    setIntent(next);
    setTab(next.target);
    if (next.target === 'companies' && next.company_filters) {
      const f = next.company_filters;
      setCompanyQuery(f.query ?? '');
      setLocations((f.locations ?? []).join(', '));
      setIndustries((f.industries ?? []).join(', '));
      setCnaes((f.cnaes ?? []).join(', '));
      setTechnologies((f.technologies ?? []).join(', '));
      setSignals((f.signals ?? []).join(', '));
      setEmployeeMin(f.employee_min?.toString() ?? '');
      setEmployeeMax(f.employee_max?.toString() ?? '');
      setIncludeUnknown(Boolean(f.include_unknown));
    }
    if (next.target === 'people' && next.people_filters) {
      const f = next.people_filters;
      setPeopleQuery(f.query ?? '');
      setPeopleCompany(f.company ?? '');
      setDomain(f.domain ?? '');
      setTitles((f.titles ?? []).join(', '));
      setSeniorities((f.seniorities ?? []).join(', '));
      setBuyerRoles((f.buyer_roles ?? []).join(', '));
      setPeopleLocations((f.locations ?? []).join(', '));
      setEmailStatus(f.email_status ?? 'any');
      setMinActionable(f.min_actionable_score?.toString() ?? '');
    }
  }

  async function handleInterpret() {
    if (naturalQuery.trim().length < 3) return;
    try {
      const parsed = await interpret.mutateAsync({ query: naturalQuery, target: 'auto' });
      applyIntent(parsed);
      toast.success('Busca interpretada. Revise os filtros antes de executar.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível interpretar a busca.');
    }
  }

  async function runCompanySearch() {
    try {
      await companySearch.mutateAsync(companyFilters);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Erro ao buscar empresas.');
    }
  }

  async function runPeopleSearch() {
    try {
      await peopleSearch.mutateAsync(peopleFilters);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Erro ao buscar pessoas.');
    }
  }

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden border-primary/20 bg-gradient-to-br from-card to-primary/[0.04]">
        <CardHeader className="pb-4">
          <div className="flex items-center gap-2 text-sm font-medium text-primary">
            <Sparkles className="size-4" aria-hidden="true" />
            Busca assistida
          </div>
          <CardTitle className="text-xl">Descreva quem você quer encontrar</CardTitle>
          <CardDescription>
            A IA apenas transforma seu pedido em filtros. Você revisa tudo antes de consultar a base.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Label htmlFor="natural-search" className="sr-only">Pedido de busca em linguagem natural</Label>
            <Input
              id="natural-search"
              value={naturalQuery}
              onChange={(event) => setNaturalQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !interpret.isPending) void handleInterpret();
              }}
              placeholder="Ex.: diretores de eventos de EJs em São Paulo com e-mail verificado"
              className="h-11 flex-1"
              maxLength={500}
            />
            <Button
              className="h-11 shrink-0"
              onClick={() => void handleInterpret()}
              disabled={interpret.isPending || naturalQuery.trim().length < 3}
            >
              {interpret.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Sparkles className="size-4" aria-hidden="true" />}
              {interpret.isPending ? 'Interpretando...' : 'Interpretar filtros'}
            </Button>
          </div>
          {intent ? (
            <div className="mt-4 rounded-lg border bg-background/70 p-4" role="status" aria-live="polite">
              <p className="text-sm font-medium">{intent.summary}</p>
              {(intent.assumptions.length > 0 || intent.unresolved.length > 0) && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {intent.assumptions.map((item) => <Badge key={item} variant="secondary">Suposição: {item}</Badge>)}
                  {intent.unresolved.map((item) => <Badge key={item} variant="outline">Refinar: {item}</Badge>)}
                </div>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Tabs value={tab} onValueChange={(value) => setTab(value as SearchTarget)}>
        <TabsList className="mx-0">
          <TabsTrigger value="companies"><Building2 aria-hidden="true" /> Empresas</TabsTrigger>
          <TabsTrigger value="people"><Users aria-hidden="true" /> Pessoas</TabsTrigger>
        </TabsList>

        <TabsContent value="companies" className="space-y-5 pt-3">
          <CompanyFilters
            values={{ companyQuery, locations, industries, cnaes, technologies, signals, employeeMin, employeeMax, includeUnknown }}
            setters={{ setCompanyQuery, setLocations, setIndustries, setCnaes, setTechnologies, setSignals, setEmployeeMin, setEmployeeMax, setIncludeUnknown }}
            pending={companySearch.isPending}
            onSearch={() => void runCompanySearch()}
          />
          <CompanyResults data={companySearch.data} pending={companySearch.isPending} />
        </TabsContent>

        <TabsContent value="people" className="space-y-5 pt-3">
          <PeopleFilters
            values={{ peopleQuery, peopleCompany, domain, titles, seniorities, buyerRoles, peopleLocations, emailStatus, minActionable }}
            setters={{ setPeopleQuery, setPeopleCompany, setDomain, setTitles, setSeniorities, setBuyerRoles, setPeopleLocations, setEmailStatus, setMinActionable }}
            pending={peopleSearch.isPending}
            onSearch={() => void runPeopleSearch()}
          />
          <PeopleResults data={peopleSearch.data} pending={peopleSearch.isPending} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Field({ id, label, value, onChange, placeholder, type = 'text' }: { id: string; label: string; value: string; onChange: (value: string) => void; placeholder?: string; type?: string }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </div>
  );
}

function CompanyFilters({ values, setters, pending, onSearch }: any) {
  return (
    <Card>
      <CardHeader><CardTitle>Filtros de empresas</CardTitle><CardDescription>Combine critérios. Campos sem dados permanecem desconhecidos, não negativos.</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Field id="company-query" label="Busca geral" value={values.companyQuery} onChange={setters.setCompanyQuery} placeholder="Nome, categoria, domínio..." />
          <Field id="company-location" label="Localização" value={values.locations} onChange={setters.setLocations} placeholder="Araraquara, SP" />
          <Field id="company-industry" label="Segmentos" value={values.industries} onChange={setters.setIndustries} placeholder="Metalúrgica, clínica" />
          <Field id="company-cnae" label="CNAE" value={values.cnaes} onChange={setters.setCnaes} placeholder="Separados por vírgula" />
          <Field id="company-tech" label="Tecnologias" value={values.technologies} onChange={setters.setTechnologies} placeholder="TOTVS, WordPress" />
          <Field id="company-signals" label="Sinais" value={values.signals} onChange={setters.setSignals} placeholder="HAS_CNC, NEW_FACTORY" />
          <Field id="employees-min" label="Funcionários mínimos" value={values.employeeMin} onChange={setters.setEmployeeMin} type="number" />
          <Field id="employees-max" label="Funcionários máximos" value={values.employeeMax} onChange={setters.setEmployeeMax} type="number" />
        </div>
        <label className="flex items-start gap-2 text-sm text-muted-foreground">
          <input type="checkbox" className="mt-0.5 size-4" checked={values.includeUnknown} onChange={(event) => setters.setIncludeUnknown(event.target.checked)} />
          <span>Incluir empresas cujo dado necessário ainda é desconhecido. Elas aparecem identificadas como “dados incompletos”.</span>
        </label>
        <Button onClick={onSearch} disabled={pending}>
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Search className="size-4" aria-hidden="true" />}
          {pending ? 'Buscando...' : 'Buscar empresas'}
        </Button>
      </CardContent>
    </Card>
  );
}

function PeopleFilters({ values, setters, pending, onSearch }: any) {
  return (
    <Card>
      <CardHeader><CardTitle>Filtros de pessoas</CardTitle><CardDescription>Priorize decisores com identidade, papel e contato mais acionáveis.</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Field id="people-query" label="Busca geral" value={values.peopleQuery} onChange={setters.setPeopleQuery} placeholder="Nome, cargo, empresa..." />
          <Field id="people-company" label="Empresa" value={values.peopleCompany} onChange={setters.setPeopleCompany} />
          <Field id="people-domain" label="Domínio" value={values.domain} onChange={setters.setDomain} placeholder="empresa.com.br" />
          <Field id="people-titles" label="Cargos" value={values.titles} onChange={setters.setTitles} placeholder="CEO, Diretor de Eventos" />
          <Field id="people-seniority" label="Senioridade" value={values.seniorities} onChange={setters.setSeniorities} placeholder="executive, lead" />
          <Field id="people-buyer-role" label="Buyer roles" value={values.buyerRoles} onChange={setters.setBuyerRoles} placeholder="ECONOMIC_BUYER" />
          <Field id="people-location" label="Localização" value={values.peopleLocations} onChange={setters.setPeopleLocations} placeholder="São Paulo, SP" />
          <div className="space-y-1.5">
            <Label htmlFor="email-status">E-mail</Label>
            <select id="email-status" className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={values.emailStatus} onChange={(event) => setters.setEmailStatus(event.target.value)}>
              <option value="any">Qualquer</option><option value="present">Com e-mail</option><option value="verified">Verificado</option><option value="missing">Sem e-mail</option>
            </select>
          </div>
          <Field id="min-actionable" label="Acionabilidade mínima" value={values.minActionable} onChange={setters.setMinActionable} type="number" placeholder="0–100" />
        </div>
        <Button onClick={onSearch} disabled={pending}>
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Search className="size-4" aria-hidden="true" />}
          {pending ? 'Buscando...' : 'Buscar pessoas'}
        </Button>
      </CardContent>
    </Card>
  );
}

function CompanyResults({ data, pending }: { data?: { companies: CompanySearchResult[]; total: number; unknown_count: number; candidate_scan_truncated: boolean }; pending: boolean }) {
  if (pending) return <LoadingState text="Consultando empresas do workspace..." />;
  if (!data) return <InitialState text="Defina os filtros e execute a busca. Nenhum provider externo é acionado nesta etapa." />;
  if (!data.companies.length) return <InitialState text="Nenhuma empresa conhecida corresponde aos filtros atuais." />;
  return (
    <section aria-labelledby="company-results-title" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 id="company-results-title" className="text-lg font-semibold">{data.total} empresas encontradas</h2>{data.candidate_scan_truncated ? <Badge variant="outline">Base ampla — refine os filtros</Badge> : null}</div>
      <div className="grid gap-3 lg:grid-cols-2">
        {data.companies.map((company) => (
          <article key={company.id} className="rounded-xl border bg-card p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="truncate font-semibold">{company.company_name}</h3><p className="text-sm text-muted-foreground">{company.location || 'Localização não informada'}{company.category ? ` · ${company.category}` : ''}</p></div>{company.match_state === 'UNKNOWN' ? <Badge variant="outline">Dados incompletos</Badge> : <Badge variant="secondary">Match</Badge>}</div>
            <div className="mt-3 flex flex-wrap gap-1.5">{company.technologies.slice(0, 4).map((item) => <Badge key={item} variant="outline">{item}</Badge>)}{company.signals.slice(0, 4).map((item) => <Badge key={item} variant="secondary">{item}</Badge>)}</div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-muted-foreground">Domínio</dt><dd className="truncate font-medium">{company.normalized_domain || '—'}</dd></div><div><dt className="text-muted-foreground">Funcionários</dt><dd className="font-medium">{company.employees ?? 'Desconhecido'}</dd></div><div><dt className="text-muted-foreground">CNAE</dt><dd className="truncate font-medium">{company.cnae[0] || '—'}</dd></div><div><dt className="text-muted-foreground">Leads vinculados</dt><dd className="font-medium">{company.lead_count}</dd></div></dl>
          </article>
        ))}
      </div>
    </section>
  );
}

function PeopleResults({ data, pending }: { data?: { people: PeopleSearchResult[]; total: number; candidate_scan_truncated: boolean }; pending: boolean }) {
  if (pending) return <LoadingState text="Priorizando pessoas e acionabilidade..." />;
  if (!data) return <InitialState text="Busque pessoas já resolvidas no workspace. A pontuação explica o que é conhecido e o que ainda precisa de validação." />;
  if (!data.people.length) return <InitialState text="Nenhuma pessoa conhecida corresponde aos filtros atuais." />;
  return (
    <section aria-labelledby="people-results-title" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 id="people-results-title" className="text-lg font-semibold">{data.total} pessoas encontradas</h2>{data.candidate_scan_truncated ? <Badge variant="outline">Base ampla — refine os filtros</Badge> : null}</div>
      <div className="grid gap-3 lg:grid-cols-2">
        {data.people.map((person) => (
          <article key={person.id} className="rounded-xl border bg-card p-4 shadow-sm">
            <div className="flex items-start justify-between gap-4"><div className="min-w-0"><h3 className="truncate font-semibold">{person.name}</h3><p className="text-sm text-muted-foreground">{person.role || 'Cargo não informado'}{person.company.name ? ` · ${person.company.name}` : ''}</p></div><div className="text-right"><p className="text-2xl font-semibold tabular-nums">{Math.round(person.actionable_contact.score)}</p><p className="text-xs text-muted-foreground">{statusLabel(person.actionable_contact.status)}</p></div></div>
            <div className="mt-3 flex flex-wrap gap-1.5"><Badge variant="secondary">{person.buyer_role}</Badge>{person.persona ? <Badge variant="outline">{person.persona}</Badge> : null}{person.email_verified ? <Badge variant="outline"><MailCheck className="size-3" aria-hidden="true" /> E-mail verificado</Badge> : null}</div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-muted-foreground">E-mail</dt><dd className="truncate font-medium">{person.email || 'Não encontrado'}</dd></div><div><dt className="text-muted-foreground">Telefone</dt><dd className="font-medium">{person.phone || 'Não encontrado'}</dd></div><div><dt className="text-muted-foreground">Cobertura do score</dt><dd className="font-medium">{Math.round(person.actionable_contact.coverage * 100)}%</dd></div><div><dt className="text-muted-foreground">Fonte</dt><dd className="truncate font-medium">{person.source || '—'}</dd></div></dl>
            {person.actionable_contact.unknown_dimensions.length ? <p className="mt-3 text-xs text-muted-foreground">Ainda desconhecido: {person.actionable_contact.unknown_dimensions.join(', ')}.</p> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function LoadingState({ text }: { text: string }) {
  return <div className="flex min-h-40 items-center justify-center gap-2 rounded-xl border border-dashed text-sm text-muted-foreground" role="status"><Loader2 className="size-4 animate-spin" aria-hidden="true" />{text}</div>;
}

function InitialState({ text }: { text: string }) {
  return <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 text-center"><Database className="size-6 text-muted-foreground" aria-hidden="true" /><p className="max-w-xl text-sm text-muted-foreground">{text}</p></div>;
}
