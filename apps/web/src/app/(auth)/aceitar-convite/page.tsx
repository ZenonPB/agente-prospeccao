'use client';

import { use, useState } from 'react';
import { signIn, getSession, useSession } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Loader2, CheckCircle2, XCircle, Building2, Lock } from 'lucide-react';
import Link from 'next/link';
import { useAcceptInvite, useCheckInvite, useAcceptRegister } from '@/hooks/use-api';
import { setAccessToken } from '@/lib/api';
import { AuthShell } from '@/components/auth/auth-shell';

export default function AcceptInvitePage(props: { searchParams: Promise<{ token?: string }> }) {
  const searchParams = use(props.searchParams);
  const { data: session, status } = useSession();
  const token = searchParams.token || '';

  const check = useCheckInvite(token);
  const acceptInvite = useAcceptInvite();
  const acceptRegister = useAcceptRegister();

  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState('');
  const [done, setDone] = useState<{ orgName: string; viaRegister: boolean } | null>(null);

  const invite = check.data;

  // Sem token → link inválido.
  if (!token) return invalidCard('Link inválido', 'O link de convite não contém um token válido.');

  // Resolvendo convite.
  if (check.isLoading || status === 'loading') {
    return loadingCard('Verificando convite...');
  }

  if (check.isError) {
    const msg = check.error instanceof Error ? check.error.message : 'Convite inválido';
    return invalidCard('Erro no convite', msg);
  }

  if (!invite) return null;

  // Já aceito.
  if (invite.accepted) {
    return successCard(invite.organization?.name || 'Organização', false);
  }
  if (invite.expired) {
    return invalidCard('Convite expirado', 'Este convite expirou e não pode mais ser aceito.');
  }

  const callbackUrl = encodeURIComponent(`/aceitar-convite?token=${token}`);

  // Usuário autenticado.
  if (session) {
    if ((session.user?.email || '').toLowerCase() !== invite.email.toLowerCase()) {
      return (
        <AuthShell>
          <Card className="w-full border-border/60 shadow-sm">
            <CardHeader className="space-y-2 text-center">
              <XCircle className="mx-auto h-12 w-12 text-destructive" aria-hidden="true" />
              <CardTitle className="font-heading text-2xl font-semibold tracking-tight">E-mail diferente</CardTitle>
              <CardDescription>
                Este convite foi enviado para <strong>{invite.email}</strong>, mas você está logado com{' '}
                <strong>{session.user?.email}</strong>.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-center">
              <Link href={`/api/auth/signout?callbackUrl=${encodeURIComponent('/login')}`}>
                <Button variant="outline" className="h-11 w-full">Trocar de conta</Button>
              </Link>
              <Link href="/dashboard">
                <Button className="h-11 w-full">Ir para o dashboard</Button>
              </Link>
            </CardContent>
          </Card>
        </AuthShell>
      );
    }

    if (acceptInvite.isSuccess || done) {
      return successCard(done?.orgName || invite.organization?.name || 'Organização');
    }
    if (acceptInvite.isError) {
      const msg = acceptInvite.error instanceof Error ? acceptInvite.error.message : 'Erro ao aceitar convite';
      return invalidCard('Erro no convite', msg);
    }

    return (
      <AuthShell>
        <Card className="w-full border-border/60 shadow-sm">
          <CardHeader className="space-y-2 text-center">
            <Building2 className="mx-auto h-12 w-12 text-primary" aria-hidden="true" />
            <CardTitle className="font-heading text-2xl font-semibold tracking-tight">
              Convite para {invite.organization?.name || 'organização'}
            </CardTitle>
            <CardDescription>
              Você está logado como <strong>{session.user?.email}</strong> e foi convidado para esta organização.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-center">
            <Button
              className="h-11 w-full"
              disabled={acceptInvite.isPending}
              onClick={() => acceptInvite.mutate(token)}
            >
              {acceptInvite.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Aceitar convite
            </Button>
            <Link href="/dashboard">
              <Button variant="ghost" className="h-11 w-full">Cancelar</Button>
            </Link>
          </CardContent>
        </Card>
      </AuthShell>
    );
  }

  // Não autenticado.
  if (acceptRegister.isSuccess || done?.viaRegister) {
    return successCard(done?.orgName || invite.organization?.name || 'Organização', true);
  }

  // Já existe conta → pedir login.
  if (invite.has_account) {
    return (
      <AuthShell>
        <Card className="w-full border-border/60 shadow-sm">
          <CardHeader className="space-y-2 text-center">
            <Building2 className="mx-auto h-12 w-12 text-primary" aria-hidden="true" />
            <CardTitle className="font-heading text-2xl font-semibold tracking-tight">Convite para {invite.organization?.name || 'organização'}</CardTitle>
            <CardDescription>
              Você já tem uma conta com este e-mail. Faça login para aceitar o convite.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-center">
            <Link href={`/login?callbackUrl=${callbackUrl}`}>
              <Button className="h-11 w-full">Fazer login</Button>
            </Link>
          </CardContent>
        </Card>
      </AuthShell>
    );
  }

  // Sem conta → cadastro no mesmo fluxo.
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    if (password.length < 8) {
      setFormError('A senha deve ter no mínimo 8 caracteres');
      return;
    }
    try {
      await acceptRegister.mutateAsync({ token, name, password });
      const result = await signIn('credentials', { email: invite.email, password, redirect: false });
      if (result?.error) {
        setFormError('Conta criada, mas erro no login automático.');
        return;
      }
      const sess = await getSession();
      const access = (sess as { accessToken?: string } | null)?.accessToken;
      if (access) setAccessToken(access);
      setDone({ orgName: invite.organization?.name || 'Organização', viaRegister: true });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Erro ao criar conta e aceitar convite.');
    }
  };

  return (
    <AuthShell>
      <Card className="w-full border-border/60 shadow-sm">
        <CardHeader className="space-y-2 text-center">
          <Building2 className="mx-auto h-12 w-12 text-primary" aria-hidden="true" />
          <CardTitle className="font-heading text-2xl font-semibold tracking-tight">
            Entrar em {invite.organization?.name || 'organização'}
          </CardTitle>
          <CardDescription>
            Você foi convidado para {invite.organization?.name || 'uma organização'}. Crie sua conta com o e-mail{' '}
            <strong>{invite.email}</strong> — o convite é aceito na hora.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRegister} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="invite-name">Nome</Label>
              <Input id="invite-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Seu nome" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-email">E-mail</Label>
              <Input id="invite-email" type="email" value={invite.email} disabled />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-password">Senha</Label>
              <Input
                id="invite-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Mínimo 8 caracteres"
                minLength={8}
                required
              />
            </div>
            {formError && <p className="text-sm text-red-500">{formError}</p>}
            <Button type="submit" className="h-11 w-full" disabled={acceptRegister.isPending}>
              {acceptRegister.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Lock className="mr-2 h-4 w-4" />}
              Criar conta e aceitar convite
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Já tem conta?{' '}
            <Link href={`/login?callbackUrl=${callbackUrl}`} className="font-medium text-primary hover:underline">
              Faça login
            </Link>
          </p>
        </CardContent>
      </Card>
    </AuthShell>
  );
}

