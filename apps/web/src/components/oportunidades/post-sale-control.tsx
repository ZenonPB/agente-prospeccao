"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, HeartHandshake } from "lucide-react";
import { toast } from "sonner";
import { useRegisterPostSale } from "@/hooks/use-api";

const CHANNELS: { value: "WHATSAPP" | "EMAIL"; label: string }[] = [
  { value: "WHATSAPP", label: "WhatsApp" },
  { value: "EMAIL", label: "E-mail" },
];

export function PostSaleControl({ leadId }: { leadId: string }) {
  const post = useRegisterPostSale();
  const [channel, setChannel] = useState<"WHATSAPP" | "EMAIL">("WHATSAPP");
  const [message, setMessage] = useState("");

  const handle = async () => {
    try {
      await post.mutateAsync({
        id: leadId,
        data: { channel, content: message.trim() || undefined },
      });
      toast.success("Contato pós-venda registrado.");
      setMessage("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao registrar pós-venda.");
    }
  };

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center gap-2">
        <HeartHandshake className="h-4 w-4 text-muted-foreground" />
        <p className="text-sm font-medium">Pós-venda</p>
      </div>
      <p className="text-xs text-muted-foreground">
        Registre o primeiro contato após o fechamento. Se quiser, escreva uma
        mensagem de acompanhamento — ela virará um lembrete agendado.
      </p>
      <div className="space-y-2">
        <Label htmlFor="pos-channel">Canal</Label>
        <Select value={channel} onValueChange={(v) => setChannel((v || "WHATSAPP") as "WHATSAPP" | "EMAIL")}>
          <SelectTrigger id="pos-channel" className="w-full">
            <SelectValue>{CHANNELS.find((c) => c.value === channel)?.label}</SelectValue>
          </SelectTrigger>
          <SelectContent align="start">
            {CHANNELS.map((c) => (
              <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="pos-message">Mensagem de acompanhamento (opcional)</Label>
        <Textarea
          id="pos-message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={3}
          placeholder="Ex.: Olá! Fechamos o projeto — em 14 dias vamos acompanhar sua evolução..."
        />
      </div>
      <Button size="sm" onClick={handle} disabled={post.isPending}>
        {post.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        Registrar contato pós-venda
      </Button>
    </div>
  );
}