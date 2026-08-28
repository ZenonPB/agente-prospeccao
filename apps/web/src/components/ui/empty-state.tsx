import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

/**
 * Estado vazio que orienta o usuário: explica o que fazer em vez de
 * apenas dizer "não há nada aqui". O ícone pulsa como um radar à
 * espera de sinais — a assinatura visual do produto.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-14 text-center animate-fade-up",
        className,
      )}
    >
      {icon && (
        <div className="sonar flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          {icon}
        </div>
      )}
      <h3 className="font-heading text-base font-semibold tracking-tight">{title}</h3>
      {description && (
        <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
