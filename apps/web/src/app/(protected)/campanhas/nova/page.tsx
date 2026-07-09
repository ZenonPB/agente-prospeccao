'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ArrowLeft, ArrowRight, Check, Loader2, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { useCreateCampaign } from '@/hooks/use-api';

const steps = [
  { id: 1, title: 'O que você quer vender?' },
  { id: 2, title: 'Para quem?' },
  { id: 3, title: 'Onde?' },
  { id: 4, title: 'Revisão' },
];

const serviceSuggestions = [
  'Landing page',
  'ERP',
  'App mobile',
  'Sistema de gestão',
  'Projeto de usinagem',
  'Consultoria em TI',
  'Desenvolvimento web',
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

export default function NovaCampanhaPage() {
  const router = useRouter();
  const createCampaign = useCreateCampaign();
  const [currentStep, setCurrentStep] = useState(1);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    service: '',
    serviceDescription: '',
    segment: '',
    city: '',
    state: '',
    radius: '10',
  });

  const handleNext = () => {
    setError('');

    if (currentStep === 1 && !formData.service.trim()) {
      setError('Informe o serviço que você quer vender');
      return;
    }
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
    const query = `${formData.segment} em ${formData.city}, ${formData.state}`;

    try {
      await createCampaign.mutateAsync({
        name,
        target_service: formData.service || undefined,
        target_segment: formData.segment || undefined,
        target_city: formData.city || undefined,
        target_state: formData.state || undefined,
      });
      router.push('/campanhas');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar campanha');
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/campanhas">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Nova Campanha</h2>
          <p className="text-muted-foreground">
            Crie uma nova campanha de prospecção
          </p>
        </div>
      </div>

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
            <>
              <div className="space-y-2">
                <Label htmlFor="service">Serviço-alvo *</Label>
                <Input
                  id="service"
                  placeholder="Ex: Landing page, ERP, App mobile..."
                  value={formData.service}
                  onChange={(e) =>
                    setFormData({ ...formData, service: e.target.value })
                  }
                />
                <div className="flex flex-wrap gap-2">
                  {serviceSuggestions.map((suggestion) => (
                    <Button
                      key={suggestion}
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setFormData({ ...formData, service: suggestion })
                      }
                    >
                      {suggestion}
                    </Button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Descrição do serviço</Label>
                <Textarea
                  id="description"
                  placeholder="Descreva o serviço para a IA entender o contexto..."
                  value={formData.serviceDescription}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      serviceDescription: e.target.value,
                    })
                  }
                />
              </div>
            </>
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
              <Button variant="outline" className="w-full" disabled>
                🤖 Me sugira segmentos
              </Button>
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
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="radius">Raio de busca</Label>
                <Select
                  value={formData.radius}
                  onValueChange={(value) => value && setFormData({ ...formData, radius: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="5">5 km</SelectItem>
                    <SelectItem value="10">10 km</SelectItem>
                    <SelectItem value="25">25 km</SelectItem>
                    <SelectItem value="50">50 km</SelectItem>
                    <SelectItem value="100">100 km</SelectItem>
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
                    <dt className="text-muted-foreground">Serviço:</dt>
                    <dd className="font-medium">{formData.service || 'Não informado'}</dd>
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
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Raio:</dt>
                    <dd className="font-medium">{formData.radius} km</dd>
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
    </div>
  );
}
