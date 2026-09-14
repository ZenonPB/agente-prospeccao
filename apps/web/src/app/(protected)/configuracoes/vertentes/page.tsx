'use client';

import { useMemo, useState } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  Eye,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useVertentes } from '@/hooks/use-vertentes';
import type { Vertente, VertenteSignal } from '@/lib/vertentes-api';
import { humanizeCode, signalLabel } from '@/lib/offers';

const VERTICAL_LABELS: Record<string, string> = {
  digital: 'Tecnologia',
  technology: 'Tecnologia',
  mechanical_engineering: 'Engenharia mecânica',
  awards: 'Produtos e eventos',
  awards_sports: 'Produtos e eventos',
  awards_mej: 'Produtos e eventos',
  additive_manufacturing: 'Engenharia e fabricação',
  laser_fabrication: 'Engenharia e fabricação',
  custom_laser_products: 'Produtos personalizados',
};

const PROVIDER_LABELS: Record<string, string> = {
  google_places: 'Google e mapas',
  cnae_discovery: 'Base empresarial e CNAE',
  instagram_search: 'Instagram',
  event_search: 'Eventos futuros',
  job_search: 'Vagas e contratações',
  company_news: 'Notícias empresariais',
  csv_import: 'Base importada',
  pncp_search: 'Compras públicas',
};

const ROLE_LABELS: Record<string, string> = {
  founder: 'Sócio ou fundador',
  president: 'Presidência',
  event_manager: 'Responsável pelo evento',
  commercial_director: 'Diretoria comercial',
  marketing_director: 'Diretoria de marketing',
  marketing_manager: 'Marketing',
  project_manager: 'Gestão de projetos',
  procurement: 'Compras',
  engineering_manager: 'Gestão de engenharia',
  plant_engineer: 'Engenharia da planta',
  maintenance_manager: 'Manutenção',
  operations_director: 'Diretoria de operações',
  safety_manager: 'Segurança do trabalho',
  designer: 'Projetista',
  sports_director: 'Direção esportiva',
  it_manager: 'Tecnologia',
  finance_manager: 'Financeiro',
  product_manager: 'Produto',
};

const CHANNEL_LABELS: Record<string, string> = {
  email: 'E-mail',
  phone: 'Telefone',
  whatsapp: 'WhatsApp',
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
};

function labelVertical(value: string) {
  return VERTICAL_LABELS[value] ?? humanizeCode(value);
}

function labelProvider(value: string) {
  return PROVIDER_LABELS[value] ?? humanizeCode(value);
}

function labelRole(value: string) {
  return ROLE_LABELS[value] ?? humanizeCode(value);
}

function labelChannel(value: string) {
  return CHANNEL_LABELS[value] ?? humanizeCode(value);
}

