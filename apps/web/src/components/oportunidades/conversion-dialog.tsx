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
import { toast } from 'sonner';

interface ConversionDialogProps {
  leadId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ConversionDialog({ leadId, open, onOpenChange }: ConversionDialogProps) {
  const registerConversion = useRegisterConversion();
  const [service, setService] = useState('');
  const [value, setValue] = useState('');
  const [notes, setNotes] = useState('');

  const handleRegister = async () => {
    try {
      const numeric = value.replace(',', '.');
      await registerConversion.mutateAsync({
        id: leadId,
        data: {
          service_sold: service || undefined,
          contract_value: numeric ? Number(numeric) : undefined,
          notes: notes || undefined,
        },
      });
      toast.success('Conversão registrada.');
      onOpenChange(false);
      setService('');
      setValue('');
      setNotes('');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Erro ao registrar conversão.');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[calc(100%-2rem)] sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Registrar conversão</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
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
