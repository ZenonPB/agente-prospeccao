'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Search, Filter, ArrowUpDown } from 'lucide-react';
import Link from 'next/link';
import { Lead } from '@/types';

const leads: Lead[] = [
  {
    id: '1',
    company_name: 'Tijuca Restaurante & Bar',
    website: 'https://tijucarestaurante.com.br',
    phone: '(16) 3333-4444',
    category: 'Restaurante',
    city: 'Araraquara',
    state: 'SP',
    country: 'Brasil',
    status: 'QUALIFICADO',
    qualification_score: 88,
    primary_need: 'SECURITY_FIX',
    created_at: '2024-01-15',
    updated_at: '2024-01-15',
  },
  {
    id: '2',
    company_name: 'Restaurante Pau Seco',
    website: 'https://pausseco.com.br',
    phone: '(16) 3222-1111',
    category: 'Restaurante',
    city: 'Araraquara',
    state: 'SP',
    country: 'Brasil',
    status: 'QUALIFICADO',
    qualification_score: 74,
    primary_need: 'MODERN_WEBSITE',
    created_at: '2024-01-15',
    updated_at: '2024-01-15',
  },
  {
    id: '3',
    company_name: 'Clínica Saúde Integral',
    website: 'https://saudeintegral.com.br',
    phone: '(11) 3333-2222',
    category: 'Clínica',
    city: 'São Paulo',
    state: 'SP',
    country: 'Brasil',
    status: 'QUALIFICADO',
    qualification_score: 65,
    primary_need: 'PERFORMANCE',
    created_at: '2024-01-20',
    updated_at: '2024-01-20',
  },
  {
    id: '4',
    company_name: 'Academia Fitness Center',
    website: 'https://fitnesscenter.com.br',
    phone: '(19) 3333-4444',
    category: 'Academia',
    city: 'Campinas',
    state: 'SP',
    country: 'Brasil',
    status: 'ANALISADO',
    qualification_score: 45,
    primary_need: 'SEO',
    created_at: '2024-01-22',
    updated_at: '2024-01-22',
  },
];

const scoreColors = {
  high: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-red-100 text-red-800',
};

const getScoreColor = (score: number) => {
  if (score >= 80) return scoreColors.high;
  if (score >= 60) return scoreColors.medium;
  return scoreColors.low;
};

export function LeadList() {
  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="relative flex-1 md:w-64">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Buscar por nome..." className="pl-9" />
        </div>
        <Select defaultValue="all">
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Campanha" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas as campanhas</SelectItem>
            <SelectItem value="1">Restaurantes Araraquara</SelectItem>
            <SelectItem value="2">Clínicas São Paulo</SelectItem>
          </SelectContent>
        </Select>
        <Select defaultValue="score_desc">
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Ordenar por" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="score_desc">Score (maior primeiro)</SelectItem>
            <SelectItem value="score_asc">Score (menor primeiro)</SelectItem>
            <SelectItem value="date_desc">Data (mais recente)</SelectItem>
            <SelectItem value="date_asc">Data (mais antigo)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Lead Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {leads.map((lead) => (
          <Link key={lead.id} href={`/oportunidades/${lead.id}`}>
            <Card className="transition-colors hover:bg-muted">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-lg">{lead.company_name}</CardTitle>
                    <p className="text-sm text-muted-foreground">{lead.category}</p>
                  </div>
                  <Badge className={getScoreColor(lead.qualification_score)}>
                    {lead.qualification_score}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Necessidade:</span>
                    <Badge variant="outline">{lead.primary_need}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Local:</span>
                    <span>{lead.city}, {lead.state}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Status:</span>
                    <Badge variant={lead.status === 'QUALIFICADO' ? 'default' : 'secondary'}>
                      {lead.status}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}