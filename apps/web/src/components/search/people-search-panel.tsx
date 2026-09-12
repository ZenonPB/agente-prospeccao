'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Database, Loader2, MailCheck, Search, Users } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { usePeopleSearch } from '@/hooks/use-search';
import {
  BUYER_ROLE_OPTIONS,
  buyerRoleLabel,
  contactDimensionLabel,
  providerLabel,
} from '@/lib/commercial-labels';
import type { PeopleSearchFilters, PeopleSearchResult } from '@/lib/search-api';

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

function contactStatusLabel(status: string) {
  if (status === 'actionable') return 'Pronto para contato';
  if (status === 'review') return 'Vale revisar os dados';
  return 'Poucos dados para contato';
}

export function PeopleSearchPanel({ interpretedFilters }: { interpretedFilters?: PeopleSearchFilters | null }) {
  const search = usePeopleSearch();
  const [query, setQuery] = useState('');
  const [company, setCompany] = useState('');
  const [domain, setDomain] = useState('');
  const [titles, setTitles] = useState('');
  const [buyerRoles, setBuyerRoles] = useState<string[]>([]);
  const [locations, setLocations] = useState('');
  const [emailStatus, setEmailStatus] = useState<PeopleSearchFilters['email_status']>('any');
  const [phoneStatus, setPhoneStatus] = useState<PeopleSearchFilters['phone_status']>('any');
  const [minQuality, setMinQuality] = useState('');

  useEffect(() => {
    if (!interpretedFilters) return;
    setQuery(interpretedFilters.query ?? '');
    setCompany(interpretedFilters.company ?? '');
    setDomain(interpretedFilters.domain ?? '');
    setTitles((interpretedFilters.titles ?? []).join(', '));
    setBuyerRoles(interpretedFilters.buyer_roles ?? []);
    setLocations((interpretedFilters.locations ?? []).join(', '));
    setEmailStatus(interpretedFilters.email_status ?? 'any');
    setPhoneStatus(interpretedFilters.phone_status ?? 'any');
    setMinQuality(interpretedFilters.min_actionable_score?.toString() ?? '');
  }, [interpretedFilters]);

  const filters = useMemo<PeopleSearchFilters>(() => ({
    query: query || undefined,
    company: company || undefined,
    domain: domain || undefined,
    titles: splitList(titles),
    buyer_roles: buyerRoles,
    locations: splitList(locations),
    email_status: emailStatus,
    phone_status: phoneStatus,
    min_actionable_score: numberOrUndefined(minQuality),
    limit: 50,
  }), [query, company, domain, titles, buyerRoles, locations, emailStatus, phoneStatus, minQuality]);

  function toggleRole(role: string) {
    setBuyerRoles((current) => current.includes(role) ? current.filter((item) => item !== role) : [...current, role]);
  }

  async function runSearch() {
    try {
      await search.mutateAsync(filters);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível buscar pessoas.');
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Filtros de pessoas</CardTitle>
          <CardDescription>Encontre decisores e contatos com os dados mais úteis para a próxima abordagem.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Field id="people-query" label="Pessoa ou termo" value={query} onChange={setQuery} placeholder="Nome, cargo ou empresa" />
            <Field id="people-company" label="Empresa" value={company} onChange={setCompany} placeholder="Nome da empresa" />
            <Field id="people-domain" label="Domínio da empresa" value={domain} onChange={setDomain} placeholder="empresa.com.br" />
            <Field id="people-titles" label="Cargos" value={titles} onChange={setTitles} placeholder="Diretor de Eventos, CEO" />
            <Field id="people-location" label="Localização" value={locations} onChange={setLocations} placeholder="São Paulo, SP" />
            <Field id="min-quality" label="Qualidade mínima do contato" value={minQuality} onChange={setMinQuality} type="number" placeholder="0 a 100" />

            <div className="space-y-1.5">
              <Label htmlFor="email-status">E-mail</Label>
              <Select value={emailStatus} onValueChange={(value) => setEmailStatus(value as PeopleSearchFilters['email_status'])}>
                <SelectTrigger id="email-status" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">Qualquer situação</SelectItem>
                  <SelectItem value="present">Com e-mail</SelectItem>
                  <SelectItem value="verified">E-mail confirmado por fonte confiável</SelectItem>
                  <SelectItem value="missing">Sem e-mail</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="phone-status">Telefone</Label>
              <Select value={phoneStatus} onValueChange={(value) => setPhoneStatus(value as PeopleSearchFilters['phone_status'])}>
                <SelectTrigger id="phone-status" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">Qualquer situação</SelectItem>
                  <SelectItem value="present">Com telefone</SelectItem>
                  <SelectItem value="missing">Sem telefone</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Papel na decisão</legend>
            <p className="text-sm text-muted-foreground">Você pode selecionar mais de um papel.</p>
            <div className="flex flex-wrap gap-2">
              {BUYER_ROLE_OPTIONS.map((item) => {
                const selected = buyerRoles.includes(item.value);
                return (
                  <Button key={item.value} type="button" size="sm" variant={selected ? 'default' : 'outline'} aria-pressed={selected} onClick={() => toggleRole(item.value)}>
                    {item.label}
                  </Button>
                );
              })}
            </div>
            {buyerRoles.filter((role) => !BUYER_ROLE_OPTIONS.some((item) => item.value === role)).map((role) => (
              <Badge key={role} variant="secondary">{buyerRoleLabel(role)}</Badge>
            ))}
          </fieldset>

          <Button onClick={() => void runSearch()} disabled={search.isPending}>
            {search.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Search className="size-4" aria-hidden="true" />}
            {search.isPending ? 'Buscando...' : 'Buscar pessoas'}
          </Button>
        </CardContent>
      </Card>

      <PeopleResults data={search.data} pending={search.isPending} />
    </div>
  );
}

function PeopleResults({ data, pending }: {
  data?: { people: PeopleSearchResult[]; total: number; candidate_scan_truncated: boolean };
  pending: boolean;
}) {
  if (pending) return <StateCard icon={<Loader2 className="size-5 animate-spin" aria-hidden="true" />} text="Organizando os contatos mais úteis..." />;
  if (!data) return <StateCard icon={<Database className="size-5" aria-hidden="true" />} text="Defina os filtros e faça a busca entre os contatos já conhecidos." />;
  if (!data.people.length) return <StateCard icon={<Users className="size-5" aria-hidden="true" />} text="Nenhuma pessoa conhecida corresponde aos filtros atuais." />;

  return (
    <section aria-labelledby="people-results-title" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="people-results-title" className="text-lg font-semibold">{data.total} pessoa{data.total === 1 ? '' : 's'} encontrada{data.total === 1 ? '' : 's'}</h2>
        {data.candidate_scan_truncated ? <Badge variant="outline">Há mais resultados possíveis — refine os filtros</Badge> : null}
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {data.people.map((person) => (
          <article key={person.id} className="rounded-xl border bg-card p-4 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h3 className="truncate font-semibold">{person.name}</h3>
                <p className="text-sm text-muted-foreground">{person.role || 'Cargo não informado'}{person.company.name ? ` · ${person.company.name}` : ''}</p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-semibold tabular-nums">{Math.round(person.actionable_contact.score)}</p>
                <p className="text-xs text-muted-foreground">Qualidade do contato</p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <Badge variant="secondary">{buyerRoleLabel(person.buyer_role)}</Badge>
              <Badge variant="outline">{contactStatusLabel(person.actionable_contact.status)}</Badge>
              {person.email_verified ? <Badge variant="outline"><MailCheck className="size-3" aria-hidden="true" /> E-mail confirmado</Badge> : null}
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-muted-foreground">E-mail</dt><dd className="truncate font-medium">{person.email || 'Não encontrado'}</dd></div>
              <div><dt className="text-muted-foreground">Telefone</dt><dd className="font-medium">{person.phone || 'Não encontrado'}</dd></div>
              <div><dt className="text-muted-foreground">Dados disponíveis para avaliação</dt><dd className="font-medium">{Math.round(person.actionable_contact.coverage * 100)}%</dd></div>
              <div><dt className="text-muted-foreground">Origem</dt><dd className="truncate font-medium">{providerLabel(person.source)}</dd></div>
            </dl>
            {person.actionable_contact.unknown_dimensions.length ? (
              <p className="mt-3 text-xs text-muted-foreground">
                Ainda falta confirmar: {person.actionable_contact.unknown_dimensions.map(contactDimensionLabel).join(', ')}.
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function StateCard({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 text-center text-muted-foreground" role="status">
      {icon}
      <p className="max-w-xl text-sm">{text}</p>
    </div>
  );
}
