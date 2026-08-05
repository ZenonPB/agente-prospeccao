import { cn } from "@/lib/utils";

interface BrandMarkProps {
  className?: string;
}

/**
 * Marca do produto: um radar — anéis concêntricos + um "ping" de sinal.
 * Prospecção é caça ao sinal; o ping é a oportunidade encontrada.
 */
export function BrandMark({ className }: BrandMarkProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className={cn("h-8 w-8", className)}
    >
      <circle
        cx="16"
        cy="16"
        r="12.5"
        stroke="currentColor"
        strokeOpacity="0.3"
        strokeWidth="2"
      />
      <circle
        cx="16"
        cy="16"
        r="7.5"
        stroke="currentColor"
        strokeOpacity="0.55"
        strokeWidth="2"
      />
      <circle cx="16" cy="16" r="2.5" fill="currentColor" />
      <circle cx="23.5" cy="8.5" r="2" fill="currentColor" />
    </svg>
  );
}
