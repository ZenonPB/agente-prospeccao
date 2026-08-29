"use client";

import Image from "next/image";
import { useTheme } from "@/components/theme-provider";
import { useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";
import { BrandMark } from "./brand-mark";

interface BrandLogoProps {
  className?: string;
}

/**
 * Marca do produto: no tema AlphaMec exibe a logo oficial da empresa; nos
 * demais temas mantém o radar (varredura de sinais).
 */
export function BrandLogo({ className }: BrandLogoProps) {
  const { theme } = useTheme();
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );

  if (mounted && theme === "alpha") {
    return (
      <Image
        src="/imgs/alphamec/logo-alphamec.png"
        alt="Logotipo da AlphaMec"
        width={32}
        height={32}
        className={cn("h-8 w-8 shrink-0 object-contain", className)}
      />
    );
  }

  return <BrandMark className={className} />;
}
