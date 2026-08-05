'use client';

import { use, useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Loader2, CheckCircle2, XCircle, Building2 } from 'lucide-react';
import Link from 'next/link';
import { useAcceptInvite } from '@/hooks/use-api';
import { AuthShell } from '@/components/auth/auth-shell';

export default function AcceptInvitePage(props: { searchParams: Promise<{ token?: string }> }) {
  const searchParams = use(props.searchParams);
  const router = useRouter();
  const { data: session, status } = useSession();
  const token = searchParams.token || '';
  const acceptInvite = useAcceptInvite();
  const attempted = useRef(false);

  const [orgName, setOrgName] = useState<string | null>(null);

  useEffect(() => {
    if (status === 'loading' || !session || !token || attempted.current) return;
    attempted.current = true;

    acceptInvite.mutate(token, {
      onSuccess: (data) => {
        setOrgName(data.organization?.name || 'Organização');
      },
    });
  }, [token, session, status, acceptInvite]);

  if (!token) {
    return (
      <AuthShell>
        <Card className="w-full border-border/60 shadow-sm">
          <CardHeader className="text-center">
            <XCircle className="mx-auto h-12 w-12 text-destructive" aria-hidden="true" />
            <CardTitle className="font-heading text-2xl font-semibold tracking-tight">Link inválido</CardTitle>
            <CardDescription>
              O link de convite não contém um token válido.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Link href="/dashboard">
              <Button variant="outline" className="h-11">
                Ir para o dashboard
              </Button>
            </Link>
          </CardContent>
        </Card>
      </AuthShell>
    );
  }

  if (status === 'loading' || acceptInvite.isPending) {
    return (
      <AuthShell>
        <Card className="w-full border-border/60 shadow-sm">
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <Loader2 className="h-10 w-10 animate-spin text-primary" aria-hidden="true" />
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {status === 'loading' ? 'Verificando sessão...' : 'Aceitando convite...'}
            </p>
          </CardContent>
        </Card>
      </AuthShell>
    );
  }

  if (!session) {
    const callbackUrl = encodeURIComponent(`/aceitar-convite?token=${token}`);
    return (
      <AuthShell>
        <Card className="w-full border-border/60 shadow-sm">
          <CardHeader className="space-y-2 text-center">
            <Building2 className="mx-auto h-12 w-12 text-primary" aria-hidden="true" />
            <CardTitle className="font-heading text-2xl font-semibold tracking-tight">Convite para organização</CardTitle>
            <CardDescription>
              Você precisa estar logado para aceitar este convite. Faça login ou crie uma conta com o e-mail do convite.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-center">
            <Link href={`/login?callbackUrl=${callbackUrl}`}>
              <Button className="h-11 w-full">Fazer login</Button>
            </Link>
            <Link href={`/register?callbackUrl=${callbackUrl}`}>
              <Button variant="outline" className="h-11 w-full">Criar conta</Button>
            </Link>
          </CardContent>
        </Card>
      </AuthShell>
    );
  }

  if (acceptInvite.isError) {
    const errorMsg = acceptInvite.error instanceof Error
      ? acceptInvite.error.message
      : 'Erro ao aceitar convite';

    return (
      <AuthShell>
        <Card className="w-full border-border/60 shadow-sm">
          <CardHeader className="space-y-2 text-center">
            <XCircle className="mx-auto h-12 w-12 text-destructive" aria-hidden="true" />
            <CardTitle className="font-heading text-2xl font-semibold tracking-tight">Erro no convite</CardTitle>
            <CardDescription>{errorMsg}</CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Link href="/dashboard">
              <Button variant="outline" className="h-11">
                Ir para o dashboard
              </Button>
            </Link>
          </CardContent>
        </Card>
      </AuthShell>
    );
  }

  if (acceptInvite.isSuccess) {
    return (
      <AuthShell>
        <Card className="w-full border-border/60 shadow-sm">
          <CardHeader className="space-y-2 text-center">
            <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" aria-hidden="true" />
            <CardTitle className="font-heading text-2xl font-semibold tracking-tight">Convite aceito!</CardTitle>
            <CardDescription>
              Você agora é membro de <strong>{orgName}</strong>.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Button className="h-11 w-full" onClick={() => router.push('/dashboard')}>
              Ir para o dashboard
            </Button>
          </CardContent>
        </Card>
      </AuthShell>
    );
  }

  return null;
}
