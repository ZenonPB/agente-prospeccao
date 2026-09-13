'use client';

import { useState } from 'react';
import { Loader2, ThumbsDown, ThumbsUp } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useLeadUsefulnessFeedback } from '@/hooks/use-api';
import { LEAD_USEFULNESS_REASONS, type LeadUsefulnessReason } from '@/types/lead-usefulness';

interface LeadUsefulnessDialogProps {
  lead: { id?: string; company_name?: string } | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function LeadUsefulnessDialog({ lead, open, onOpenChange }: LeadUsefulnessDialogProps) {
  const [useful, setUseful] = useState<boolean | null>(null);
  const [reason, setReason] = useState<LeadUsefulnessReason | ''>('');
  const [detail, setDetail] = useState('');
  const mutation = useLeadUsefulnessFeedback();

  const submit = () => {
    if (!lead?.id) return;
    if (useful === null) {
      toast.error('Escolha se o lead foi útil ou não');
      return;
    }
    if (!useful && !reason) {
      toast.error('Escolha o motivo para ajudar a melhorar a prospecção');
      return;
    }
    mutation.mutate(
      {
        id: lead.id,
        useful,
        reason: useful ? null : (reason || null),
        detail: detail.trim() ? detail.trim() : null,
      },
      {
        onSuccess: (data) => {
          toast.success(data.useful ? 'Que bom! Feedback registrado.' : 'Feedback registrado. Vamos melhorar a seleção.', {
            description: data.updated ? 'Sua avaliação anterior foi atualizada.' : undefined,
          });
          onOpenChange(false);
        },
        onError: () => toast.error('Não foi possível registrar. Tente de novo.'),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Este lead foi útil?</DialogTitle>
          <DialogDescription>
            {lead?.company_name ?? 'Lead'} — sua avaliação ajuda a trazer empresas melhores.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2" role="group" aria-label="Avaliação do lead">
            <Button
              type="button"
              variant={useful === true ? 'default' : 'outline'}
              onClick={() => setUseful(true)}
              aria-pressed={useful === true}
            >
              <ThumbsUp className="mr-2 h-4 w-4" aria-hidden="true" />
              Útil
            </Button>
            <Button
              type="button"
              variant={useful === false ? 'default' : 'outline'}
              onClick={() => setUseful(false)}
              aria-pressed={useful === false}
            >
              <ThumbsDown className="mr-2 h-4 w-4" aria-hidden="true" />
              Não útil
            </Button>
          </div>

          {useful === false && (
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm text-muted-foreground" htmlFor="usefulness-reason">
                  Por que não foi útil?
                </label>
                <Select value={reason || undefined} onValueChange={(value) => setReason(value as LeadUsefulnessReason)}>
                  <SelectTrigger id="usefulness-reason">
                    <SelectValue placeholder="Escolha o motivo" />
                  </SelectTrigger>
                  <SelectContent>
                    {LEAD_USEFULNESS_REASONS.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-muted-foreground" htmlFor="usefulness-detail">
                  Quer contar mais? (opcional)
                </label>
                <Textarea
                  id="usefulness-detail"
                  rows={3}
                  placeholder="Ex.: empresa fora do nosso porte, já tem fornecedor de troféus..."
                  value={detail}
                  onChange={(e) => setDetail(e.target.value)}
                />
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Enviar avaliação
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
