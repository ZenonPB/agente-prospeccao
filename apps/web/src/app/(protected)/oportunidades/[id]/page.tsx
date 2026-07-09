'use client';

import { use } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, Phone, Mail, MapPin, Calendar, Globe, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useLead } from '@/hooks/use-api';

const severityConfig: Record<string, { label: string; color: string }> = {
  CRITICO: { label: 'Crítico', color: 'bg-red-100 text-red-700' },
  ALTO: { label: 'Alto', color: 'bg-orange-100 text-orange-700' },
  MEDIO: { label: 'Médio', color: 'bg-amber-100 text-amber-700' },
  BAIXO: { label: 'Baixo', color: 'bg-blue-100 text-blue-700' },
};

const primaryNeedLabels: Record<string, string> = {
  SECURITY_FIX: 'Problemas de segurança',
  MODERN_WEBSITE: 'Site desatualizado',
  PERFORMANCE: 'Site lento',
  SEO: 'Problemas de visibilidade',
  NONE: 'Sem problemas',
};

const statusLabels: Record<string, string> = {
  NOVO: 'Novo',
  ANALISADO: 'Analisado',
  QUALIFICADO: 'Apto para contato',
  DESQUALIFICADO: 'Desqualificado',
  CONTATADO: 'Contatado',
  RESPONDIDO: 'Respondeu',
  REUNIAO_MARCADA: 'Reunião marcada',
  PERDIDO: 'Perdido',
};

export default function LeadDetailPage(props: { params: Promise<{ id: string }> }) {
  const params = use(props.params);
  const { data: lead, isLoading } = useLead(params.id);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Lead não encontrado</p>
        <Link href="/oportunidades">
          <Button variant="link" className="mt-4">Voltar para oportunidades</Button>
        </Link>
      </div>
    );
  }

  const enrichment = lead.enrichment;
  const securityIssues = enrichment?.security_issues || [];
  const rawTech = enrichment?.raw_technical_data;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <Link href="/oportunidades">
          <Button variant="ghost" size="icon" className="h-10 w-10 shrink-0">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-2xl font-bold tracking-tight">{lead.company_name}</h2>
            <Badge className="bg-emerald-100 text-emerald-700 text-lg">{lead.qualification_score}</Badge>
          </div>
          <p className="text-muted-foreground">{lead.category || 'Sem categoria'} • {lead.city || 'Não informado'}{lead.state ? `, ${lead.state}` : ''}</p>
        </div>
        <Button className="h-10">
          <Mail className="mr-2 h-4 w-4" />
          Enviar mensagem
        </Button>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="h-10">
          <TabsTrigger value="overview" className="h-9">Dados gerais</TabsTrigger>
          <TabsTrigger value="technical" className="h-9">Análise do site</TabsTrigger>
          <TabsTrigger value="contacts" className="h-9">Contatos</TabsTrigger>
          <TabsTrigger value="actions" className="h-9">Ações</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Informações do Lead</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {lead.website && (
                  <div className="flex items-center gap-3">
                    <Globe className="h-4 w-4 text-muted-foreground" />
                    <a href={lead.website} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                      {lead.website}
                    </a>
                  </div>
                )}
                {lead.phone && (
                  <div className="flex items-center gap-3">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <span>{lead.phone}</span>
                  </div>
                )}
                {lead.email && (
                  <div className="flex items-center gap-3">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <span>{lead.email}</span>
                  </div>
                )}
                <div className="flex items-center gap-3">
                  <MapPin className="h-4 w-4 text-muted-foreground" />
                  <span>{lead.city || 'Não informado'}{lead.state ? `, ${lead.state}` : ''}{lead.country ? `, ${lead.country}` : ''}</span>
                </div>
                <div className="flex items-center gap-3">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span>Encontrado em {new Date(lead.created_at).toLocaleDateString('pt-BR')}</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Aptidão</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Pontuação:</span>
                  <Badge className="bg-emerald-100 text-emerald-700 text-lg">{lead.qualification_score}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Necessidade:</span>
                  <Badge variant="outline">{primaryNeedLabels[lead.primary_need || 'NONE']}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Status:</span>
                  <Badge>{statusLabels[lead.status] || lead.status}</Badge>
                </div>
                {lead.qualification_reason && (
                  <div className="pt-2">
                    <p className="text-sm text-muted-foreground">Por que este lead é uma oportunidade:</p>
                    <p className="text-sm mt-1">{lead.qualification_reason}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="technical" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Análise do Site</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {enrichment ? (
                <>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                      <p className="text-2xl">{enrichment.ssl_ok ? '✅' : '❌'}</p>
                      <p className="text-sm font-medium mt-1">Certificado SSL</p>
                      <p className="text-xs text-muted-foreground">{enrichment.ssl_ok ? 'Configurado' : 'Não configurado'}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl">⚙️</p>
                      <p className="text-sm font-medium mt-1">Tecnologia</p>
                      <p className="text-xs text-muted-foreground">{enrichment.cms || 'Não identificada'}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl">{enrichment.load_time_ms && enrichment.load_time_ms > 3000 ? '🐢' : '⚡'}</p>
                      <p className="text-sm font-medium mt-1">Velocidade</p>
                      <p className="text-xs text-muted-foreground">{enrichment.load_time_ms ? `${(enrichment.load_time_ms / 1000).toFixed(1)}s` : 'Não medido'}</p>
                    </div>
                  </div>
                  {securityIssues.length > 0 && (
                    <div>
                      <h4 className="mb-3 font-medium">Problemas encontrados</h4>
                      <div className="space-y-2">
                        {securityIssues.map((issue: string, index: number) => (
                          <div key={index} className="flex items-start gap-3 rounded-lg border p-3">
                            <div className="text-sm">{issue}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Nenhuma análise técnica disponível</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="contacts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Contatos</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                A busca por contatos de decisores será disponibilizada em breve.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="actions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Próximas Ações</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button className="w-full h-11">
                <Mail className="mr-2 h-4 w-4" />
                Gerar mensagem personalizada
              </Button>
              <Button variant="outline" className="w-full h-11">
                <Phone className="mr-2 h-4 w-4" />
                Registrar contato realizado
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}