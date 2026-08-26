'use client';

import { useSession, signOut } from 'next-auth/react';
import { Menu, HelpCircle, Bell, CheckCheck } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useAppStore } from '@/stores/useAppStore';
import { useOnboardingStore } from '@/stores/useOnboardingStore';
import { useUpdateOnboardingStatus, useNotifications, useMarkNotificationRead, useMarkAllNotificationsRead } from '@/hooks/use-api';
import { BrandLogo } from './brand-logo';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';

export function Header() {
  const router = useRouter();
  const { data: session } = useSession();
  const { toggleSidebar } = useAppStore();
  const { resetTour } = useOnboardingStore();
  const updateStatusMutation = useUpdateOnboardingStatus();
  const { data: notifData } = useNotifications({ limit: 10 });
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();

  const unreadCount = notifData?.unread_count ?? 0;

  const handleRestartTour = () => {
    resetTour();
    updateStatusMutation.mutate('NOT_STARTED');
  };

  const handleNotificationClick = (notif: { id: string; lead_id?: string; is_read: boolean }) => {
    if (!notif.is_read) {
      markRead.mutate(notif.id);
    }
    if (notif.lead_id) {
      router.push(`/oportunidades/${notif.lead_id}`);
    }
  };

  const handleMarkAllRead = () => {
    markAllRead.mutate(undefined, {
      onSuccess: () => toast.success('Todas as notificações marcadas como lidas'),
    });
  };

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b bg-card px-4 lg:px-6">
      {/* Left side */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className="h-10 w-10 lg:hidden"
          aria-label="Abrir menu"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <Link href="/dashboard" className="flex items-center gap-2 lg:hidden">
          <BrandLogo className="h-6 w-6 text-primary" />
          <span className="text-[15px] font-semibold tracking-tight">Prospect.ai</span>
        </Link>
      </div>

      {/* Right side — notifications + user menu */}
      <div className="flex items-center gap-2">
        {/* Notification bell */}
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" size="icon" className="relative h-10 w-10" aria-label="Notificações" />
            }
          >
            <Bell className="h-5 w-5" />
            {unreadCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-80" align="end">
            <DropdownMenuLabel className="flex items-center justify-between">
              <span>Notificações</span>
              {unreadCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto gap-1 px-2 py-0.5 text-xs"
                  onClick={handleMarkAllRead}
                >
                  <CheckCheck className="h-3 w-3" />
                  Marcar todas como lidas
                </Button>
              )}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {(!notifData?.notifications || notifData.notifications.length === 0) ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                Nenhuma notificação
              </div>
            ) : (
              notifData.notifications.map((notif) => (
                <DropdownMenuItem
                  key={notif.id}
                  className={`flex flex-col items-start gap-1 py-2.5 ${!notif.is_read ? 'bg-primary/5' : ''}`}
                  onClick={() => handleNotificationClick(notif)}
                >
                  <div className="flex w-full items-center gap-2">
                    {!notif.is_read && (
                      <span className="h-2 w-2 shrink-0 rounded-full bg-primary" />
                    )}
                    <span className="flex-1 truncate text-sm font-medium">{notif.title}</span>
                  </div>
                  {notif.message && (
                    <p className="ml-4 text-xs text-muted-foreground line-clamp-2">{notif.message}</p>
                  )}
                </DropdownMenuItem>
              ))
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="ghost" className="relative h-10 items-center gap-2 rounded-full pr-2" aria-label="Menu do usuário" />}
          >
            <Avatar className="h-8 w-8">
              <AvatarImage src={session?.user?.image || ''} alt={session?.user?.name || ''} />
              <AvatarFallback>
                {session?.user?.name?.split(' ').map((n) => n[0]).join('').toUpperCase() || 'U'}
              </AvatarFallback>
            </Avatar>
            <span className="hidden max-w-40 truncate text-sm font-medium sm:block">
              {session?.user?.name}
            </span>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56" align="end">
            <DropdownMenuGroup>
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none">{session?.user?.name}</p>
                  <p className="text-xs leading-none text-muted-foreground">
                    {session?.user?.email}
                  </p>
                </div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem render={<Link href="/configuracoes" />}>
              Configurações
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleRestartTour}>
              <HelpCircle className="mr-2 h-4 w-4" />
              Refazer Tutorial
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => signOut()}>
              Sair da conta
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
