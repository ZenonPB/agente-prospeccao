'use client';

import { useSession } from 'next-auth/react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Camera, Sun, Moon, Palette, Lock, Save, Loader2, Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { authApi } from '@/lib/api';
import { SalesRoleBadge } from '@/components/sales/sales-role-badge';
import { OrgSecretsCard } from '@/components/configuracoes/org-secrets-card';
import { OrgSendSettings } from '@/components/configuracoes/org-send-settings';
import { useOrgMembership } from '@/hooks/use-api';
import { PageHeader } from '@/components/ui/page-header';
import { useTheme } from 'next-themes';

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
    description: 'Tema AlphaMec (vermelho profundo)',
    icon: Palette,
    preview: 'bg-[#4c0000] border-[#7c0000]',
    previewText: 'text-white',
    previewAccent: 'bg-[#630201]',
  },
];

export default function ConfiguracoesPage() {
  const { data: session, update } = useSession();
  const { data: membership } = useOrgMembership();
  const { theme, setTheme } = useTheme();

  const handleThemeChange = (themeId: string) => {
    setTheme(themeId);
    toast.success(`Tema "${themes.find(t => t.id === themeId)?.name}" aplicado.`);
  };

  const [name, setName] = useState(session?.user?.name || '');
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);

  const initials = session?.user?.name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase() || 'U';

  const handleSaveProfile = async () => {
    setSavingProfile(true);
    try {
      await authApi.updateProfile(name);
      await update();
      toast.success('Perfil atualizado com sucesso.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar perfil.');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error('As senhas não coincidem.');
      return;
    }
    if (newPassword.length < 8) {
      toast.error('A senha deve ter no mínimo 8 caracteres.');
      return;
    }
    setChangingPassword(true);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      toast.success('Senha alterada com sucesso.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao alterar senha.');
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageHeader
        eyebrow="Gestão"
        title="Configurações"
        description="Gerencie suas preferências e informações da conta"
      />

      {/* Perfil */}
      <Card>
        <CardHeader>
          <CardTitle>Perfil</CardTitle>
          <CardDescription>
            Suas informações pessoais na plataforma
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
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

          <div className="space-y-2">
            <Label htmlFor="name">Nome completo</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Seu nome"
            />
          </div>

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

          <div className="space-y-2">
            <Label>Papel na equipe</Label>
            <div className="flex items-center gap-2">
              <SalesRoleBadge role={membership?.membership?.sales_role} />
              <span className="text-sm text-muted-foreground">
                {membership?.organization?.name || 'Sua organização'}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Define o que você vê e pode fazer na organização
            </p>
          </div>

          <div className="flex justify-end">
            <Button onClick={handleSaveProfile} disabled={savingProfile}>
              {savingProfile ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-1.5 h-4 w-4" />
              )}
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
            {themes.map((themeItem) => {
              const Icon = themeItem.icon;
              const isActive = theme === themeItem.id;
              return (
                <button
                  key={themeItem.id}
                  type="button"
                  onClick={() => handleThemeChange(themeItem.id)}
                  className={`relative flex flex-col items-center gap-3 rounded-xl border-2 p-4 text-center transition-all hover:shadow-md ${
                    isActive
                      ? 'border-primary shadow-sm'
                      : 'border-transparent bg-muted/50 hover:border-muted-foreground/20'
                  }`}
                >
                  <div
                    className={`flex h-20 w-full items-center justify-center rounded-lg border ${themeItem.preview} ${themeItem.previewText}`}
                  >
                    <div className="flex flex-col items-center gap-1.5">
                      <div className={`h-2 w-12 rounded ${themeItem.previewAccent}`} />
                      <div className={`h-2 w-8 rounded ${themeItem.previewAccent}`} />
                    </div>
                  </div>

                  <Icon className="h-5 w-5" />
                  <div>
                    <p className="text-sm font-medium">{themeItem.name}</p>
                    <p className="text-xs text-muted-foreground">{themeItem.description}</p>
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
        <CardContent>
          <form onSubmit={handleChangePassword} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="currentPassword">Senha atual</Label>
              <Input
                id="currentPassword"
                type={showPasswords ? 'text' : 'password'}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                placeholder="••••••••"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="newPassword">Nova senha</Label>
              <Input
                id="newPassword"
                type={showPasswords ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                placeholder="••••••••"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirmar nova senha</Label>
              <Input
                id="confirmPassword"
                type={showPasswords ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                placeholder="••••••••"
              />
            </div>

            <div className="flex items-center justify-between">
              <button
                type="button"
                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
                onClick={() => setShowPasswords(!showPasswords)}
              >
                {showPasswords ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                {showPasswords ? 'Ocultar senhas' : 'Mostrar senhas'}
              </button>
              <Button type="submit" disabled={changingPassword}>
                {changingPassword ? (
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                ) : (
                  <Lock className="mr-1.5 h-4 w-4" />
                )}
                Alterar senha
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Chaves de API (BYOK) */}
      <OrgSecretsCard />

      {/* Envio de follow-ups (item 3.7) */}
      <OrgSendSettings />
    </div>
  );
}
