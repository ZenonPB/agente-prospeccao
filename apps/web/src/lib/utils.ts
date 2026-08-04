import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Normaliza um telefone BR para o formato wa.me (código do país + DDD + número).
 * Aceita "(16) 99999-9999", "16 999999999", "+55 11 91234-5678", etc.
 * Retorna null se não houver dígitos suficientes para o WhatsApp.
 */
export function toWhatsAppNumber(phone?: string | null): string | null {
  if (!phone) return null;
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 10 || digits.length > 13) return null;
  // Já tem código do país (55...)? Se não, adiciona 55 (Brasil).
  const withCountry = digits.length === 12 || digits.length === 13
    ? digits
    : `55${digits}`;
  return withCountry;
}

export function whatsAppLink(phone?: string | null, text?: string | null): string | null {
  const number = toWhatsAppNumber(phone);
  if (!number) return null;
  const base = `https://wa.me/${number}`;
  return text ? `${base}?text=${encodeURIComponent(text)}` : base;
}
