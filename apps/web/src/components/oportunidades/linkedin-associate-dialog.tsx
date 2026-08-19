'use client';

import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Loader2, Copy, ExternalLink, Search, ShieldCheck } from 'lucide-react';
import { LinkedInIcon } from '@/components/ui/linkedin-icon';
import { toast } from 'sonner';
import { useLinkedinQueries, useAssociateLinkedIn } from '@/hooks/use-api';
import type { ContactItem } from '@/types';

function copyToClipboard(text: string, message: string) {
  navigator.clipboard.writeText(text);
  toast.success(message);
}

interface LinkedInAssociateDialogProps {
  leadId: string;
  companyName: string;
  contact: ContactItem;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function LinkedInAssociateDialog({
  leadId,
  companyName,
  contact,
  open,
  onOpenChange,
}: LinkedInAssociateDialogProps) {
  const { data: queryData, isLoading: loadingQueries } = useLinkedinQueries(open ? leadId : undefined);
  const associate = useAssociateLinkedIn();
  const [url, setUrl] = useState('');

  const queries = queryData?.queries || [];
  const searchUrl = queryData?.search_url || '';

  const onSave = async () => {
    if (!url.trim()) {
      toast.error('Cole a URL do perfil do LinkedIn antes de salvar.');
      return;
    }
    try {
      await associate.mutateAsync({ leadId, contactId: contact.id, url: url.trim() });
      toast.success('Perfil do LinkedIn associado ao decisor.');
      setUrl('');
      onOpenChange(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível associar o perfil.');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <LinkedInIcon className="h-5 w-5 text-primary" />
            Vincular Perfil do LinkedIn ao Contato
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5">
          <div>
            <p className="text-sm font-medium">{contact.name}</p>
            <p className="text-xs text-muted-foreground">
              {contact.role_label || 'Decisor'} · {companyName}
            </p>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <Label htmlFor="linkedin-query" className="text-xs font-medium text-muted-foreground">
                Consultas sugeridas
              </Label>
              {searchUrl && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1 text-[11px]"
                  onClick={() => window.open(searchUrl, '_blank', 'noopener,noreferrer')}
                >
                  <Search className="h-3 w-3" aria-hidden="true" />
                  Buscar no LinkedIn
                  <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </Button>
              )}
            </div>
            {loadingQueries ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : queries.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhuma consulta disponível.</p>
            ) : (
              <div className="space-y-1.5">
                {queries.map((q) => (
                  <div
                    key={q.label}
                    className="flex items-center justify-between gap-2 rounded-lg border bg-muted/40 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="text-xs font-medium">{q.label}</p>
                      <p className="truncate font-mono text-[11px] text-muted-foreground">{q.query}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0"
                      onClick={() => copyToClipboard(q.query, 'Consulta copiada.')}
                      aria-label={`Copiar consulta ${q.label}`}
                    >
                      <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="linkedin-url" className="text-xs font-medium text-muted-foreground">
              Colar o perfil encontrado
            </Label>
            <Input
              id="linkedin-url"
              placeholder="https://www.linkedin.com/in/nome-do-perfil"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onSave();
              }}
            />
            <p className="text-[11px] text-muted-foreground">
              O perfil é validado de forma passiva (sem acessar o LinkedIn). Se confirmado, marca como
              &quot;validado&quot;; senão fica como candidato para revisão.
            </p>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button onClick={onSave} disabled={associate.isPending}>
            {associate.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <ShieldCheck className="mr-2 h-4 w-4" aria-hidden="true" />
            )}
            Validar e salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
