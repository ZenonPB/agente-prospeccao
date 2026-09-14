'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Loader2,
  MapPin,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  Wand2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PageHeader } from '@/components/ui/page-header';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useCampaignFromBrief, useCreateCampaign, useUpdateCampaign, type CampaignBrief } from '@/hooks/use-api';
import { useVertentes } from '@/hooks/use-vertentes';
import { offerOriginLabel, offerProfileLabel } from '@/lib/offers';
import { cn } from '@/lib/utils';

const examples = [
  'Landing pages para clínicas de psicologia em Araraquara',
  'Sistemas web para empresas que ainda dependem de processos manuais e planilhas',
  'Projetos mecânicos para indústrias em expansão no interior de São Paulo',
  'Troféus para campeonatos e corridas nos próximos meses',
  'Troféus para eventos do MEJ e empresas juniores',
];

const brazilianStates = [
  ['AC', 'Acre'], ['AL', 'Alagoas'], ['AP', 'Amapá'], ['AM', 'Amazonas'],
  ['BA', 'Bahia'], ['CE', 'Ceará'], ['DF', 'Distrito Federal'], ['ES', 'Espírito Santo'],
  ['GO', 'Goiás'], ['MA', 'Maranhão'], ['MT', 'Mato Grosso'], ['MS', 'Mato Grosso do Sul'],
  ['MG', 'Minas Gerais'], ['PA', 'Pará'], ['PB', 'Paraíba'], ['PR', 'Paraná'],
  ['PE', 'Pernambuco'], ['PI', 'Piauí'], ['RJ', 'Rio de Janeiro'], ['RN', 'Rio Grande do Norte'],
  ['RS', 'Rio Grande do Sul'], ['RO', 'Rondônia'], ['RR', 'Roraima'], ['SC', 'Santa Catarina'],
  ['SP', 'São Paulo'], ['SE', 'Sergipe'], ['TO', 'Tocantins'],
] as const;

type Mode = 'assistant' | 'manual';

type ManualDraft = {
  offerKey: string;
  segment: string;
  city: string;
  state: string;
};

