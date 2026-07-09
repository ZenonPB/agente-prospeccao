'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import Link from 'next/link';
import { useCampaigns } from '@/hooks/use-api';

export function ActiveCampaigns() {
  const { data, isLoading } = useCampaigns();
  const campaigns = data?.campaigns || [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Buscas em Andamento</CardTitle>
        <Link href="/campanhas" className="text-sm text-primary hover:underline">
          Ver todas →
        </Link>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="text-center text-muted-foreground py-8">Carregando...</div>
        ) : campaigns.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">Nenhuma campanha encontrada</div>
        ) : (
          <div className="space-y-4">
            {campaigns.slice(0, 3).map((campaign) => (
              <Link key={campaign.id} href={`/campanhas/${campaign.id}`}>
                <div className="rounded-lg border p-4 transition-all hover:border-primary hover:bg-muted/50">
                  <div className="mb-3 flex items-start justify-between">
                    <div>
                      <h4 className="font-medium">{campaign.name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {campaign.target_service || campaign.target_segment || 'Geral'} • {campaign.target_city || 'Todas as cidades'}
                      </p>
                    </div>
                    <Badge 
                      variant={campaign.status === 'ACTIVE' ? 'default' : 'secondary'}
                      className={campaign.status === 'ACTIVE' ? 'bg-emerald-100 text-emerald-700' : ''}
                    >
                      {campaign.status === 'ACTIVE' ? 'Em andamento' : campaign.status === 'PAUSED' ? 'Pausada' : campaign.status}
                    </Badge>
                  </div>
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                      {campaign.lead_count || 0} leads encontrados
                    </span>
                    <span className="font-medium">Aptidão: {campaign.avg_score || 0}</span>
                  </div>
                  <Progress 
                    value={campaign.lead_count ? Math.min((campaign.lead_count / 100) * 100, 100) : 0} 
                    className="h-2"
                  />
                </div>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}