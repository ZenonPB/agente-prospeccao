'use client';

import { useState } from 'react';
import { useSession } from 'next-auth/react';
import { toast } from 'sonner';
import { ShieldAlert, Loader2, CheckCircle2 } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { SalesRoleBadge } from '@/components/sales/sales-role-badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { UserMinus, Crown, LogOut } from 'lucide-react';
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
} from '@/components/ui/alert-dialog';
import { useOrgMembership, useOrgMembers, usePatchMemberSalesRole, useRemoveMember, useTransferOwnership, useLeaveOrganization } from '@/hooks/use-api';
import { InvitesManager } from '@/components/configuracoes/invites-manager';
import { SalesTargetsManager } from '@/components/configuracoes/sales-targets-manager';
import { OrgAuditLog } from '@/components/configuracoes/org-audit-log';
import { PageHeader } from '@/components/ui/page-header';
import type { SalesRole } from '@/types';

const ROLE_LABELS: Record<SalesRole, string> = {
  CONSULTOR: 'Consultor',
  ANALYST: 'Analista',
  MANAGER: 'Gestor',
};

function initials(name?: string) {
  return (
    name
      ?.split(' ')
      .map((n) => n[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || '?'
  );
}

function orgRoleBadge(role?: string) {
  switch (role) {
    case 'OWNER':
      return <Badge variant="default">Dono</Badge>;
    case 'ADMIN':
      return <Badge variant="secondary">Admin</Badge>;
    default:
      return <Badge variant="outline">Membro</Badge>;
  }
}

export default function MembrosPage() {
  const { data: session } = useSession();
  const { data: membership, isLoading: loadingMembership, isError: membershipError } = useOrgMembership();
  const orgId = membership?.organization?.id;

  const { data: membersData, isLoading, isError, error, refetch } = useOrgMembers(orgId);
  const patchRole = usePatchMemberSalesRole();
  const removeMember = useRemoveMember();
  const transferOwnership = useTransferOwnership();
  const leaveOrg = useLeaveOrganization();

  const [pendingId, setPendingId] = useState<string | null>(null);
  const [successId, setSuccessId] = useState<string | null>(null);

  const currentUserId = (session?.user as { id?: string } | undefined)?.id;
  const myRole = membership?.membership?.role;
  const canManage = myRole === 'OWNER' || myRole === 'ADMIN';
  const canSetRole = canManage || membership?.membership?.sales_role === 'MANAGER';

  if (loadingMembership) {
    return <MembersLoading />;
  }

  if (membershipError) {
    return (
      <AccessDenied message="Não foi possível identificar sua organização. Faça login novamente." />
    );
  }

  if (!canSetRole) {
    return (
      <AccessDenied message="Apenas gestores (MANAGER), o dono ou um administrador podem ver a equipe." />
    );
  }

  const members = membersData?.members || [];

  const handleRoleChange = (userId: string, salesRole: SalesRole) => {
    if (!orgId) return;
    setPendingId(userId);
    patchRole.mutate(
      { orgId, userId, salesRole },
      {
        onSuccess: () => {
          toast.success('Papel de venda atualizado.');
          setSuccessId(userId);
          setTimeout(() => setSuccessId((prev) => (prev === userId ? null : prev)), 2000);
        },
        onError: (err) => {
          toast.error(err instanceof Error ? err.message : 'Erro ao atualizar o papel.');
        },
        onSettled: () => setPendingId(null),
      }
    );
  };

  const handleRemoveMember = (userId: string, memberName?: string) => {
    if (!orgId) return;
    removeMember.mutate(
      { orgId, userId },
      {
        onSuccess: () => toast.success(`Membro ${memberName || ''} removido da organização.`),
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao remover membro.'),
      }
    );
  };

  const handleTransferOwnership = (newOwnerUserId: string, memberName?: string) => {
    if (!orgId) return;
    transferOwnership.mutate(
      { orgId, newOwnerUserId },
      {
        onSuccess: () => toast.success(`Propriedade transferida para ${memberName || 'o novo proprietário'}.`),
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao transferir propriedade.'),
      }
    );
  };

  const handleLeaveOrg = () => {
    if (!orgId) return;
    leaveOrg.mutate(
      { orgId },
      {
        onSuccess: () => {
          toast.success('Você saiu da organização.');
          window.location.href = '/dashboard';
        },
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao sair da organização.'),
      }
    );
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader
        eyebrow="Gestão"
        title="Equipe"
        description={
          membership?.organization?.name
            ? `${membership.organization.name} · gerencie quem acessa o quê`
            : 'Gerencie quem acessa o quê nesta organização'
        }
      />

      {canManage && <InvitesManager />}

      {canManage && orgId && <SalesTargetsManager orgId={orgId} members={members} />}

      <Card>
        <CardHeader>
          <CardTitle>Membros</CardTitle>
          <CardDescription>
            Cada papel de venda define o que a pessoa vê e pode fazer. Consulte o significado
            ao passar o mouse sobre os selos.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-center gap-4">
                  <Skeleton className="h-9 w-9 rounded-full" />
                  <div className="flex-1 space-y-1.5">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-48" />
                  </div>
                  <Skeleton className="h-7 w-28" />
                </div>
              ))}
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <ShieldAlert className="h-8 w-8 text-destructive" />
              <p className="text-sm font-medium">Não foi possível carregar os membros</p>
              <p className="text-xs text-muted-foreground">
                {error instanceof Error ? error.message : 'Tente novamente mais tarde'}
              </p>
              <Button variant="outline" className="h-11" size="sm" onClick={() => refetch()}>
                Tentar novamente
              </Button>
            </div>
          ) : (
            <div className="w-full min-w-0 overflow-x-auto">
            <Table className="min-w-[760px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Pessoa</TableHead>
                  <TableHead>Papel na organização</TableHead>
                  <TableHead>Papel de venda</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((member) => {
                  const isMe = member.user_id === currentUserId;
                  const isPending = pendingId === member.user_id;
                  const isSuccess = successId === member.user_id;
                  return (
                    <TableRow key={member.user_id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar>
                            <AvatarFallback>{initials(member.name)}</AvatarFallback>
                          </Avatar>
                          <div>
                            <div className="flex items-center gap-1.5">
                              <span className="font-medium">{member.name || 'Sem nome'}</span>
                              {isMe && (
                                <Badge variant="outline" className="text-[10px] font-normal">
                                  você
                                </Badge>
                              )}
                            </div>
                            <p className="text-xs text-muted-foreground">{member.email}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>{orgRoleBadge(member.role)}</TableCell>
                      <TableCell>
                        {canSetRole ? (
                          <div className="flex items-center gap-2">
                            <Select
                              value={member.sales_role}
                              onValueChange={(value) => handleRoleChange(member.user_id, value as SalesRole)}
                              disabled={isPending}
                            >
                              <SelectTrigger size="sm" className="w-32">
                                <SelectValue>
                                  {(value) => ROLE_LABELS[value as SalesRole] ?? (value as string)}
                                </SelectValue>
                              </SelectTrigger>
                              <SelectContent>
                                {(Object.keys(ROLE_LABELS) as SalesRole[]).map((role) => (
                                  <SelectItem key={role} value={role}>
                                    {ROLE_LABELS[role]}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" aria-hidden="true" /> : null}
                            {!isPending && isSuccess ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" aria-hidden="true" /> : null}
                          </div>
                        ) : (
                          <SalesRoleBadge role={member.sales_role} />
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Transfer Owner Option (OWNER only, target !== me) */}
                          {myRole === 'OWNER' && !isMe && (
                            <AlertDialog>
                              <AlertDialogTrigger render={<Button variant="outline" size="sm" className="h-11 gap-1 text-xs" />}>
                                <Crown className="h-3.5 w-3.5 text-amber-500" />
                                Transferir Dono
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Transferir propriedade da organização?</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    Você está prestes a passar o papel de **Dono** para <strong>{member.name || member.email}</strong>. Seu papel na organização será alterado para **Admin**.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => handleTransferOwnership(member.user_id, member.name)}>
                                    Confirmar transferência
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          )}

                          {/* Remove Member Option (canManage, target !== me, target !== OWNER) */}
                          {canManage && !isMe && member.role !== 'OWNER' && (
                            <AlertDialog>
                              <AlertDialogTrigger render={<Button variant="ghost" size="sm" className="h-11 gap-1 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive" />}>
                                <UserMinus className="h-3.5 w-3.5" />
                                Remover
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Remover {member.name || member.email}?</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    Este membro perderá acesso a esta organização. Todos os leads atualmente atribuídos a ele serão desatribuídos automaticamente para a fila livre.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                                  <AlertDialogAction
                                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                    onClick={() => handleRemoveMember(member.user_id, member.name)}
                                  >
                                    Remover membro
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          )}

                          {/* Leave Org Option (for me if not OWNER) */}
                          {isMe && member.role !== 'OWNER' && (
                            <AlertDialog>
                              <AlertDialogTrigger render={<Button variant="outline" size="sm" className="h-11 gap-1 text-xs text-muted-foreground hover:text-destructive" />}>
                                <LogOut className="h-3.5 w-3.5" />
                                Sair da org
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Sair da organização?</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    Você deixará de ser membro desta organização. Seus leads atribuídos voltarão para a fila livre da equipe.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                                  <AlertDialogAction
                                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                    onClick={handleLeaveOrg}
                                  >
                                    Confirmar saída
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {orgId && <OrgAuditLog orgId={orgId} />}
    </div>
  );
}

function MembersLoading() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-4 w-72" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-9 w-9 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-48" />
                </div>
                <Skeleton className="h-7 w-28" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function AccessDenied({ message }: { message: string }) {
  return (
    <div className="mx-auto max-w-4xl">
      <Card className="border-destructive/20 bg-destructive/5">
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <ShieldAlert className="h-10 w-10 text-destructive" />
          <h2 className="text-lg font-semibold">Acesso restrito</h2>
          <p className="max-w-sm text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    </div>
  );
}
