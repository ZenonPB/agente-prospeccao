'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Loader2, Trophy } from 'lucide-react';
import { useRegisterConversion } from '@/hooks/use-api';
import { offerProfileLabel } from '@/lib/offers';
import { toast } from 'sonner';
import type { LeadOpportunity } from '@/types';

interface ConversionDialogProps {
  leadId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  opportunities: LeadOpportunity[];
}

function melhorOferta(opportunities: LeadOpportunity[]): LeadOpportunity | null {
  if (opportunities.length === 0) return null;
  return opportunities.reduce((melhor, atual) => (atual.score > melhor.score ? atual : melhor));
}

export function ConversionDialog({ leadId, open, onOpenChange, opportunities }: ConversionDialogProps) {
  const registerConversion = useRegisterConversion();
  const [service, setService] = useState('');
  const [manualKey, setManualKey] = useState<string | null>(null);
  const [value, setValue] = useState('');
  const [notes, setNotes] = useState('');

  // Oferta com maior aderência, derivada na renderização; o vendedor pode trocar.
  const melhor = melhorOferta(opportunities);
  const offerKey = manualKey ?? melhor?.offer_key ?? 'unknown';
  const opportunityId = opportunities.find((item) => item.offer_key === offerKey)?.id ?? '';

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) setManualKey(null);
    onOpenChange(nextOpen);
  };

  const handleRegister = async () => {
    if (registerConversion.isPending) return;
    const texto = value.trim();
    // Aceita "1234,56" e "1.234,56" além do formato do campo numérico ("1234.56").
    const normalizado = texto.includes(',') && texto.includes('.')
      ? texto.replace(/\./g, '').replace(',', '.')
      : texto.replace(',', '.');
    let contractValue: number | undefined;
    if (normalizado) {
      const numero = Number(normalizado);
      if (!Number.isFinite(numero) || numero < 0) {
        toast.error('Informe um valor de contrato válido (número maior ou igual a zero).');
        return;
      }
      contractValue = numero;
    }
    try {
      await registerConversion.mutateAsync({
        id: leadId,
        data: {
          offer_key: offerKey,
          lead_opportunity_id: opportunityId || undefined,
          service_sold: service || undefined,
          contract_value: contractValue,
          notes: notes || undefined,
        },
      });
      toast.success('Conversão registrada.');
      onOpenChange(false);
      setService('');
      setManualKey(null);
      setValue('');
      setNotes('');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Erro ao registrar conversão.');
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="w-[calc(100%-2rem)] sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Registrar conversão</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="convOffer" className="text-sm font-medium">
              Oferta relacionada
            </label>
            <select
              id="convOffer"
              value={offerKey}
              onChange={(event) => setManualKey(event.target.value)}
              className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            >
              <option value="unknown">Não identificada (revisar depois)</option>
              {opportunities.map((opportunity) => (
                <option key={opportunity.id} value={opportunity.offer_key}>
                  {offerProfileLabel(opportunity.offer_key)} · {opportunity.score} pontos
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Já deixamos marcada a oferta com maior aderência — troque se a venda foi outra.
            </p>
          </div>
          <div className="space-y-2">
            <label htmlFor="convService" className="text-sm font-medium">
              Serviço vendido
            </label>
            <Input
              id="convService"
              value={service}
              onChange={(e) => setService(e.target.value)}
              placeholder="Ex.: Landing page, site institucional..."
              className="min-w-0"
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="convValue" className="text-sm font-medium">
              Valor do contrato (R$)
            </label>
            <Input
              id="convValue"
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="0,00"
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="convNotes" className="text-sm font-medium">
              Observações
            </label>
            <Textarea
              id="convNotes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Como fechou? Contexto do negócio..."
              rows={3}
            />
          </div>
        </div>
        <DialogFooter className="flex-col-reverse gap-2 sm:flex-row">
          <Button className="h-11" variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button className="h-11" onClick={handleRegister} disabled={registerConversion.isPending}>
            {registerConversion.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Trophy className="mr-2 h-4 w-4" />
            )}
            Registrar conversão
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
