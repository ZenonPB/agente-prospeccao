'use client';

import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { History, User, RotateCcw } from 'lucide-react';
import { useCadenceStepVersions } from '@/hooks/use-api';
import type { FollowUpVersion } from '@/types';

interface VersionHistoryDialogProps {
  leadId: string;
  step: string;
  stepLabel: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRestore?: (content: string, subject?: string) => void;
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function VersionCard({
  version,
  isCurrent,
  onRestore,
}: {
  version: FollowUpVersion;
  isCurrent?: boolean;
  onRestore?: (content: string, subject?: string) => void;
}) {
  return (
    <div className="rounded-lg border p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant={isCurrent ? 'default' : 'outline'}>
            v{version.version_number}
          </Badge>
          {isCurrent && <span className="text-xs text-muted-foreground">(atual)</span>}
        </div>
        <span className="text-xs text-muted-foreground">
          {formatDate(version.created_at)}
        </span>
      </div>

      {version.edited_by && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <User className="h-3 w-3" />
          {version.edited_by}
        </div>
      )}

      {version.subject && (
        <div>
          <p className="text-xs font-medium text-muted-foreground">Assunto:</p>
          <p className="text-sm">{version.subject}</p>
        </div>
      )}

      {version.content && (
        <div>
          <p className="text-xs font-medium text-muted-foreground">Conteúdo:</p>
          <p className="text-sm whitespace-pre-wrap line-clamp-4">{version.content}</p>
        </div>
      )}

      {!isCurrent && onRestore && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1 text-xs"
          onClick={() => onRestore(version.content || '', version.subject || undefined)}
        >
          <RotateCcw className="h-3 w-3" />
          Restaurar esta versão
        </Button>
      )}
    </div>
  );
}

export function VersionHistoryDialog({
  leadId,
  step,
  stepLabel,
  open,
  onOpenChange,
  onRestore,
}: VersionHistoryDialogProps) {
  const { data, isLoading } = useCadenceStepVersions(open ? leadId : null, open ? step : null);

  const versions = data?.versions || [];
  const current = data?.current;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History className="h-4 w-4" />
            Histórico de versões — {stepLabel}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-3 pr-2">
          {isLoading ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              Carregando histórico...
            </div>
          ) : versions.length === 0 && !current?.content ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              Nenhuma versão salva ainda.
            </div>
          ) : (
            <>
              {current?.content && (
                <VersionCard
                  version={{
                    id: 'current',
                    version_number: versions.length + 1,
                    subject: current.subject,
                    content: current.content,
                    variant: current.variant,
                    edited_by: null,
                    edit_reason: null,
                    created_at: null,
                  }}
                  isCurrent
                />
              )}
              {versions.map((v) => (
                <VersionCard
                  key={v.id}
                  version={v}
                  onRestore={onRestore}
                />
              ))}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function VersionHistoryButton({
  leadId,
  step,
  stepLabel,
  onRestore,
}: {
  leadId: string;
  step: string;
  stepLabel: string;
  onRestore?: (content: string, subject?: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="h-7 gap-1 text-xs"
        onClick={() => setOpen(true)}
      >
        <History className="h-3 w-3" />
        Histórico
      </Button>
      <VersionHistoryDialog
        leadId={leadId}
        step={step}
        stepLabel={stepLabel}
        open={open}
        onOpenChange={setOpen}
        onRestore={onRestore}
      />
    </>
  );
}
