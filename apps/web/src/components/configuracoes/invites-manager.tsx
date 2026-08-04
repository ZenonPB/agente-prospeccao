"use client";

import { useState, useCallback } from "react";
import { useMyOrganization, useInvites, useCreateInvite, useRevokeInvite } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Mail, Trash2, UserPlus, Clock, Check } from "lucide-react";
import { toast } from "sonner";
import type { OrgRole, SalesRole } from "@/types";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function InvitesManager() {
  const { data: orgData } = useMyOrganization();
  const orgId = orgData?.organization?.id;
  const { data: invitesData, isLoading } = useInvites(orgId || "");
  const createInvite = useCreateInvite();
  const revokeInvite = useRevokeInvite();

  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<OrgRole>("MEMBER");
  const [salesRole, setSalesRole] = useState<SalesRole>("CONSULTOR");

  const invites = invitesData?.invites || [];

  const isValidEmail = EMAIL_REGEX.test(email);

  const handleCreateInvite = useCallback(async () => {
    if (!orgId || !email) {
      toast.error("Preencha o e-mail do convidado");
      return;
    }

    if (!isValidEmail) {
      toast.error("Formato de e-mail inválido");
      return;
    }

    try {
      await createInvite.mutateAsync({ orgId, email, role, salesRole });
      toast.success("Convite enviado com sucesso!");
      setOpen(false);
      setEmail("");
      setRole("MEMBER");
      setSalesRole("CONSULTOR");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao enviar convite");
    }
  }, [orgId, email, isValidEmail, role, salesRole, createInvite]);

  const handleRevoke = useCallback(async (inviteId: string) => {
    if (!orgId) return;
    
    try {
      await revokeInvite.mutateAsync({ orgId, inviteId });
      toast.success("Convite revogado");
    } catch {
      toast.error("Erro ao revogar convite");
    }
  }, [orgId, revokeInvite]);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const isExpired = (expiresAt: string) => {
    return new Date(expiresAt) < new Date();
  };

  const canManageInvites = orgData?.membership?.role === "OWNER" || orgData?.membership?.role === "ADMIN";

  if (!canManageInvites) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Convites</CardTitle>
          <CardDescription>
            Apenas proprietários e administradores podem gerenciar convites.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Convites Pendentes</CardTitle>
            <CardDescription>
              Convide membros para sua organização por e-mail
            </CardDescription>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger render={<Button />}>
              <UserPlus className="mr-2 h-4 w-4" aria-hidden="true" />
              Convidar Membro
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Convidar Membro</DialogTitle>
                <DialogDescription>
                  Envie um convite por e-mail para adicionar um novo membro à organização
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="email">E-mail</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="usuario@exemplo.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    aria-invalid={email.length > 0 && !isValidEmail}
                  />
                  {email.length > 0 && !isValidEmail ? (
                    <p className="text-xs text-destructive">Formato de e-mail inválido</p>
                  ) : null}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="role">Papel Administrativo</Label>
                  <Select value={role} onValueChange={(v) => setRole(v as OrgRole)}>
                    <SelectTrigger id="role">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="MEMBER">Membro</SelectItem>
                      <SelectItem value="ADMIN">Administrador</SelectItem>
                      <SelectItem value="OWNER">Proprietário</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sales-role">Papel de Venda</Label>
                  <Select value={salesRole} onValueChange={(v) => setSalesRole(v as SalesRole)}>
                    <SelectTrigger id="sales-role">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="CONSULTOR">Consultor</SelectItem>
                      <SelectItem value="ANALYST">Analista</SelectItem>
                      <SelectItem value="MANAGER">Gerente</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>
                  Cancelar
                </Button>
                <Button
                  onClick={handleCreateInvite}
                  disabled={createInvite.isPending || !isValidEmail}
                >
                  {createInvite.isPending ? "Enviando..." : "Enviar Convite"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando...</p>
        ) : invites.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum convite pendente. Clique em &quot;Convidar Membro&quot; para começar.
          </p>
        ) : (
          <div className="space-y-3">
            {invites.map((invite) => (
              <div
                key={invite.id}
                className="flex items-center justify-between rounded-lg border p-4"
              >
                <div className="flex items-start gap-3">
                  <Mail className="mt-1 h-5 w-5 text-muted-foreground" aria-hidden="true" />
                  <div className="space-y-1">
                    <p className="font-medium">{invite.email}</p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>
                        {invite.role === "OWNER" ? "Proprietário" : invite.role === "ADMIN" ? "Administrador" : "Membro"}
                      </span>
                      <span>·</span>
                      <span>{invite.sales_role}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      {invite.accepted_at ? (
                        <>
                          <Check className="h-3 w-3 text-green-600" aria-hidden="true" />
                          <span className="text-green-600">
                            Aceito em {formatDate(invite.accepted_at)}
                          </span>
                        </>
                      ) : isExpired(invite.expires_at) ? (
                        <>
                          <Clock className="h-3 w-3 text-orange-600" aria-hidden="true" />
                          <span className="text-orange-600">Expirado</span>
                        </>
                      ) : (
                        <>
                          <Clock className="h-3 w-3" aria-hidden="true" />
                          <span className="text-muted-foreground">
                            Expira em {formatDate(invite.expires_at)}
                          </span>
                        </>
                      )}
                    </div>
                    {invite.invited_by_name ? (
                      <p className="text-xs text-muted-foreground">
                        Convidado por {invite.invited_by_name}
                      </p>
                    ) : null}
                  </div>
                </div>
                {!invite.accepted_at && !isExpired(invite.expires_at) ? (
                  <AlertDialog>
                    <AlertDialogTrigger
                      render={
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={revokeInvite.isPending}
                          aria-label={`Revogar convite de ${invite.email}`}
                        />
                      }
                    >
                      <Trash2 className="h-4 w-4 text-destructive" aria-hidden="true" />
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Revogar convite?</AlertDialogTitle>
                        <AlertDialogDescription>
                          O convite para <strong>{invite.email}</strong> será cancelado. Essa ação não pode ser desfeita.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancelar</AlertDialogCancel>
                        <AlertDialogAction onClick={() => handleRevoke(invite.id)}>
                          Revogar
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
