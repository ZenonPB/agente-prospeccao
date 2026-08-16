"use client";

import { useState } from "react";
import { Bookmark, Loader2, Plus, Trash2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCreatePlaybook,
  useDeletePlaybook,
  useOrgMembership,
  usePlaybooks,
} from "@/hooks/use-api";
import { toast } from "sonner";

export function PlaybooksCard() {
  const { data: membership } = useOrgMembership();
  const myUserId = membership?.membership?.user_id;
  const myRole = membership?.membership?.role;
  const canDeleteAny = myRole === "OWNER" || myRole === "ADMIN";

  const list = usePlaybooks({ limit: 50 });
  const create = useCreatePlaybook();
  const remove = useDeletePlaybook();

  const [vertical, setVertical] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");

  const handleSave = async () => {
    if (!subject.trim() || !body.trim()) {
      toast.error("Informe assunto e corpo antes de salvar.");
      return;
    }
    try {
      await create.mutateAsync({
        vertical: vertical.trim() || undefined,
        subject: subject.trim(),
        body,
        tags: [],
      });
      toast.success("Mensagem salva no seu playbook.");
      setSubject("");
      setBody("");
      setVertical("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Falha ao salvar.");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bookmark className="h-5 w-5 text-muted-foreground" />
          Playbooks por consultor
        </CardTitle>
        <CardDescription>
          Salve aqui as mensagens que funcionaram bem. Outros consultores da sua
          organização podem ler; só você ou um admin pode editar/remover.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3 rounded-md border border-dashed p-3">
          <p className="text-sm font-medium">Nova mensagem</p>
          <div className="space-y-2">
            <Label htmlFor="pb-vertical">Vertical / segmento</Label>
            <Input
              id="pb-vertical"
              placeholder="Ex.: academias, restaurantes, escritórios de advocacia"
              value={vertical}
              onChange={(e) => setVertical(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="pb-subject">Assunto</Label>
            <Input
              id="pb-subject"
              placeholder="Assunto que funcionou"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="pb-body">Mensagem</Label>
            <Textarea
              id="pb-body"
              placeholder="Cole aqui a mensagem que teve boa resposta"
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={create.isPending}>
              {create.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              Salvar no meu playbook
            </Button>
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-medium">Mensagens salvas</p>
          {list.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : list.data?.items.length ? (
            <div className="space-y-2">
              {list.data.items.map((p) => {
                const canDelete = canDeleteAny || p.author_id === myUserId;
                return (
                  <div key={p.id} className="rounded-md border p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-xs text-muted-foreground">
                          {p.vertical || "sem vertical"}
                          {" · "}
                          {p.author_name || p.author_email || "anônimo"}
                        </p>
                        <p className="text-sm font-medium">{p.subject}</p>
                      </div>
                      {canDelete && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => remove.mutate(p.id)}
                          disabled={remove.isPending}
                          aria-label="Remover playbook"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                    <p className="mt-1 text-xs whitespace-pre-wrap text-muted-foreground line-clamp-3">
                      {p.body}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Nenhum playbook salvo ainda na organização.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
