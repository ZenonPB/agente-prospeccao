'use client';

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Loader2, MessageCircle, Sparkles } from 'lucide-react';
import { whatsAppLink } from '@/lib/utils';
import { toast } from 'sonner';
import { useRecordWhatsAppClick } from '@/hooks/use-api';
import type { Lead, OutreachMessages } from '@/types/index';

type CadenceStep = 'OPENING' | 'FOLLOWUP_1' | 'FOLLOWUP_2' | 'CLOSING';

interface OutreachMessagesModalProps {
  lead: Lead;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  messages: OutreachMessages | null;
  isGenerating: boolean;
  onRegenerateVariants: () => void;
  onApplyVariant: (step: CadenceStep, variant: OutreachMessages) => void;
  onSaveToPlaybook: (subject: string, body: string) => void;
}

export function OutreachMessagesModal({
  lead,
  open,
  onOpenChange,
  messages,
  isGenerating,
  onRegenerateVariants,
  onApplyVariant,
  onSaveToPlaybook,
}: OutreachMessagesModalProps) {
  const copyToClipboard = (text: string, message: string) => {
    navigator.clipboard.writeText(text);
    toast.success(message);
  };
  const whatsAppUrl = messages
    ? whatsAppLink(lead.whatsapp || lead.phone, messages.whatsapp_short)
    : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px]">
        <DialogHeader>
          <DialogTitle>Mensagem gerada para {lead.company_name}</DialogTitle>
        </DialogHeader>
        {isGenerating ? (
          <div className="flex flex-col items-center justify-center py-12 space-y-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">
              Gerando sequência personalizada de outreach com IA...
            </p>
          </div>
        ) : messages ? (
          <>
            {messages.variants && messages.variants.length >= 2 && (
              <div className="mb-4 rounded-md border border-dashed border-primary/30 bg-primary/5 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">Variantes A/B geradas</p>
                    <p className="text-xs text-muted-foreground">
                      Escolha uma variante para abrir/finalizar a cadência. A versão escolhida fica registrada
                      como variante e aparece nas métricas de resposta.
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={onRegenerateVariants}
                    disabled={isGenerating}
                  >
                    {isGenerating ? (
                      <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                    ) : null}
                    Regerar
                  </Button>
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {messages.variants.map((variant) => (
                    <div
                      key={variant.label}
                      className="rounded-md border bg-background p-3 space-y-2"
                    >
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Variante {variant.label}
                      </p>
                      <p className="text-xs font-medium">Assunto: {variant.subject}</p>
                      <p className="text-xs text-muted-foreground line-clamp-3">{variant.rationale}</p>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={isGenerating}
                        onClick={() => onApplyVariant('OPENING', variant)}
                      >
                        Usar abertura
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {!messages.variants && (
              <div className="mb-4 flex justify-end">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onRegenerateVariants}
                  disabled={isGenerating}
                >
                  {isGenerating ? (
                    <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                  ) : null}
                  Gerar variantes A/B
                </Button>
              </div>
            )}
            <Tabs defaultValue="email" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="email">E-mail</TabsTrigger>
                <TabsTrigger value="followups">Follow-ups</TabsTrigger>
                <TabsTrigger value="whatsapp">WhatsApp</TabsTrigger>
              </TabsList>
              <TabsContent value="email" className="space-y-4 pt-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Assunto:</p>
                  <div className="flex items-center space-x-2">
                    <Input value={messages.subject} readOnly />
                    <Button variant="outline" size="sm" onClick={() => copyToClipboard(messages.subject, 'Assunto copiado!')}>
                      Copiar
                    </Button>
                  </div>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Corpo da mensagem:</p>
                  <div className="flex items-center space-x-2">
                    <Textarea value={messages.body_opening} readOnly rows={8} />
                    <div className="flex flex-col gap-1">
                      <Button variant="outline" size="sm" onClick={() => copyToClipboard(messages.body_opening, 'Corpo do e-mail copiado!')}>
                        Copiar
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onSaveToPlaybook(messages.subject, messages.body_opening)}
                      >
                        Salvar no playbook
                      </Button>
                    </div>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">Gerado com base nas evidências reais do lead</p>
              </TabsContent>
              <TabsContent value="followups" className="space-y-4 pt-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Follow-up 1 — Dia 3:</p>
                  <Textarea value={messages.followup_1} readOnly rows={5} />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Follow-up 2 — Dia 7:</p>
                  <Textarea value={messages.followup_2} readOnly rows={5} />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Encerramento — Dia 14:</p>
                  <Textarea value={messages.closing} readOnly rows={3} />
                </div>
              </TabsContent>
              <TabsContent value="whatsapp" className="space-y-4 pt-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Mensagem para WhatsApp:</p>
                  <Textarea value={messages.whatsapp_short} readOnly rows={6} />
                  <Badge className="mt-2">Versão curta para WhatsApp Business</Badge>
                </div>
                {whatsAppUrl ? (
                  <WhatsAppSendButton
                    leadId={lead.id}
                    messageText={messages.whatsapp_short}
                    fallbackUrl={whatsAppUrl}
                  />
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Adicione um WhatsApp no lead (aba Dados gerais) para abrir a conversa direto.
                  </p>
                )}
              </TabsContent>
            </Tabs>
          </>
        ) : (
          <div className="text-center py-6">
            <p className="text-sm text-muted-foreground mb-4">Nenhuma mensagem gerada ainda.</p>
            <Button disabled>
              <Sparkles className="mr-2 h-4 w-4" />
              Gerar Mensagem com IA
            </Button>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Fechar</Button>
          <Button
            onClick={() =>
              copyToClipboard(
                `${messages?.subject}\n\n${messages?.body_opening}`,
                'E-mail completo copiado!'
              )
            }
            disabled={!messages}
          >
            Copiar e-mail completo
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function WhatsAppSendButton({
  leadId,
  messageText,
  fallbackUrl,
}: {
  leadId: string;
  messageText: string;
  fallbackUrl: string;
}) {
  const recordWhatsApp = useRecordWhatsAppClick();
  return (
    <Button
      className="h-10 w-full gap-2 bg-emerald-600 font-medium text-white shadow-sm hover:bg-emerald-700"
      disabled={recordWhatsApp.isPending}
      onClick={() => {
        recordWhatsApp.mutate(
          { leadId, messageText },
          {
            onSuccess: (res) => {
              if (res.whatsapp_url) {
                window.open(res.whatsapp_url, '_blank');
                toast.success('WhatsApp acionado com mensagem!');
              }
            },
            onError: () => {
              window.open(fallbackUrl, '_blank');
            },
          }
        );
      }}
    >
      {recordWhatsApp.isPending ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <MessageCircle className="h-4 w-4" />
      )}
      Abrir no WhatsApp
    </Button>
  );
}