function SignalList({ title, signals, tone }: { title: string; signals: VertenteSignal[]; tone: 'up' | 'down' }) {
  const Icon = tone === 'up' ? TrendingUp : TrendingDown;
  if (!signals.length) return null;
  return (
    <section className="space-y-2">
      <h4 className="font-semibold">{title}</h4>
      <div className="grid gap-2 md:grid-cols-2">
        {signals.map((signal) => (
          <div key={signal.key} className="rounded-lg border p-3">
            <div className="flex items-start gap-2">
              <Icon className={tone === 'up' ? 'mt-0.5 h-4 w-4 text-emerald-600' : 'mt-0.5 h-4 w-4 text-red-600'} aria-hidden="true" />
              <div className="min-w-0">
                <p className="font-medium">{signalLabel(signal.key) || signal.label}</p>
                <p className="mt-0.5 text-sm text-muted-foreground">{signal.description}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function SimpleView({ vertente }: { vertente: Vertente }) {
  return (
    <div className="space-y-6">
      <section>
        <h4 className="font-semibold">Quem procuramos</h4>
        <div className="mt-2 flex flex-wrap gap-2">
          {vertente.simple.segments.map((item) => <Badge key={item} variant="secondary">{item}</Badge>)}
        </div>
      </section>

      <section>
        <h4 className="font-semibold">Onde encontramos oportunidades</h4>
        <div className="mt-2 flex flex-wrap gap-2">
          {vertente.simple.discovery_sources.map((item) => <Badge key={item} variant="outline">{labelProvider(item)}</Badge>)}
        </div>
      </section>

      <SignalList title="O que aumenta a aderência" signals={vertente.simple.positive_signals} tone="up" />
      <SignalList title="O que reduz a aderência" signals={vertente.simple.negative_signals} tone="down" />

      <section>
        <h4 className="font-semibold">Quem normalmente decide</h4>
        <div className="mt-2 flex flex-wrap gap-2">
          {vertente.simple.decision_makers.map((item) => <Badge key={item} variant="secondary">{labelRole(item)}</Badge>)}
        </div>
      </section>

      <section>
        <h4 className="font-semibold">Canais prioritários</h4>
        <div className="mt-2 flex flex-wrap gap-2">
          {vertente.simple.channels.map((item) => <Badge key={item} variant="outline">{labelChannel(item)}</Badge>)}
        </div>
      </section>

      {vertente.simple.qualification_questions.length > 0 ? (
        <section>
          <h4 className="font-semibold">Perguntas que ajudam a qualificar</h4>
          <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
            {vertente.simple.qualification_questions.map((item) => (
              <li key={item} className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <h4 className="font-semibold">Como a análise funciona</h4>
        <ol className="mt-2 flex flex-wrap items-center gap-1.5 text-sm">
          {vertente.simple.analysis_flow.map((item, index) => (
            <li key={item} className="flex items-center gap-1.5">
              <span className="rounded-full border bg-muted/40 px-3 py-1">{item}</span>
              {index < vertente.simple.analysis_flow.length - 1 ? <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" /> : null}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function AdvancedView({ vertente }: { vertente: Vertente }) {
  const advanced = vertente.advanced;
  const icp = record(advanced.icp);
  const discovery = record(advanced.discovery);
  const prescoring = record(advanced.prescoring);
  const enrichment = record(advanced.enrichment);
  const signals = record(advanced.signals);
  const intent = record(advanced.intent);
  const decisionMakers = record(advanced.decision_makers);
  const qualification = record(advanced.qualification);
  const outreach = record(advanced.outreach);
  const signalWeights = record(signals.weights);
  const prescoreWeights = record(prescoring.weights);

  return (
    <div className="space-y-6">
      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Chave</p><p className="mt-1 font-mono text-sm">{vertente.key}</p></div>
        <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Versão</p><p className="mt-1 font-medium">{vertente.version}</p></div>
        <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Arquétipo</p><p className="mt-1 font-mono text-sm">{vertente.archetype}</p></div>
      </section>

      <section>
        <h4 className="font-semibold">ICP</h4>
        <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Segmentos</dt><dd className="mt-1">{stringList(icp.segments).join(', ') || '—'}</dd></div>
          <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Portes</dt><dd className="mt-1">{stringList(icp.company_sizes).join(', ') || '—'}</dd></div>
          <div className="rounded-lg border p-3"><dt className="text-muted-foreground">CNAEs</dt><dd className="mt-1">{stringList(icp.cnaes).join(', ') || '—'}</dd></div>
          <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Exclusões</dt><dd className="mt-1">{stringList(icp.exclusions).join(', ') || '—'}</dd></div>
        </dl>
      </section>

      <section>
        <h4 className="font-semibold">Discovery</h4>
        <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Fontes</dt><dd className="mt-1">{stringList(discovery.providers).map(labelProvider).join(', ') || '—'}</dd></div>
          <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Candidatos-alvo</dt><dd className="mt-1">{String(discovery.target_candidates ?? '—')}</dd></div>
          <div className="rounded-lg border p-3 sm:col-span-2"><dt className="text-muted-foreground">Estratégia</dt><dd className="mt-1 font-mono text-xs">{String(discovery.query_strategy ?? '—')}</dd></div>
        </dl>
      </section>

      <section>
        <h4 className="font-semibold">Pré-scoring</h4>
        <div className="mt-2 grid gap-3 lg:grid-cols-[220px_1fr]">
          <dl className="space-y-2 text-sm">
            <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Threshold</dt><dd className="mt-1 font-medium">{String(prescoring.threshold ?? '—')}</dd></div>
            <div className="rounded-lg border p-3"><dt className="text-muted-foreground">Top K</dt><dd className="mt-1 font-medium">{String(prescoring.top_k ?? '—')}</dd></div>
          </dl>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[360px] text-sm">
              <thead><tr className="border-b text-left text-muted-foreground"><th className="p-2">Sinal</th><th className="p-2">Peso</th></tr></thead>
              <tbody>{Object.entries(prescoreWeights).map(([key, value]) => <tr key={key} className="border-b last:border-0"><td className="p-2">{signalLabel(key)}</td><td className="p-2 font-mono text-xs">{String(value)}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      </section>

      <section>
        <h4 className="font-semibold">Enriquecimento</h4>
        <div className="mt-2 flex flex-wrap gap-2">{stringList(enrichment.steps).map((item) => <Badge key={item} variant="outline">{humanizeCode(item)}</Badge>)}</div>
      </section>

      <section>
        <h4 className="font-semibold">Scoring</h4>
        <div className="mt-2 overflow-x-auto rounded-lg border">
          <table className="w-full min-w-[420px] text-sm">
            <thead><tr className="border-b text-left text-muted-foreground"><th className="p-2">Sinal</th><th className="p-2">Tipo</th><th className="p-2">Peso</th></tr></thead>
            <tbody>
              {[...stringList(signals.positive), ...stringList(signals.optional_positive)].map((key) => <tr key={`p-${key}`} className="border-b last:border-0"><td className="p-2">{signalLabel(key)}</td><td className="p-2">Positivo</td><td className="p-2 font-mono text-xs">{String(signalWeights[key] ?? '—')}</td></tr>)}
              {[...stringList(signals.negative), ...stringList(signals.disqualifiers)].map((key) => <tr key={`n-${key}`} className="border-b last:border-0"><td className="p-2">{signalLabel(key)}</td><td className="p-2">Negativo</td><td className="p-2 font-mono text-xs">{String(signalWeights[key] ?? '—')}</td></tr>)}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border p-3"><h4 className="font-semibold">Intent e timing</h4><p className="mt-2 text-sm text-muted-foreground">Janela de decaimento: {String(intent.decay_days ?? '—')} dias · gatilho {String(intent.trigger_threshold ?? '—')}</p></div>
        <div className="rounded-lg border p-3"><h4 className="font-semibold">Decisores</h4><p className="mt-2 text-sm text-muted-foreground">{stringList(decisionMakers.priority).map(labelRole).join(', ') || stringList(decisionMakers.roles).map(labelRole).join(', ') || '—'}</p></div>
        <div className="rounded-lg border p-3"><h4 className="font-semibold">Qualificação</h4><p className="mt-2 text-sm text-muted-foreground">{stringList(qualification.questions).length} pergunta(s) · quality gates {Object.keys(record(qualification.quality_gates)).length ? 'configurados' : 'não configurados'}</p></div>
        <div className="rounded-lg border p-3"><h4 className="font-semibold">Abordagem</h4><p className="mt-2 text-sm text-muted-foreground">Ângulo: {humanizeCode(String(outreach.angle ?? ''))}</p></div>
      </section>
    </div>
  );
}

function VertenteDetails({ vertente }: { vertente: Vertente }) {
  return (
    <Tabs defaultValue="simple">
      <TabsList>
        <TabsTrigger value="simple">Visão simples</TabsTrigger>
        <TabsTrigger value="advanced">Visão avançada</TabsTrigger>
      </TabsList>
      <TabsContent value="simple" className="pt-4"><SimpleView vertente={vertente} /></TabsContent>
      <TabsContent value="advanced" className="pt-4"><AdvancedView vertente={vertente} /></TabsContent>
    </Tabs>
  );
}

export default function VertentesPage() {
  const { data, isLoading, isError, refetch } = useVertentes();
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Vertente | null>(null);

  const groups = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('pt-BR');
    const filtered = (data?.items ?? []).filter((item) => {
      if (!query) return true;
      return [item.name, item.tagline, item.vertical, ...item.simple.segments]
        .join(' ')
        .toLocaleLowerCase('pt-BR')
        .includes(query);
    });
    const grouped = new Map<string, Vertente[]>();
    for (const item of filtered) {
      const label = labelVertical(item.vertical);
      grouped.set(label, [...(grouped.get(label) ?? []), item]);
    }
    return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b, 'pt-BR'));
  }, [data, search]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Estratégia comercial"
        title="Vertentes"
        description="Cada vertente reúne, em um só lugar, quem procurar, onde encontrar, quais sinais observar e como qualificar uma oportunidade."
      />

      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="flex gap-3 p-4">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
          <div className="space-y-1 text-sm">
            <p className="font-medium">Uma única estratégia por oferta</p>
            <p className="text-muted-foreground">A vertente que você vê aqui é a mesma configuração efetiva usada pelo pipeline. Vertentes de fábrica são mantidas pelo sistema; versões publicadas pela sua organização aparecem identificadas.</p>
          </div>
        </CardContent>
      </Card>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por vertente, segmento ou serviço..." className="pl-9" />
      </div>

      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">{[1, 2, 3, 4].map((item) => <Skeleton key={item} className="h-40 w-full" />)}</div>
      ) : isError ? (
        <Card><CardContent className="flex flex-col items-center gap-3 py-10 text-center"><p className="text-sm text-muted-foreground">Não foi possível carregar as vertentes.</p><Button variant="outline" onClick={() => void refetch()}>Tentar novamente</Button></CardContent></Card>
      ) : groups.length === 0 ? (
        <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">Nenhuma vertente corresponde à busca.</CardContent></Card>
      ) : (
        <div className="space-y-8">
          {groups.map(([group, items]) => (
            <section key={group} className="space-y-3">
              <div><h2 className="text-lg font-semibold">{group}</h2><p className="text-sm text-muted-foreground">{items.length} {items.length === 1 ? 'vertente disponível' : 'vertentes disponíveis'}</p></div>
              <div className="grid gap-3 lg:grid-cols-2">
                {items.map((item) => (
                  <Card key={item.key} className="overflow-hidden">
                    <CardHeader className="space-y-3 pb-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="space-y-1"><CardTitle className="text-base">{item.name}</CardTitle><p className="text-sm text-muted-foreground">{item.tagline}</p></div>
                        <div className="flex flex-wrap gap-1.5"><Badge variant="outline">v{item.version}</Badge><Badge variant={item.origin === 'factory' ? 'secondary' : 'default'}>{item.origin === 'factory' ? 'De fábrica' : 'Da sua organização'}</Badge></div>
                      </div>
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between text-xs"><span className="text-muted-foreground">Completude da estratégia</span><span className="font-medium">{item.maturity.score}%</span></div>
                        <Progress value={item.maturity.score} aria-label={`Completude de ${item.name}: ${item.maturity.score}%`} />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="flex flex-wrap gap-1.5">{item.simple.segments.slice(0, 4).map((segment) => <Badge key={segment} variant="outline" className="font-normal">{segment}</Badge>)}</div>
                      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                        {item.capabilities.event_discovery ? <span className="rounded-full border px-2 py-1">Eventos</span> : null}
                        {item.capabilities.website_analysis ? <span className="rounded-full border px-2 py-1">Análise de site</span> : null}
                        {item.capabilities.people_discovery ? <span className="rounded-full border px-2 py-1">Decisores</span> : null}
                        {item.capabilities.intent_detection ? <span className="rounded-full border px-2 py-1">Timing e intenção</span> : null}
                      </div>
                      <Button variant="outline" className="w-full" onClick={() => setSelected(item)}><Eye className="mr-2 h-4 w-4" />Ver como funciona</Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      <Dialog open={Boolean(selected)} onOpenChange={(open) => { if (!open) setSelected(null); }}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle className="flex flex-wrap items-center gap-2">{selected?.name}{selected?.origin === 'factory' ? <Badge variant="secondary">De fábrica</Badge> : <Badge>Da sua organização</Badge>}</DialogTitle>
            <DialogDescription>{selected?.tagline}</DialogDescription>
          </DialogHeader>
          {selected ? <VertenteDetails vertente={selected} /> : null}
          {selected?.origin === 'factory' ? (
            <div className="flex items-start gap-2 rounded-lg border border-dashed p-3 text-sm text-muted-foreground"><Sparkles className="mt-0.5 h-4 w-4 shrink-0" /><p>Esta configuração é mantida pelo sistema e não é alterada diretamente. Personalizações aprovadas são versionadas por organização para preservar histórico e rollback.</p></div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
