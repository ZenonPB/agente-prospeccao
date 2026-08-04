'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ArrowLeft, ArrowRight, Check, Loader2, AlertCircle, Monitor, Cog, Sparkles, MapPin, Wand2, ListOrdered, Send } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useCreateCampaign, useSuggestSegment, useCampaignFromBrief, useUpdateCampaign, type SegmentSuggestion, type CampaignBrief } from '@/hooks/use-api';
import { TemplateSelector } from '@/components/campanhas/template-selector';
import { PageHeader } from '@/components/ui/page-header';

const steps = [
  { id: 1, title: 'Perfil da prospecção' },
  { id: 2, title: 'Para quem?' },
  { id: 3, title: 'Onde?' },
  { id: 4, title: 'Revisão' },
];

const profiles = [
  {
    id: 'web_presence',
    title: 'Serviços digitais',
    description: 'sites, apps, ERPs, landing pages, sistemas',
    icon: Monitor,
  },
  {
    id: 'business_opportunity',
    title: 'Serviços industriais/presenciais',
    description: 'usinagem, manutenção, consultoria, projetos mecânicos',
    icon: Cog,
  },
];

const segmentSuggestions = [
  'Restaurantes',
  'Clínicas',
  'Academias',
  'Indústrias',
  'Lojas varejistas',
  'Escritórios de contabilidade',
  'Farmácias',
];

type Mode = 'wizard' | 'agente';

