"""Utilitários de normalização de dados para dedupe entre fontes (Places/CSV/CNAE)."""
import re

_SCHEME_RE = re.compile(r"^https?://")
_WWW_RE = re.compile(r"^www\.")


def normalize_domain(url: str | None) -> str | None:
    """Extrai o domínio canônico (sem scheme/www, sem porta/caminho/query, lowercase).

    Ex.: 'https://www.Firma.com.br/pagina' -> 'firma.com.br'
    """
    if not url:
        return None
    domain = url.strip().lower()
    domain = _SCHEME_RE.sub("", domain)
    domain = _WWW_RE.sub("", domain)
    domain = domain.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    return domain or None
