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

# Herramentas de design / link que NÃO são o site da empresa — o negócio usa o
# link só para divulgação/solicitação de pedido (ex.: Canva). Tratados como
# "sem site próprio" (roadmap-leads P3 / S3).
_TOOL_DOMAINS = {
    "canva.com",
    "canva.link",
    "beacons.ai",
    "linkbio.co",
}

# Marketplaces / storefronts de terceiros (e-commerce de entrega, cardápio ou
# vitrine) que NÃO representam um site próprio — o negócio depende da
# plataforma de outrem, sendo portanto público-alvo de um site próprio.
_MARKETPLACE_DOMAINS = {
    "instadelivery.com.br",
    "ifood.com.br",
    "pedidosja.com.br",
    "cardapioja.com",
    "deliveryextra.com",
    "menuqr.com.br",
    "foodzap.com.br",
}

# Raízes cujos SUBDOMÍNIOS também contam como rede social/ferramenta (ex.:
# "api.whatsapp.com" é WhatsApp, não site). Qualquer host que termine com uma
# destas raízes é tratado como "sem site próprio".
_SUBDOMAIN_SOCIAL_ROOTS = (
    "whatsapp.com",
    "wa.me",
    "canva.com",
    "canva.link",
    "instagram.com",
)


def _clean_domain(url: str | None) -> str | None:
    """Remove scheme/www e devolve o host (lowercase, sem caminho/query/fragmento)."""
    if not url:
        return None
    domain = url.strip().lower()
    domain = _SCHEME_RE.sub("", domain)
    domain = _WWW_RE.sub("", domain)
    domain = domain.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    return domain or None


def _is_non_own_website_domain(domain: str) -> bool:
    """True se o host aponta para rede social / ferramenta / marketplace.

    Considera tanto o host exato quanto subdomínios de raízes sociais
    (ex.: "api.whatsapp.com" → whatsapp → sem site próprio).
    """
    if domain in _SOCIAL_DOMAINS or domain in _TOOL_DOMAINS or domain in _MARKETPLACE_DOMAINS:
        return True
    for root in _SUBDOMAIN_SOCIAL_ROOTS:
        if domain.endswith("." + root):
            return True
    return False


def normalize_domain(url: str | None) -> str | None:
    """Extrai o domínio canônico (sem scheme/www, sem porta/caminho/query, lowercase).

    Ex.: 'https://www.Firma.com.br/pagina' -> 'firma.com.br'

    Retorna None para domínios sem site próprio (redes sociais, ferramentas
    como Canva, marketplaces, e subdomínios dessas raízes) e para entradas
    vazias — esses não são chave de dedupe válida.
    """
    domain = _clean_domain(url)
    if not domain:
        return None
    if _is_non_own_website_domain(domain):
        return None
    return domain


def is_social_domain(url: str | None) -> bool:
    """Indica se a URL aponta para rede social/ferramenta/marketplace (sem site próprio)."""
    domain = _clean_domain(url)
    if not domain:
        return False
    return _is_non_own_website_domain(domain)