export default function NovaCampanhaPage() {
  const router = useRouter();
  const createCampaign = useCreateCampaign();
  const suggestSegment = useSuggestSegment();
  const campaignFromBrief = useCampaignFromBrief();
  const updateCampaign = useUpdateCampaign();
  const [mode, setMode] = useState<Mode>('wizard');
  const [currentStep, setCurrentStep] = useState(1);
  const [error, setError] = useState('');
  const [suggestion, setSuggestion] = useState<SegmentSuggestion | null>(null);
  const [excludedSuggestions, setExcludedSuggestions] = useState<string[]>([]);
  const [brief, setBrief] = useState('');
  const [briefResult, setBriefResult] = useState<CampaignBrief | null>(null);
  const [briefDraft, setBriefDraft] = useState<CampaignBrief | null>(null);
  const [formData, setFormData] = useState({
    analysisProfile: 'web_presence',
    segment: '',
    city: '',
    state: '',
  });
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);

  const handleSuggestSegment = async () => {
    setError('');
    try {
      const result = await suggestSegment.mutateAsync({
        profile: formData.analysisProfile as 'web_presence' | 'business_opportunity',
        current_segment: formData.segment || undefined,
        exclude: excludedSuggestions,
      });
      setSuggestion(result);
      // Preenche o input automaticamente e marca o segmento como sugerido
      // para evitar repetição na próxima chamada.
      setFormData((prev) => ({ ...prev, segment: result.segment }));
      setExcludedSuggestions((prev) =>
        result.segment && !prev.includes(result.segment)
          ? [...prev, result.segment]
          : prev,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao gerar sugestão');
    }
  };

  const handleNext = () => {
    setError('');

    if (currentStep === 2 && !formData.segment.trim()) {
      setError('Selecione ou informe o segmento-alvo');
      return;
    }
    if (currentStep === 3 && !formData.city.trim()) {
      setError('Informe a cidade para a busca');
      return;
    }

    if (currentStep < steps.length) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    setError('');
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSubmit = async () => {
    setError('');
    const name = `${formData.segment} em ${formData.city}`;

    try {
      const campaign = await createCampaign.mutateAsync({
        name,
        analysis_profile: formData.analysisProfile as 'web_presence' | 'business_opportunity',
        target_segment: formData.segment || undefined,
        target_city: formData.city || undefined,
        target_state: formData.state || undefined,
      });
      if (selectedTemplateId) {
        await updateCampaign.mutateAsync({
          id: campaign.id,
          data: { scoring_template_id: selectedTemplateId },
        });
      }
      router.push('/campanhas');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar campanha');
    }
  };

  const handleGenerateBrief = async () => {
    setError('');
    if (!brief.trim()) {
      setError('Descreva o que você quer prospectar');
      return;
    }
    try {
      const result = await campaignFromBrief.mutateAsync(brief);
      setBriefResult(result);
      setBriefDraft({ ...result });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao interpretar o brief');
    }
  };

  const handleConfirmBrief = async (startCollection: boolean) => {
    setError('');
    if (!briefDraft) return;
    if (!briefDraft.name.trim() || !briefDraft.target_segment.trim()) {
      setError('Preencha ao menos nome e segmento-alvo');
      return;
    }
    try {
      const campaign = await createCampaign.mutateAsync({
        name: briefDraft.name,
        analysis_profile: briefDraft.analysis_profile,
        target_service: briefDraft.target_service || undefined,
        target_segment: briefDraft.target_segment || undefined,
        target_city: briefDraft.target_city || undefined,
        target_state: briefDraft.target_state || undefined,
        places_query: briefDraft.places_query || undefined,
      });
      if (startCollection) {
        router.push(`/campanhas/${campaign.id}`);
      } else {
        router.push('/campanhas');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar campanha');
    }
  };

  const updateBriefDraft = (patch: Partial<CampaignBrief>) => {
    setBriefDraft((prev) => (prev ? { ...prev, ...patch } : prev));
  };

  const profileLabel =
    formData.analysisProfile === 'web_presence'
      ? 'Serviços digitais'
      : 'Serviços industriais/presenciais';

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/campanhas">
          <Button variant="ghost" size="icon" className="h-9 w-9">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <PageHeader
          eyebrow="Configuração"
          title="Nova Busca de Prospecção"
          description="Crie uma campanha em segundos com o assistente inteligente ou passo a passo"
        />
      </div>

      {/* Mode toggle */}
      <div className="flex items-center gap-2 rounded-lg border bg-card p-1">
        <button
          type="button"
          onClick={() => setMode('agente')}
          className={cn(
            'flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors',
            mode === 'agente' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <Wand2 className="h-4 w-4" />
          Agente (descreva o que quer vender)
        </button>
        <button
          type="button"
          onClick={() => setMode('wizard')}
          className={cn(
            'flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors',
            mode === 'wizard' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <ListOrdered className="h-4 w-4" />
          Wizard (passo a passo)
        </button>
      </div>

      {mode === 'agente' ? (
        <Card>
          <CardHeader>
            <CardTitle>Descreva sua prospecção</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {!briefResult ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="brief">O que você quer prospectar?</Label>
                  <Textarea
                    id="brief"
                    rows={4}
                    placeholder='Ex.: "quero vender landing pages para clínicas de psicologia em Araraquara" ou "projetos de engenharia mecânica para metalúrgicas em São Paulo"'
                    value={brief}
                    onChange={(e) => setBrief(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Escreva em português, do jeito que você falaria: serviço + público + (opcional) cidade.
                  </p>
                </div>
                <Button
                  className="w-full"
                  onClick={handleGenerateBrief}
                  disabled={campaignFromBrief.isPending}
                >
                  {campaignFromBrief.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Interpretando...
                    </>
                  ) : (
                    <>
                      <Sparkles className="mr-2 h-4 w-4" />
                      Gerar campanha
                    </>
                  )}
                </Button>
              </>
            ) : (
              briefDraft && (
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-primary" />
                        <span className="text-xs uppercase tracking-wide text-muted-foreground">
                          Sugestão da IA — revise e edite
                        </span>
                      </div>
                      {briefDraft.rationale && (
                        <p className="text-sm text-muted-foreground">{briefDraft.rationale}</p>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setBriefResult(null);
                        setBriefDraft(null);
                        setBrief('');
                      }}
                    >
                      Recomeçar
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="brief-name">Nome da campanha</Label>
                    <Input
                      id="brief-name"
                      value={briefDraft.name}
                      onChange={(e) => updateBriefDraft({ name: e.target.value })}
                    />
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="brief-service">Serviço que você vende</Label>
                      <Input
                        id="brief-service"
                        value={briefDraft.target_service}
                        onChange={(e) => updateBriefDraft({ target_service: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="brief-segment">Segmento-alvo</Label>
                      <Input
                        id="brief-segment"
                        value={briefDraft.target_segment}
                        onChange={(e) => updateBriefDraft({ target_segment: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="brief-city">Cidade</Label>
                      <Input
                        id="brief-city"
                        value={briefDraft.target_city}
                        onChange={(e) => updateBriefDraft({ target_city: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="brief-state">Estado</Label>
                      <Input
                        id="brief-state"
                        placeholder="UF (ex.: SP)"
                        value={briefDraft.target_state}
                        onChange={(e) => updateBriefDraft({ target_state: e.target.value.toUpperCase() })}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="brief-profile">Perfil da prospecção</Label>
                    <Select
                      value={briefDraft.analysis_profile}
                      onValueChange={(value) =>
                        value && updateBriefDraft({ analysis_profile: value as 'web_presence' | 'business_opportunity' })
                      }
                    >
                      <SelectTrigger id="brief-profile">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="web_presence">Serviços digitais</SelectItem>
                        <SelectItem value="business_opportunity">Serviços industriais/presenciais</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="brief-query">Query do Google Maps (coleta)</Label>
                    <Input
                      id="brief-query"
                      value={briefDraft.places_query}
                      onChange={(e) => updateBriefDraft({ places_query: e.target.value })}
                    />
                    <p className="text-xs text-muted-foreground">
                      Como um cliente pesquisaria no Google Maps para encontrar o segmento.
                    </p>
                  </div>

                  {briefDraft.scoring_template_label && (
                    <div className="flex items-center gap-2 rounded-lg border bg-muted p-3 text-sm">
                      <Badge variant="secondary">Template de critérios</Badge>
                      <span>{briefDraft.scoring_template_label}</span>
                    </div>
                  )}

                  <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
                    <Button
                      variant="outline"
                      onClick={() => handleConfirmBrief(false)}
                      disabled={createCampaign.isPending}
                    >
                      {createCampaign.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Check className="mr-2 h-4 w-4" />
                      )}
                      Criar campanha
                    </Button>
                    <Button
                      onClick={() => handleConfirmBrief(true)}
                      disabled={createCampaign.isPending}
                    >
                      {createCampaign.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="mr-2 h-4 w-4" />
                      )}
                      Criar e iniciar coleta
                    </Button>
                  </div>
                </div>
              )
            )}
          </CardContent>
        </Card>
      ) : (
        <>
      {/* Progress Steps */}
      <div className="flex items-center justify-between">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-center">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full ${
                currentStep > step.id
                  ? 'bg-green-500 text-white'
                  : currentStep === step.id
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              {currentStep > step.id ? (
                <Check className="h-4 w-4" />
              ) : (
                step.id
              )}
            </div>
            {index < steps.length - 1 && (
              <div
                className={`ml-2 h-0.5 w-12 ${
                  currentStep > step.id ? 'bg-green-500' : 'bg-muted'
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step Content */}
      <Card>
        <CardHeader>
          <CardTitle>{steps[currentStep - 1].title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {currentStep === 1 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Escolha o tipo de prospecção que melhor se encaixa no seu serviço:
              </p>
              {profiles.map((profile) => {
                const selected = formData.analysisProfile === profile.id;
                const Icon = profile.icon;
                return (
                  <button
                    key={profile.id}
                    type="button"
                    onClick={() => setFormData({ ...formData, analysisProfile: profile.id })}
                    className={cn(
                      'flex w-full items-center gap-4 rounded-lg border-2 p-4 text-left transition-all hover:shadow-md',
                      selected
                        ? 'border-primary bg-primary/5'
                        : 'border-muted bg-card'
                    )}
                  >
                    <div className={cn(
                      'rounded-lg p-2.5',
                      selected ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                    )}>
                      <Icon className="h-6 w-6" />
                    </div>
                    <div>
                      <p className="font-medium">{profile.title}</p>
                      <p className="text-sm text-muted-foreground">{profile.description}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {currentStep === 2 && (
            <>
              <div className="space-y-2">
                <Label htmlFor="segment">Segmento-alvo *</Label>
                <Input
                  id="segment"
                  placeholder="Ex: Restaurantes, Clínicas, Academias..."
                  value={formData.segment}
                  onChange={(e) =>
                    setFormData({ ...formData, segment: e.target.value })
                  }
                />
                <div className="flex flex-wrap gap-2">
                  {segmentSuggestions.map((suggestion) => (
                    <Button
                      key={suggestion}
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setFormData({ ...formData, segment: suggestion })
                      }
                    >
                      {suggestion}
                    </Button>
                  ))}
                </div>
              </div>

              <Button
                variant="outline"
                className="w-full"
                onClick={handleSuggestSegment}
                disabled={suggestSegment.isPending}
              >
                {suggestSegment.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Gerando sugestão...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    Me sugira segmentos
                  </>
                )}
              </Button>

              {suggestion && (
                <div className="rounded-lg border-2 border-primary/30 bg-primary/5 p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-primary" />
                        <span className="text-xs uppercase tracking-wide text-muted-foreground">
                          Sugestão da IA
                        </span>
                      </div>
                      <p className="text-lg font-semibold">{suggestion.segment}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleSuggestSegment}
                      disabled={suggestSegment.isPending}
                    >
                      {suggestSegment.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        'Gerar outro'
                      )}
                    </Button>
                  </div>
                  <p className="text-sm text-muted-foreground">{suggestion.rationale}</p>
                  {suggestion.hook && (
                    <p className="text-sm italic text-foreground/80">
                      “{suggestion.hook}”
                    </p>
                  )}
                  {suggestion.subniches?.length > 0 && (
                    <div className="space-y-1.5">
                      <p className="text-xs font-medium text-muted-foreground">
                        Subnichos (clique para usar):
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {suggestion.subniches.map((sub) => (
                          <Badge
                            key={sub}
                            variant="secondary"
                            className="cursor-pointer hover:bg-secondary/80 transition-colors"
                            onClick={() =>
                              setFormData({ ...formData, segment: sub })
                            }
                          >
                            {sub}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {suggestion.cities_hint?.length > 0 && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <MapPin className="h-3.5 w-3.5" />
                      <span>Densidade em: {suggestion.cities_hint.join(', ')}</span>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {currentStep === 3 && (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="city">Cidade *</Label>
                <Input
                  id="city"
                  placeholder="Ex: Araraquara"
                  value={formData.city}
                  onChange={(e) =>
                    setFormData({ ...formData, city: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="state">Estado</Label>
                <Select
                  value={formData.state}
                  onValueChange={(value) => value && setFormData({ ...formData, state: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="SP">São Paulo</SelectItem>
                    <SelectItem value="RJ">Rio de Janeiro</SelectItem>
                    <SelectItem value="MG">Minas Gerais</SelectItem>
                    <SelectItem value="PR">Paraná</SelectItem>
                    <SelectItem value="SC">Santa Catarina</SelectItem>
                    <SelectItem value="RS">Rio Grande do Sul</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {currentStep === 4 && (
            <div className="space-y-4">
              <div className="rounded-lg border p-4">
                <h4 className="font-medium">Resumo da Campanha</h4>
                <dl className="mt-2 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Perfil:</dt>
                    <dd className="font-medium">{profileLabel}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Segmento:</dt>
                    <dd className="font-medium">{formData.segment || 'Não informado'}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Localização:</dt>
                    <dd className="font-medium">
                      {formData.city && formData.state
                        ? `${formData.city}, ${formData.state}`
                        : formData.city || 'Não informado'}
                    </dd>
                  </div>
                </dl>
              </div>
                  <div className="rounded-lg bg-muted p-4 text-sm">
                    <p className="font-medium">Estimativa de leads disponíveis</p>
                    <p className="text-muted-foreground">
                      Baseado em buscas similares, estimamos aproximadamente{' '}
                      <span className="font-medium text-foreground">45-60 leads</span>{' '}
                      nesta região para o segmento selecionado.
                    </p>
                  </div>

                  <TemplateSelector
                    value={selectedTemplateId}
                    onChange={(id) => setSelectedTemplateId(id)}
                  />
                </div>
              )}
        </CardContent>
      </Card>

      {/* Navigation Buttons */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={handlePrevious}
          disabled={currentStep === 1}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Anterior
        </Button>
        {currentStep < steps.length ? (
          <Button onClick={handleNext}>
            Próximo
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        ) : (
          <Button onClick={handleSubmit} disabled={createCampaign.isPending}>
            {createCampaign.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Check className="mr-2 h-4 w-4" />
            )}
            Criar Campanha
          </Button>
        )}
      </div>
        </>
      )}
    </div>
  );
}
