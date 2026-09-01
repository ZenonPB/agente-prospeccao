'use client';

import { useState } from 'react';
import { BrainCircuit, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { useScoreFeedback } from '@/hooks/use-api';

interface ScoreFeedbackDialogProps {
  lead: {
    id?: string;
    company_name?: string;
    qualification_score?: number | null;
  } | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ScoreFeedbackDialog({ lead, open, onOpenChange }: ScoreFeedbackDialogProps) {
  // Formulário inicializado a partir do lead — o diálogo é remontado via `key`
  // no caller, então não precisamos de effect para resetar estado.
  const [score, setScore] = useState(lead?.qualification_score ?? 50);
  const [reason, setReason] = useState('');
  const scoreFeedback = useScoreFeedback();

  const submit = () => {
    if (!lead || !lead.id) return;
    if (lead.qualification_score == null) {
      toast.error('Este lead ainda não possui score da IA');
      return;
    }
    if (reason.trim().length < 5) {
      toast.error('Explique o motivo do ajuste (mínimo 5 caracteres)');
      return;
    }
    scoreFeedback.mutate(
      { id: lead.id, suggested_score: score, reason: reason.trim(), apply_to_lead: true },
      {
        onSuccess: () => {
          toast.success('Feedback registrado — a IA vai usar isso para calibrar', {
            description: `Score do lead corrigido para ${score}.`,
          });
          onOpenChange(false);
        },
        onError: () => toast.error('Erro ao registrar o feedback'),
      },
    );
  };

  const delta = lead?.qualification_score != null ? score - lead.qualification_score : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BrainCircuit className="h-5 w-5 text-primary" />
            Discordar do score
          </DialogTitle>
          <DialogDescription>
            {lead?.company_name} — score da IA:{' '}
            <strong>{lead?.qualification_score ?? '—'}</strong>. Diga qual nota
            você daria e por quê: isso vira regra de calibração para os próximos
            scorings.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Seu score</span>
              <span className="font-semibold">
                {score}
                {delta !== 0 && (
                  <span className={delta < 0 ? 'ml-1 text-red-600' : 'ml-1 text-emerald-600'}>
                    ({delta > 0 ? '+' : ''}{delta})
                  </span>
                )}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={score}
              onChange={(e) => setScore(Number(e.target.value))}
              className="w-full accent-primary"
              aria-label="Score sugerido"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted-foreground" htmlFor="score-feedback-reason">
              Por que o score está errado?
            </label>
            <Textarea
              id="score-feedback-reason"
              rows={3}
              placeholder="Ex.: o site é atualizado, bonito e passa confiança — não é uma dor para redesign; score mais próximo de 40."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={scoreFeedback.isPending}>
            {scoreFeedback.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Registrar feedback
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
