'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

interface Campaign {
  id: string;
  name: string;
  segment: string;
  city: string;
  lead_count: number;
  target_leads: number;
  avg_score: number;
  status: 'ACTIVE' | 'PAUSED';
}

const activeCampaigns: Campaign[] = [
  {
    id: '1',
    name: 'Restaurantes Araraquara',
    segment: 'Restaurantes',
    city: 'Araraquara, SP',
    lead_count: 45,
    target_leads: 100,
    avg_score: 72,
    status: 'ACTIVE',
  },
  {
    id: '2',
    name: 'Clínicas São Paulo',
    segment: 'Clínicas',
    city: 'São Paulo, SP',
    lead_count: 23,
    target_leads: 50,
    avg_score: 68,
    status: 'ACTIVE',
  },
  {
    id: '3',
    name: 'Academias Campinas',
    segment: 'Academias',
    city: 'Campinas, SP',
    lead_count: 12,
    target_leads: 30,
    avg_score: 75,
    status: 'PAUSED',
  },
];

export function ActiveCampaigns() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Campanhas Ativas</CardTitle>
        <Link href="/campanhas" className="text-sm text-primary hover:underline">
          Ver todas →
        </Link>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {activeCampaigns.map((campaign) => (
            <Link key={campaign.id} href={`/campanhas/${campaign.id}`}>
              <div className="rounded-lg border p-4 transition-colors hover:bg-muted">
                <div className="mb-2 flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">{campaign.name}</h4>
                    <p className="text-sm text-muted-foreground">
                      {campaign.segment} • {campaign.city}
                    </p>
                  </div>
                  <Badge variant={campaign.status === 'ACTIVE' ? 'default' : 'secondary'}>
                    {campaign.status === 'ACTIVE' ? 'Ativa' : 'Pausada'}
                  </Badge>
                </div>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">
                    {campaign.lead_count}/{campaign.target_leads} leads
                  </span>
                  <span className="font-medium">Score: {campaign.avg_score}</span>
                </div>
                <Progress 
                  value={(campaign.lead_count / campaign.target_leads) * 100} 
                  className="h-2"
                />
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}