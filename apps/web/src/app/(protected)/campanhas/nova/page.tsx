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
import {
  OFFER_PROFILE_OPTIONS,
  offerOriginLabel,
  offerProfileDescription,
  offerProfileLabel,
} from '@/lib/offers';
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

const DIGITAL_OFFERS = new Set(['landing_page', 'web_systems_erp']);

function analysisProfileFor(offerKey: string): 'web_presence' | 'business_opportunity' {
  return DIGITAL_OFFERS.has(offerKey) ? 'web_presence' : 'business_opportunity';
}

export default function NovaCampanhaPage() {
  const router = useRouter();
  const createCampaign = useCreateCampaign();
  const updateCampaign = useUpdateCampaign();
  const campaignFromBrief = useCampaignFromBrief();

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

  const selectedOffer = useMemo(
    () => OFFER_PROFILE_OPTIONS.find((item) => item.key === manual.offerKey),
    [manual.offerKey],
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

  const createFromAssistant = async () => {
    if (!briefDraft) return;
    const offerKey = selectedOfferKey || briefDraft.offer_profile_key || undefined;
    if (!briefDraft.target_service.trim() || !briefDraft.target_segment.trim()) {
      setError('Confirme o serviço e o público que você quer alcançar.');
      return;
    }
    setError('');
    try {
      const campaign = await createCampaign.mutateAsync({
        name: briefDraft.name || `${briefDraft.target_service} — ${briefDraft.target_segment}`,
        analysis_profile: briefDraft.analysis_profile,
        target_service: briefDraft.target_service,
        target_segment: briefDraft.target_segment,
        target_city: briefDraft.target_city || undefined,
        target_state: briefDraft.target_state || undefined,
        places_query: briefDraft.places_query || undefined,
        offer_profile_key: offerKey,
      });
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
    try {
      const offer = OFFER_PROFILE_OPTIONS.find((item) => item.key === manual.offerKey);
      const service = offer?.label ?? offerProfileLabel(manual.offerKey);
      const location = manual.city.trim() ? ` — ${manual.city.trim()}${manual.state ? `, ${manual.state}` : ''}` : '';
      const campaign = await createCampaign.mutateAsync({
        name: `${service} — ${manual.segment.trim()}${location}`,
        analysis_profile: analysisProfileFor(manual.offerKey),
        target_service: service,
        target_segment: manual.segment.trim(),
        target_city: manual.city.trim() || undefined,
        target_state: manual.state || undefined,
        offer_profile_key: manual.offerKey,
      });
      router.push(`/campanhas/${campaign.id}?start=true`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível criar a campanha.');
    }
  };

  const busy = createCampaign.isPending || updateCampaign.isPending;
  const suggestedOfferKey = selectedOfferKey ?? briefDraft?.offer_profile_key ?? undefined;

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
          description="Descreva o objetivo como falaria com outra pessoa. O sistema prepara a estratégia de busca e qualificação para você."
        />
      </div>

      <section className="grid gap-3 sm:grid-cols-3" aria-label="Como a prospecção funciona">
        <InfoCard icon={Target} title="Você define o objetivo" text="Diga o serviço e o tipo de cliente que procura." />
        <InfoCard icon={Search} title="O sistema procura sinais reais" text="Empresas, eventos, contexto e pessoas são analisados antes do ranking." />
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
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Estratégia identificada</p>
                      <p className="font-semibold">{offerProfileLabel(suggestedOfferKey)}</p>
                      <p className="max-w-xl text-sm text-muted-foreground">{offerProfileDescription(suggestedOfferKey)}</p>
                      <p className="text-xs text-muted-foreground">{offerOriginLabel(briefDraft.offer_resolved_from)}.</p>
                    </div>
                    <div className="w-full md:w-72">
                      <Label htmlFor="offer">Corrigir, se necessário</Label>
                      <Select value={suggestedOfferKey || ''} onValueChange={(value) => setSelectedOfferKey(value ?? null)}>
                        <SelectTrigger id="offer" className="mt-1.5"><SelectValue placeholder="Escolha o serviço">{(value) => (value ? offerProfileLabel(value as string) : 'Escolha o serviço')}</SelectValue></SelectTrigger>
                        <SelectContent>{OFFER_PROFILE_OPTIONS.map((option) => <SelectItem key={option.key} value={option.key}>{option.label}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>

                <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                  <Button variant="outline" onClick={resetSuggestion} disabled={busy}>Voltar</Button>
                  <Button onClick={() => void createFromAssistant()} disabled={busy}>
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
            <CardDescription>Escolha o serviço e o público. As fontes e os critérios de qualificação continuam automáticos.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="manual-offer">O que você quer vender</Label>
              <Select value={manual.offerKey} onValueChange={(offerKey) => setManual((current) => ({ ...current, offerKey: offerKey ?? '' }))}>
                <SelectTrigger id="manual-offer"><SelectValue>{(value) => offerProfileLabel(value as string)}</SelectValue></SelectTrigger>
                <SelectContent>{OFFER_PROFILE_OPTIONS.map((option) => <SelectItem key={option.key} value={option.key}>{option.label}</SelectItem>)}</SelectContent>
              </Select>
              {selectedOffer ? <p className="text-sm text-muted-foreground">{selectedOffer.description}</p> : null}
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
              <div className="flex gap-2"><MapPin className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" /><p><span className="font-medium">Você não precisa escolher onde procurar.</span> O sistema usa as fontes adequadas para a oferta, cruza evidências e prioriza os melhores candidatos.</p></div>
            </div>

            <Button onClick={() => void createManual()} disabled={busy}>
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