function loadingCard(text: string) {
  return (
    <AuthShell>
      <Card className="w-full border-border/60 shadow-sm">
        <CardContent className="flex flex-col items-center gap-4 py-12">
          <Loader2 className="h-10 w-10 animate-spin text-primary" aria-hidden="true" />
          <p className="text-sm text-muted-foreground" aria-live="polite">{text}</p>
        </CardContent>
      </Card>
    </AuthShell>
  );
}

function invalidCard(title: string, description: string) {
  return (
    <AuthShell>
      <Card className="w-full border-border/60 shadow-sm">
        <CardHeader className="space-y-2 text-center">
          <XCircle className="mx-auto h-12 w-12 text-destructive" aria-hidden="true" />
          <CardTitle className="font-heading text-2xl font-semibold tracking-tight">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          <Link href="/dashboard">
            <Button variant="outline" className="h-11">Ir para o painel</Button>
          </Link>
        </CardContent>
      </Card>
    </AuthShell>
  );
}

function successCard(orgName: string, viaRegister = false) {
  return (
    <AuthShell>
      <Card className="w-full border-border/60 shadow-sm">
        <CardHeader className="space-y-2 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" aria-hidden="true" />
          <CardTitle className="font-heading text-2xl font-semibold tracking-tight">
            {viaRegister ? 'Conta criada!' : 'Convite aceito!'}
          </CardTitle>
          <CardDescription>
            {viaRegister
              ? `Você criou sua conta e já faz parte de ` 
              : `Você agora é membro de `}
            <strong>{orgName}</strong>.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center">
            <Button className="h-11 w-full" onClick={() => (window.location.href = '/dashboard')}>
            Ir para o painel
          </Button>
        </CardContent>
      </Card>
    </AuthShell>
  );
}