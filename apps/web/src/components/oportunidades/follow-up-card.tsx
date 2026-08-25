'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Loader2, Save } from 'lucide-react';
import { useUpdateLead } from '@/hooks/use-api';
import { toast } from 'sonner';
import type { Lead } from '@/types/index';

const primaryNeedLabels: Record<string, string> = {
  SECURITY_FIX: 'Problemas de segurança',
  MODERN_WEBSITE: 'Site desatualizado',
  PERFORMANCE: 'Site lento',
  SEO: 'Problemas de visibilidade',
  LGPD: 'Adequação LGPD',
  NONE: 'Sem necessidade identificada',
};

export function formatPrimaryNeed(value?: string): string {
  if (!value) return 'Sem necessidade identificada';
  return primaryNeedLabels[value] || value;
}

export function FollowUpCard({ lead }: { lead: Lead }) {
  const updateLead = useUpdateLead();
  const [draftNotes, setDraftNotes] = useState(lead.notes ?? '');
  const [draftWhatsapp, setDraftWhatsapp] = useState(lead.whatsapp ?? '');
  const [draftNextAction, setDraftNextAction] = useState(
    lead.next_action_at ? lead.next_action_at.slice(0, 16) : ''
  );
  const [draftValue, setDraftValue] = useState(lead.value ? String(lead.value) : '');
  const [draftExpectedClose, setDraftExpectedClose] = useState(
    lead.expected_close_date ? lead.expected_close_date.slice(0, 10) : ''
  );
  const [draftLostReason, setDraftLostReason] = useState(lead.lost_reason ?? '');

  const saveFollowUp = () => {
    updateLead.mutate(
      {
        id: lead.id,
        data: {
          notes: draftNotes,
          whatsapp: draftWhatsapp || undefined,
          next_action_at: draftNextAction ? new Date(draftNextAction).toISOString() : null,
          value: draftValue ? parseFloat(draftValue) : undefined,
          expected_close_date: draftExpectedClose ? new Date(draftExpectedClose).toISOString() : null,
          lost_reason: draftLostReason || undefined,
        },
      },
      {
        onSuccess: () => toast.success('Acompanhamento salvo.'),
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao salvar acompanhamento.'),
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Acompanhamento & Oportunidade</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label htmlFor="lead-whatsapp" className="text-sm font-medium">
              WhatsApp
            </label>
            <Input
              id="lead-whatsapp"
              placeholder="(16) 99999-9999"
              value={draftWhatsapp}
              onChange={(e) => setDraftWhatsapp(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="lead-next-action" className="text-sm font-medium">
              Próxima ação
            </label>
            <Input
              id="lead-next-action"
              type="datetime-local"
              value={draftNextAction}
              onChange={(e) => setDraftNextAction(e.target.value)}
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label htmlFor="lead-value" className="text-sm font-medium">
              Valor estimado da oportunidade (R$)
            </label>
            <Input
              id="lead-value"
              type="number"
              step="0.01"
              placeholder="Ex: 5000.00"
              value={draftValue}
              onChange={(e) => setDraftValue(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="lead-expected-close" className="text-sm font-medium">
              Previsão de fechamento
            </label>
            <Input
              id="lead-expected-close"
              type="date"
              value={draftExpectedClose}
              onChange={(e) => setDraftExpectedClose(e.target.value)}
            />
          </div>
        </div>

        {lead.status === 'PERDIDO' && (
          <div className="space-y-2">
            <label htmlFor="lead-lost-reason" className="text-sm font-medium">
              Motivo de perda
            </label>
            <select
              id="lead-lost-reason"
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={draftLostReason}
              onChange={(e) => setDraftLostReason(e.target.value)}
            >
              <option value="">Selecione o motivo...</option>
              <option value="PRECO">Preço / Orçamento estourado</option>
              <option value="PRAZO">Prazo de entrega longo</option>
              <option value="NAO_RESPONDEU">Parou de responder / Sumiu</option>
              <option value="CONCORRENTE">Fechou com concorrente</option>
              <option value="OUTRO">Outro motivo</option>
            </select>
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="lead-notes" className="text-sm font-medium">
            Notas
          </label>
          <Textarea
            id="lead-notes"
            rows={3}
            placeholder="Contexto da conversa, objeções, próximos passos..."
            value={draftNotes}
            onChange={(e) => setDraftNotes(e.target.value)}
          />
        </div>
        <div className="flex items-center justify-end">
          <Button size="sm" onClick={saveFollowUp} disabled={updateLead.isPending}>
            {updateLead.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Salvar acompanhamento
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
