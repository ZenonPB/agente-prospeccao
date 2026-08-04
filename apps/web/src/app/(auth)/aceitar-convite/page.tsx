'use client';

import { use, useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Loader2, CheckCircle2, XCircle, Building2 } from 'lucide-react';
import Link from 'next/link';
import { useAcceptInvite } from '@/hooks/use-api';

export default function AcceptInvitePage(props: { searchParams: Promise<{ token?: string }> }) {
  const searchParams = use(props.searchParams);
  const router = useRouter();
  const { data: session, status } = useSession();
  const token = searchParams.token || '';
  const acceptInvite = useAcceptInvite();

  const [orgName, setOrgName] = useState<string | null>(null);

  useEffect(() => {
    if (status === 'loading') return;
    if (!session) return;

    if (token && !acceptInvite.isSuccess && !acceptInvite.isError && !acceptInvite.isPending) {
      acceptInvite.mutate(token, {
        onSuccess: (data) => {
          setOrgName(data.organization?.name || 'Organização');
        },
      });
    }
  }, [token, session, status]);

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">Link inválido</CardTitle>
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
      </div>
    );
  }

  if (status === 'loading' || acceptInvite.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">
              {status === 'loading' ? 'Verificando sessão...' : 'Aceitando convite...'}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-2 text-center">
            <Building2 className="mx-auto h-12 w-12 text-primary" />
            <CardTitle className="text-2xl font-bold">Convite para organização</CardTitle>
            <CardDescription>
              Você precisa estar logado para aceitar este convite. Faça login ou crie uma conta com o e-mail do convite.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-center">
            <Link href={`/login?callbackUrl=${encodeURIComponent(`/aceitar-convite?token=${token}`)}`}>
              <Button className="h-11 w-full">Fazer login</Button>
            </Link>
            <Link href={`/register?callbackUrl=${encodeURIComponent(`/aceitar-convite?token=${token}`)}`}>
              <Button variant="outline" className="h-11 w-full">Criar conta</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (acceptInvite.isError) {
    const errorMsg = acceptInvite.error instanceof Error
      ? acceptInvite.error.message
      : 'Erro ao aceitar convite';

    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-2 text-center">
            <XCircle className="mx-auto h-12 w-12 text-destructive" />
            <CardTitle className="text-2xl font-bold">Erro no convite</CardTitle>
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
      </div>
    );
  }

  if (acceptInvite.isSuccess) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-2 text-center">
            <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" />
            <CardTitle className="text-2xl font-bold">Convite aceito!</CardTitle>
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
      </div>
    );
  }

  return null;
}
