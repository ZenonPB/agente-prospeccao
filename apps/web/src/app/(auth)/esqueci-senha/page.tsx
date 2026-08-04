'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import Link from 'next/link';
import { ArrowLeft, Mail, Loader2, CheckCircle2 } from 'lucide-react';
import { AuthShell } from '@/components/auth/auth-shell';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      if (!res.ok) {
        setError('Erro ao solicitar redefinição. Tente novamente.');
        setLoading(false);
        return;
      }

      setSent(true);
    } catch {
      setError('Erro de conexão. Verifique sua internet e tente novamente.');
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <AuthShell>
        <Card className="border-border/60 shadow-sm">
          <CardHeader className="space-y-2 text-center">
            <div className="flex justify-center">
              <CheckCircle2 className="h-12 w-12 text-emerald-500" />
            </div>
            <CardTitle className="font-heading text-2xl font-semibold tracking-tight">Email enviado</CardTitle>
            <CardDescription>
              Se o email existir, você receberá um link de redefinição de senha.
              Verifique sua caixa de entrada e spam.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground text-center">
              O link expira em 2 horas.
            </p>
            <Link href="/login">
              <Button variant="outline" className="w-full h-11">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Voltar para o login
              </Button>
            </Link>
          </CardContent>
        </Card>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <Card className="border-border/60 shadow-sm">
        <CardHeader className="space-y-2 text-center">
          <CardTitle className="font-heading text-2xl font-semibold tracking-tight">Redefinir senha</CardTitle>
          <CardDescription>
            Digite seu email e enviaremos um link para redefinir sua senha.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="seu@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            {error && (
              <p className="text-sm text-red-500">{error}</p>
            )}

            <Button type="submit" className="h-12 w-full text-base" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Enviando...
                </>
              ) : (
                <>
                  <Mail className="mr-2 h-4 w-4" />
                  Enviar link de redefinição
                </>
              )}
            </Button>
          </form>

          <div className="text-center">
            <Link href="/login" className="text-sm text-primary hover:underline">
              <ArrowLeft className="mr-1 inline h-3 w-3" />
              Voltar para o login
            </Link>
          </div>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
