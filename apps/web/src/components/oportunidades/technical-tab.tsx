'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { Enrichment } from '@/types';

interface TechnicalTabProps {
  enrichment?: Enrichment;
}

export function TechnicalTab({ enrichment }: TechnicalTabProps) {
  const securityIssues = enrichment?.security_issues || [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Análise do Site</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {enrichment ? (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
  );
}
