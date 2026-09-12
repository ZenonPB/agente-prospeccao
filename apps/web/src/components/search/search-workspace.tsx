'use client';

import { useState } from 'react';
import { Building2, Loader2, Sparkles, Users } from 'lucide-react';
import { toast } from 'sonner';

import { CompanySearchPanel } from '@/components/search/company-search-panel';
import { PeopleSearchPanel } from '@/components/search/people-search-panel';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useInterpretSearch } from '@/hooks/use-search';
import type { SearchIntent, SearchTarget } from '@/lib/search-api';

export function SearchWorkspace() {
  const [tab, setTab] = useState<SearchTarget>('companies');
  const [naturalQuery, setNaturalQuery] = useState('');
  const [intent, setIntent] = useState<SearchIntent | null>(null);
  const interpret = useInterpretSearch();

  async function handleInterpret() {
    if (naturalQuery.trim().length < 3) return;
    try {
      const parsed = await interpret.mutateAsync({ query: naturalQuery, target: 'auto' });
      setIntent(parsed);
      setTab(parsed.target);
      toast.success('Filtros preparados. Revise as opções antes de fazer a busca.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível preparar os filtros.');
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
            Escreva o perfil desejado em linguagem comum. O sistema prepara os filtros, mas só faz a busca depois que você revisar e confirmar.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Label htmlFor="natural-search" className="sr-only">Descrição do perfil desejado</Label>
            <Input
              id="natural-search"
              value={naturalQuery}
              onChange={(event) => setNaturalQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !interpret.isPending) void handleInterpret();
              }}
              placeholder="Ex.: diretores de eventos de empresas juniores em São Paulo com e-mail confirmado"
              className="h-11 flex-1"
              maxLength={500}
            />
            <Button className="h-11 shrink-0" onClick={() => void handleInterpret()} disabled={interpret.isPending || naturalQuery.trim().length < 3}>
              {interpret.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Sparkles className="size-4" aria-hidden="true" />}
              {interpret.isPending ? 'Preparando...' : 'Preparar filtros'}
            </Button>
          </div>

          {intent ? (
            <div className="mt-4 rounded-lg border bg-background/70 p-4" role="status" aria-live="polite">
              <p className="text-sm font-medium">{intent.summary}</p>
              {(intent.assumptions.length > 0 || intent.unresolved.length > 0) ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {intent.assumptions.map((item) => <Badge key={`assumption-${item}`} variant="secondary">Considerado: {item}</Badge>)}
                  {intent.unresolved.map((item) => <Badge key={`unresolved-${item}`} variant="outline">Vale confirmar: {item}</Badge>)}
                </div>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Tabs value={tab} onValueChange={(value) => setTab(value as SearchTarget)}>
        <TabsList className="mx-0">
          <TabsTrigger value="companies"><Building2 aria-hidden="true" /> Empresas</TabsTrigger>
          <TabsTrigger value="people"><Users aria-hidden="true" /> Pessoas</TabsTrigger>
        </TabsList>
        <TabsContent value="companies" className="pt-3">
          <CompanySearchPanel interpretedFilters={intent?.target === 'companies' ? intent.company_filters : null} />
        </TabsContent>
        <TabsContent value="people" className="pt-3">
          <PeopleSearchPanel interpretedFilters={intent?.target === 'people' ? intent.people_filters : null} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
