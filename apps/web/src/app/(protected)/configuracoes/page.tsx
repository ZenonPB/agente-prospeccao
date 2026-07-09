'use client';

import { useSession } from 'next-auth/react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { Camera, Sun, Moon, Palette, Lock, Save } from 'lucide-react';
import { useState } from 'react';

const themes = [
  {
    id: 'light' as const,
    name: 'Claro',
    description: 'Fundo claro com texto escuro',
    icon: Sun,
    preview: 'bg-white border-gray-300',
    previewText: 'text-gray-900',
    previewAccent: 'bg-gray-100',
  },
  {
    id: 'dark' as const,
    name: 'Escuro',
    description: 'Fundo escuro com texto claro',
    icon: Moon,
    preview: 'bg-gray-950 border-gray-700',
    previewText: 'text-gray-100',
    previewAccent: 'bg-gray-800',
  },
  {
    id: 'alpha' as const,
    name: 'Alpha',
    description: 'Tema exclusivo com identidade própria',
    icon: Palette,
    preview: 'bg-zinc-900 border-emerald-700',
    previewText: 'text-emerald-100',
    previewAccent: 'bg-emerald-900/40',
  },
];

export default function ConfiguracoesPage() {
  const { data: session } = useSession();
  const [selectedTheme, setSelectedTheme] = useState('dark');

  const initials = session?.user?.name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase() || 'U';

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Configurações</h1>
        <p className="text-sm text-muted-foreground">
          Gerencie suas preferências e informações da conta
        </p>
      </div>

      {/* Perfil */}
      <Card>
        <CardHeader>
          <CardTitle>Perfil</CardTitle>
          <CardDescription>
            Suas informações pessoais na plataforma
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Avatar */}
          <div className="flex items-center gap-4">
            <Avatar className="h-16 w-16">
              <AvatarFallback className="text-lg">{initials}</AvatarFallback>
            </Avatar>
            <div>
              <Button variant="outline" size="sm" disabled>
                <Camera className="mr-1.5 h-4 w-4" />
                Alterar foto
              </Button>
              <p className="mt-1 text-xs text-muted-foreground">Em breve</p>
            </div>
          </div>

          {/* Nome */}
          <div className="space-y-2">
            <Label htmlFor="name">Nome completo</Label>
            <Input
              id="name"
              defaultValue={session?.user?.name || ''}
              placeholder="Seu nome"
            />
          </div>

          {/* Email */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="email">Email</Label>
              <Badge variant="outline" className="text-[10px] font-normal">Em breve</Badge>
            </div>
            <Input
              id="email"
              defaultValue={session?.user?.email || ''}
              disabled
              className="opacity-60"
            />
            <p className="text-xs text-muted-foreground">
              A alteração de email será integrada com verificação por email
            </p>
          </div>

          {/* Função */}
          <div className="space-y-2">
            <Label>Função</Label>
            <Input
              value={(session?.user as { role?: string } | undefined)?.role || 'Vendas'}
              disabled
              className="opacity-60"
            />
          </div>

          <div className="flex justify-end">
            <Button>
              <Save className="mr-1.5 h-4 w-4" />
              Salvar alterações
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Aparência */}
      <Card>
        <CardHeader>
          <CardTitle>Aparência</CardTitle>
          <CardDescription>
            Escolha o tema do aplicativo
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-3">
            {themes.map((theme) => {
              const Icon = theme.icon;
              const isActive = selectedTheme === theme.id;
              return (
                <button
                  key={theme.id}
                  type="button"
                  onClick={() => setSelectedTheme(theme.id)}
                  className={`relative flex flex-col items-center gap-3 rounded-xl border-2 p-4 text-center transition-all hover:shadow-md ${
                    isActive
                      ? 'border-primary shadow-sm'
                      : 'border-transparent bg-muted/50 hover:border-muted-foreground/20'
                  }`}
                >
                  {/* Preview */}
                  <div
                    className={`flex h-20 w-full items-center justify-center rounded-lg border ${theme.preview} ${theme.previewText}`}
                  >
                    <div className="flex flex-col items-center gap-1.5">
                      <div className={`h-2 w-12 rounded ${theme.previewAccent}`} />
                      <div className={`h-2 w-8 rounded ${theme.previewAccent}`} />
                    </div>
                  </div>

                  <Icon className="h-5 w-5" />
                  <div>
                    <p className="text-sm font-medium">{theme.name}</p>
                    <p className="text-xs text-muted-foreground">{theme.description}</p>
                  </div>

                  {isActive && (
                    <div className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                      ✓
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Segurança */}
      <Card>
        <CardHeader>
          <CardTitle>Segurança</CardTitle>
          <CardDescription>
            Gerencie sua senha e métodos de acesso
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-lg border border-dashed bg-muted/30 p-6 text-center">
            <Lock className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">Alteração de senha</p>
            <p className="mt-1 text-xs text-muted-foreground">
              A funcionalidade de alterar senha será integrada com verificação por email.
            </p>
            <Badge variant="secondary" className="mt-3">Em breve</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
