'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, ExternalLink, Phone, Mail, MapPin, Calendar } from 'lucide-react';
import Link from 'next/link';

// Mock data - replace with real API call
const lead = {
  id: '1',
  company_name: 'Tijuca Restaurante & Bar',
  website: 'https://tijucarestaurante.com.br',
  phone: '(16) 3333-4444',
  email: 'contato@tijucarestaurante.com.br',
  category: 'Restaurante',
  city: 'Araraquara',
  state: 'SP',
  country: 'Brasil',
  status: 'QUALIFICADO',
  qualification_score: 88,
  primary_need: 'SECURITY_FIX',
  qualification_reason: 'O site apresenta problemas críticos de segurança que precisam ser urgentemente resolvidos. O arquivo .env está exposto publicamente, permitindo acesso a credenciais sensíveis. Além disso, o certificado SSL não está configurado corretamente.',
  created_at: '2024-01-15',
  enrichment: {
    ssl_ok: false,
    https_redirect_ok: false,
    cms: 'WordPress',
    load_time_ms: 3200,
    security_issues: [
      '[CRITICO] .env exposto: Arquivo de configuração com credenciais acessível publicamente',
      '[ALTO] SSL inválido: Certificado não configurado ou expirado',
      '[MEDIO] Headers ausentes: X-Frame-Options, Content-Security-Policy',
    ],
  },
};

export default function LeadDetailPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/oportunidades">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold tracking-tight">{lead.company_name}</h2>
            <Badge className="bg-green-100 text-green-800">{lead.qualification_score}</Badge>
          </div>
          <p className="text-muted-foreground">{lead.category} • {lead.city}, {lead.state}</p>
        </div>
        <Button>
          <Mail className="mr-2 h-4 w-4" />
          Gerar Pitch
        </Button>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Visão Geral</TabsTrigger>
          <TabsTrigger value="technical">Análise Técnica</TabsTrigger>
          <TabsTrigger value="contacts">Contatos</TabsTrigger>
          <TabsTrigger value="actions">Ações</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Informações do Lead</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-2">
                  <ExternalLink className="h-4 w-4 text-muted-foreground" />
                  <a href={lead.website} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    {lead.website}
                  </a>
                </div>
                <div className="flex items-center gap-2">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <span>{lead.phone}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <span>{lead.email}</span>
                </div>
                <div className="flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-muted-foreground" />
                  <span>{lead.city}, {lead.state}, {lead.country}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span>Coletado em {lead.created_at}</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Qualificação</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Score:</span>
                  <Badge className="bg-green-100 text-green-800 text-lg">{lead.qualification_score}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Necessidade:</span>
                  <Badge variant="outline">{lead.primary_need}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Status:</span>
                  <Badge>{lead.status}</Badge>
                </div>
                <div className="pt-2">
                  <p className="text-sm text-muted-foreground">Justificativa:</p>
                  <p className="text-sm">{lead.qualification_reason}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="technical" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Relatório Técnico</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="text-center">
                  <p className="text-2xl font-bold text-red-600">❌</p>
                  <p className="text-sm font-medium">SSL</p>
                  <p className="text-xs text-muted-foreground">{lead.enrichment.ssl_ok ? 'OK' : 'Inválido'}</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-yellow-600">⚠️</p>
                  <p className="text-sm font-medium">CMS</p>
                  <p className="text-xs text-muted-foreground">{lead.enrichment.cms || 'Não detectado'}</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-red-600">🐢</p>
                  <p className="text-sm font-medium">Performance</p>
                  <p className="text-xs text-muted-foreground">{lead.enrichment.load_time_ms}ms</p>
                </div>
              </div>
              <div>
                <h4 className="mb-2 font-medium">Problemas Encontrados</h4>
                <ul className="space-y-2">
                  {lead.enrichment.security_issues.map((issue, index) => (
                    <li key={index} className="text-sm">
                      {issue}
                    </li>
                  ))}
                </ul>
              </div>
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
                Enriquecimento de contatos disponível na Fase 4 (Hunter.io + WHOIS + CNPJ).
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="actions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Ações Disponíveis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button className="w-full">
                <Mail className="mr-2 h-4 w-4" />
                Gerar Pitch com IA
              </Button>
              <Button variant="outline" className="w-full">
                <Phone className="mr-2 h-4 w-4" />
                Registrar Contato
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}