"""Utilitários de normalização de dados para dedupe entre fontes (Places/CSV/CNAE)."""
import re

_SCHEME_RE = re.compile(r"^https?://")
_WWW_RE = re.compile(r"^www\.")

# Domínios de redes sociais/perfil — NÃO são o site da empresa. Negócios sem
# site próprio só têm presença social (ex.: instagram.com), então normalizá-los
# faria N leads distintos colidirem no mesmo `normalized_domain` e quebrar a
# constraint única (organization_id, normalized_domain). Retornar None mantém
# o domínio social fora da dedupe por domínio (place_id/CNPJ continuam valendo).
_SOCIAL_DOMAINS = {
    "instagram.com",
    "facebook.com",
    "fb.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "youtu.be",
    "wa.me",
    "whatsapp.com",
    "whatsapp.link",
    "linktr.ee",
    "tiktok.com",
    "behance.net",
    "medium.com",
    "blogspot.com",
    "wixsite.com",
    "business.site",
}


def normalize_domain(url: str | None) -> str | None:
    """Extrai o domínio canônico (sem scheme/www, sem porta/caminho/query, lowercase).

    Ex.: 'https://www.Firma.com.br/pagina' -> 'firma.com.br'

    Retorna None para domínios sociais genéricos (Instagram, Facebook, etc.)
    e para entradas vazias — esses não são chave de dedupe válida.
    """
    if not url:
        return None
    domain = url.strip().lower()
    domain = _SCHEME_RE.sub("", domain)
    domain = _WWW_RE.sub("", domain)
    domain = domain.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if domain in _SOCIAL_DOMAINS:
        return None
    return domain or None


def is_social_domain(url: str | None) -> bool:
    """Indica se a URL aponta para uma rede social/perfil genérico (sem site próprio)."""
    if not url:
        return False
    domain = url.strip().lower()
    domain = _SCHEME_RE.sub("", domain)
    domain = _WWW_RE.sub("", domain)
    domain = domain.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    return domain in _SOCIAL_DOMAINS