export default function NovaCampanhaPage() {
  const router = useRouter();
  const createCampaign = useCreateCampaign();
  const updateCampaign = useUpdateCampaign();
  const campaignFromBrief = useCampaignFromBrief();
  const { data: vertentesData, isLoading: loadingVertentes, isError: vertentesError, refetch: refetchVertentes } = useVertentes();

  const [mode, setMode] = useState<Mode>('assistant');
  const [brief, setBrief] = useState('');
  const [briefDraft, setBriefDraft] = useState<CampaignBrief | null>(null);
  const [selectedOfferKey, setSelectedOfferKey] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [manual, setManual] = useState<ManualDraft>({
    offerKey: 'landing_page',
    segment: '',
    city: '',
    state: '',
  });

  const vertentes = useMemo(() => vertentesData?.items ?? [], [vertentesData]);
  const selectedOffer = useMemo(
    () => vertentes.find((item) => item.key === manual.offerKey),
    [manual.offerKey, vertentes],
  );
  const suggestedOfferKey = selectedOfferKey ?? briefDraft?.offer_profile_key ?? undefined;
  const suggestedVertente = useMemo(
    () => vertentes.find((item) => item.key === suggestedOfferKey),
    [suggestedOfferKey, vertentes],
  );

  const resetSuggestion = () => {
    setBriefDraft(null);
    setSelectedOfferKey(null);
    setError('');
  };

  const generateSuggestion = async () => {
    setError('');
    if (!brief.trim()) {
      setError('Conte o que você quer vender e para quem.');
      return;
    }
    try {
      const result = await campaignFromBrief.mutateAsync(brief.trim());
      setBriefDraft({ ...result });
      setSelectedOfferKey(result.offer_profile_key ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível preparar a busca. Tente novamente.');
    }
  };

  const updateBriefDraft = (patch: Partial<CampaignBrief>) => {
    setBriefDraft((current) => (current ? { ...current, ...patch } : current));
  };

  const handleOfferChange = (offerKey: string | null) => {
    setSelectedOfferKey(offerKey);
    if (!offerKey) return;
    const nextVertente = vertentes.find((item) => item.key === offerKey);
    if (!nextVertente) return;

    setBriefDraft((current) => {
      if (!current || current.offer_profile_key === offerKey) return current;
      return {
        ...current,
        offer_profile_key: offerKey,
        offer_profile_label: nextVertente.name,
        offer_resolved_from: 'manual',
        target_service: nextVertente.name,
        // A busca e o scoring sugeridos pertenciam à Vertente anterior. Ao
        // corrigir a estratégia, descartamos esses derivados para que o
        // pipeline os resolva novamente a partir da escolha atual.
        places_query: '',
        scoring_template_id: null,
        scoring_template_label: '',
        template_route: 'VERTENTE_CHANGED',
      };
    });
  };

  const createFromAssistant = async () => {
    if (!briefDraft) return;
    const vertenteKey = selectedOfferKey || briefDraft.offer_profile_key || undefined;
    const vertente = vertentes.find((item) => item.key === vertenteKey);
    if (!vertenteKey || !vertente) {
      setError('Escolha uma vertente disponível para esta organização.');
      return;
    }
    if (!briefDraft.target_service.trim() || !briefDraft.target_segment.trim()) {
      setError('Confirme o serviço e o público que você quer alcançar.');
      return;
    }
    setError('');
    try {
      const campaign = await createCampaign.mutateAsync({
        name: briefDraft.name || `${briefDraft.target_service} — ${briefDraft.target_segment}`,
        analysis_profile: vertente.analysis_profile,
        target_service: briefDraft.target_service,
        target_segment: briefDraft.target_segment,
        target_city: briefDraft.target_city || undefined,
        target_state: briefDraft.target_state || undefined,
        places_query: briefDraft.places_query || undefined,
        offer_profile_key: vertente.key,
      });

      // O preview pode ter criado/resolvido um adapter de scoring específico.
      // Preserve essa decisão em vez de pedir ao pipeline que classifique de
      // novo. Se a Vertente foi corrigida manualmente, handleOfferChange limpa
      // o ID para que o adapter seja recalculado de forma coerente.
      if (briefDraft.scoring_template_id) {
        await updateCampaign.mutateAsync({
          id: campaign.id,
          data: { scoring_template_id: briefDraft.scoring_template_id },
        });
      }

      router.push(`/campanhas/${campaign.id}?start=true`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível criar a campanha.');
    }
  };

  const createManual = async () => {
    setError('');
    if (!manual.offerKey || !manual.segment.trim()) {
      setError('Escolha o que você quer vender e informe o público que deseja alcançar.');
      return;
    }
    const vertente = vertentes.find((item) => item.key === manual.offerKey);
    if (!vertente) {
      setError('A vertente escolhida não está disponível para esta organização.');
      return;
    }
    try {
      const service = vertente.name;
      const location = manual.city.trim() ? ` — ${manual.city.trim()}${manual.state ? `, ${manual.state}` : ''}` : '';
      const campaign = await createCampaign.mutateAsync({
        name: `${service} — ${manual.segment.trim()}${location}`,
        analysis_profile: vertente.analysis_profile,
        target_service: service,
        target_segment: manual.segment.trim(),
        target_city: manual.city.trim() || undefined,
        target_state: manual.state || undefined,
        offer_profile_key: vertente.key,
      });
      router.push(`/campanhas/${campaign.id}?start=true`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível criar a campanha.');
    }
  };

  const busy = createCampaign.isPending || updateCampaign.isPending;

  if (loadingVertentes) {
    return <div className="mx-auto max-w-4xl py-16 text-center text-sm text-muted-foreground">Carregando as vertentes disponíveis...</div>;
  }

  if (vertentesError) {
    return (
      <div className="mx-auto flex max-w-4xl flex-col items-center gap-3 py-16 text-center">
        <p className="text-sm text-muted-foreground">Não foi possível carregar as vertentes desta organização.</p>
        <Button variant="outline" onClick={() => void refetchVertentes()}>Tentar novamente</Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-10">
      <div className="flex items-start gap-3">
        <Link
          href="/campanhas"
          aria-label="Voltar para campanhas"
          className="mt-1 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        </Link>
        <PageHeader
          eyebrow="Nova prospecção"
          title="O que você quer vender?"
          description="Descreva o objetivo como falaria com outra pessoa. O sistema escolhe uma vertente e prepara a busca e a qualificação para você."
        />
      </div>

      <section className="grid gap-3 sm:grid-cols-3" aria-label="Como a prospecção funciona">
        <InfoCard icon={Target} title="Você define o objetivo" text="Diga o serviço e o tipo de cliente que procura." />
        <InfoCard icon={Search} title="A vertente define a estratégia" text="Fontes, sinais, filtros e critérios vêm da mesma configuração comercial." />
        <InfoCard icon={ShieldCheck} title="Só sobe quem tem evidência" text="Falta de informação não vira ponto positivo nem fato inventado." />
      </section>

      <div className="grid grid-cols-2 gap-1 rounded-xl border bg-muted/40 p-1" role="tablist" aria-label="Forma de criar a prospecção">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'assistant'}
          onClick={() => { setMode('assistant'); setError(''); }}
          className={cn(
            'rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            mode === 'assistant' ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Sparkles className="mr-2 inline h-4 w-4" />
          Descrever o que quero
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'manual'}
          onClick={() => { setMode('manual'); setError(''); }}
          className={cn(
            'rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            mode === 'manual' ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          Prefiro preencher
        </button>
      </div>

      {error ? (
        <div className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}

      {mode === 'assistant' ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Wand2 className="h-5 w-5" />Descreva a busca</CardTitle>
            <CardDescription>Não precisa conhecer filtros, fontes de dados ou critérios técnicos. Escreva o objetivo comercial.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {!briefDraft ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="brief">Quero vender...</Label>
                  <Textarea
                    id="brief"
                    rows={5}
                    autoFocus
                    value={brief}
                    onChange={(event) => setBrief(event.target.value)}
                    onKeyDown={(event) => {
                      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') void generateSuggestion();
                    }}
                    placeholder="Ex.: Quero vender troféus para eventos do MEJ que acontecerão nos próximos meses."
                    aria-describedby="brief-help"
                  />
                  <p id="brief-help" className="text-xs text-muted-foreground">Inclua público e localização quando isso for importante. Ctrl/Cmd + Enter para continuar.</p>
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">Exemplos</p>
                  <div className="flex flex-wrap gap-2">
                    {examples.map((example) => (
                      <button
                        key={example}
                        type="button"
                        onClick={() => setBrief(example)}
                        className="rounded-full border px-3 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:bg-primary/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {example}
                      </button>
                    ))}
                  </div>
                </div>

                <Button className="w-full sm:w-auto" onClick={() => void generateSuggestion()} disabled={campaignFromBrief.isPending}>
                  {campaignFromBrief.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                  {campaignFromBrief.isPending ? 'Preparando sua prospecção...' : 'Preparar prospecção'}
                </Button>
              </>
            ) : (
              <div className="space-y-6">
                <div className="rounded-xl border bg-muted/30 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 text-sm font-medium"><CheckCircle2 className="h-4 w-4 text-primary" />Entendi seu objetivo</div>
                      <p className="max-w-2xl text-sm text-muted-foreground">{briefDraft.rationale || 'Revise os dados abaixo. Você continua no controle antes da busca começar.'}</p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={resetSuggestion}>Descrever novamente</Button>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="O que você quer vender" htmlFor="service">
                    <Input id="service" value={briefDraft.target_service} onChange={(event) => updateBriefDraft({ target_service: event.target.value })} />
                  </Field>
                  <Field label="Para quem" htmlFor="segment">
                    <Input id="segment" value={briefDraft.target_segment} onChange={(event) => updateBriefDraft({ target_segment: event.target.value })} />
                  </Field>
                  <Field label="Cidade (opcional)" htmlFor="city">
                    <Input id="city" value={briefDraft.target_city} onChange={(event) => updateBriefDraft({ target_city: event.target.value })} placeholder="Ex.: Araraquara" />
                  </Field>
                  <Field label="Estado (opcional)" htmlFor="state">
                    <Select value={briefDraft.target_state || ''} onValueChange={(value) => updateBriefDraft({ target_state: value ?? '' })}>
                      <SelectTrigger id="state"><SelectValue placeholder="Todo o Brasil">{(value) => (value ? (brazilianStates.find(([uf]) => uf === value)?.[1] ?? (value as string)) : 'Todo o Brasil')}</SelectValue></SelectTrigger>
                      <SelectContent>{brazilianStates.map(([uf, name]) => <SelectItem key={uf} value={uf}>{name}</SelectItem>)}</SelectContent>
                    </Select>
                  </Field>
                </div>

                <div className="rounded-xl border p-4">
                  <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                    <div className="min-w-0 space-y-1">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Vertente recomendada</p>
                      <p className="font-semibold">{suggestedVertente?.name ?? offerProfileLabel(suggestedOfferKey)}</p>
                      <p className="max-w-xl text-sm text-muted-foreground">{suggestedVertente?.tagline || 'Estratégia comercial preparada para esta oferta.'}</p>
                      <p className="text-xs text-muted-foreground">{offerOriginLabel(briefDraft.offer_resolved_from)}.</p>
                    </div>
                    <div className="w-full md:w-72">
                      <Label htmlFor="offer">Corrigir, se necessário</Label>
                      <Select value={suggestedOfferKey || ''} onValueChange={(value) => handleOfferChange(value ?? null)}>
                        <SelectTrigger id="offer" className="mt-1.5"><SelectValue placeholder="Escolha a vertente">{(value) => (value ? (vertentes.find((item) => item.key === value)?.name ?? offerProfileLabel(value as string)) : 'Escolha a vertente')}</SelectValue></SelectTrigger>
                        <SelectContent>{vertentes.map((item) => <SelectItem key={item.key} value={item.key}>{item.name}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>

                <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                  <Button variant="outline" onClick={resetSuggestion} disabled={busy}>Voltar</Button>
                  <Button onClick={() => void createFromAssistant()} disabled={busy || !suggestedVertente}>
                    {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
                    Criar e buscar oportunidades
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Preencher a prospecção</CardTitle>
            <CardDescription>Escolha a Vertente e o público. Fontes, pré-filtros, enriquecimento e critérios de qualificação vêm dela automaticamente.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="manual-offer">Vertente</Label>
              <Select value={manual.offerKey} onValueChange={(offerKey) => setManual((current) => ({ ...current, offerKey: offerKey ?? '' }))}>
                <SelectTrigger id="manual-offer"><SelectValue>{(value) => vertentes.find((item) => item.key === value)?.name ?? offerProfileLabel(value as string)}</SelectValue></SelectTrigger>
                <SelectContent>{vertentes.map((item) => <SelectItem key={item.key} value={item.key}>{item.name}</SelectItem>)}</SelectContent>
              </Select>
              {selectedOffer ? <p className="text-sm text-muted-foreground">{selectedOffer.tagline}</p> : null}
            </div>

            <Field label="Quem você quer encontrar" htmlFor="manual-segment">
              <Input id="manual-segment" value={manual.segment} onChange={(event) => setManual((current) => ({ ...current, segment: event.target.value }))} placeholder="Ex.: clínicas de psicologia, metalúrgicas, EJs..." />
            </Field>

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Cidade (opcional)" htmlFor="manual-city">
                <Input id="manual-city" value={manual.city} onChange={(event) => setManual((current) => ({ ...current, city: event.target.value }))} placeholder="Ex.: Araraquara" />
              </Field>
              <Field label="Estado (opcional)" htmlFor="manual-state">
                <Select value={manual.state} onValueChange={(state) => setManual((current) => ({ ...current, state: state ?? '' }))}>
                  <SelectTrigger id="manual-state"><SelectValue placeholder="Todo o Brasil">{(value) => (value ? (brazilianStates.find(([uf]) => uf === value)?.[1] ?? (value as string)) : 'Todo o Brasil')}</SelectValue></SelectTrigger>
                  <SelectContent>{brazilianStates.map(([uf, name]) => <SelectItem key={uf} value={uf}>{name}</SelectItem>)}</SelectContent>
                </Select>
              </Field>
            </div>

            <div className="rounded-xl bg-muted/40 p-4 text-sm">
              <div className="flex gap-2"><MapPin className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" /><p><span className="font-medium">A Vertente cuida da estratégia.</span> O sistema usa as fontes, sinais e critérios declarados nela e mantém a campanha vinculada a essa Vertente efetiva.</p></div>
            </div>

            <Button onClick={() => void createManual()} disabled={busy || !selectedOffer}>
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
              Criar e buscar oportunidades
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function InfoCard({ icon: Icon, title, text }: { icon: typeof Target; title: string; text: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
      <p className="mt-3 text-sm font-medium">{title}</p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{text}</p>
    </div>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label htmlFor={htmlFor}>{label}</Label>{children}</div>;
}
