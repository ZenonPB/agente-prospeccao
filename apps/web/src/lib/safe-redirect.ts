const CONTROL_CHARACTERS = /[\u0000-\u001F\u007F]/;

/**
 * Resolve um callback de autenticação somente para caminhos internos.
 *
 * Rejeita URLs absolutas, protocol-relative, barras invertidas e variantes
 * percent-encoded que poderiam escapar da aplicação. Entradas inválidas sempre
 * caem no dashboard.
 */
export function resolveSafeCallbackUrl(
  raw: string | null | undefined,
  fallback = '/dashboard',
): string {
  if (!raw) return fallback;

  let value = raw.trim();
  if (!value) return fallback;

  // Normaliza até três camadas de encoding, suficiente para callbacks legítimos
  // e para neutralizar tentativas comuns de double/triple encoding.
  for (let i = 0; i < 3; i += 1) {
    try {
      const decoded = decodeURIComponent(value);
      if (decoded === value) break;
      value = decoded;
    } catch {
      return fallback;
    }
  }

  if (
    CONTROL_CHARACTERS.test(value) ||
    value.includes('\\') ||
    !value.startsWith('/') ||
    value.startsWith('//')
  ) {
    return fallback;
  }

  // URL() é usada apenas como validação estrutural contra uma origem sintética.
  // O resultado só é aceito quando permanece na mesma origem e preserva path.
  try {
    const base = new URL('https://app.local');
    const candidate = new URL(value, base);
    if (candidate.origin !== base.origin) return fallback;
    return `${candidate.pathname}${candidate.search}${candidate.hash}`;
  } catch {
    return fallback;
  }
}
