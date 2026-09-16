"""Extração determinística de FACTs de HTML público (1D, sem LLM).

Tudo observável, sem julgamento comercial: title, meta, canonical, links de
páginas, contatos públicos, sociais, JSON-LD básico, robots/sitemap quando o
caller informar. Ausência de evidência = None/"unknown", nunca False.
"""
from __future__ import annotations

import html as _html
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

_TITLE_RE = re.compile(r"<title[^>]*>([^<]*)", re.IGNORECASE)
_META_DESC_RE = re.compile(
    r'<meta\s+[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_META_DESC_REV_RE = re.compile(
    r'<meta\s+[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']',
    re.IGNORECASE,
)
_CANONICAL_RE = re.compile(
    r'<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_CANONICAL_REV_RE = re.compile(
    r'<link\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']',
    re.IGNORECASE,
)
_LINK_RE = re.compile(
    r'<a\s+[^>]*href=["\']?([^"\'\s>]+)["\']?[^>]*>(.*?)(?:</a\s*>)?',
    re.IGNORECASE | re.DOTALL,
)
_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\(?\d{2}\)?[\s.-]?\d{4,5}[\s.-]?\d{4}")
_STRIP_TAGS_RE = re.compile(r"<[^>]+>")
_SOCIAL_PATTERNS = {
    "instagram": re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]{1,30})", re.IGNORECASE),
    "facebook": re.compile(r"(?:https?://)?(?:www\.)?facebook\.com/([A-Za-z0-9._-]{1,50})", re.IGNORECASE),
    "linkedin": re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(company|in)/([A-Za-z0-9._-]+)", re.IGNORECASE),
}

_CONTACT_HINTS = ("contato", "contact", "fale-conosco", "faleconosco", "orcamento")
_ABOUT_HINTS = ("sobre", "about", "quem-somos", "empresa", "institucional")
_SERVICES_HINTS = ("servico", "service", "solucao", "produto", "atuacao")


def _clean(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    cleaned = _STRIP_TAGS_RE.sub("", text)
    cleaned = _html.unescape(cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned or None


def extract_web_facts(html_text: Optional[str], *, url: Optional[str] = None) -> Dict[str, Any]:
    """Extrai FACTs observáveis do HTML. Nunca inventa dado ausente."""
    source = html_text or ""
    title_match = _TITLE_RE.search(source)
    title = _clean(title_match.group(1).split("<")[0] if title_match else None)
    desc_match = _META_DESC_RE.search(source) or _META_DESC_REV_RE.search(source)
    description = _clean(desc_match.group(1) if desc_match else None)
    canon_match = _CANONICAL_RE.search(source) or _CANONICAL_REV_RE.search(source)
    canonical = canon_match.group(1).strip() if canon_match else None
    links = _page_links(source, base=url)
    visible = _clean(source) or ""
    emails = sorted(set(_EMAIL_RE.findall(visible)))[:10]
    phones = sorted(set(_PHONE_RE.findall(visible)))[:10]
    socials = _social_links(source)
    structured = _jsonld_types(source)
    return {
        "site_reachable": True if source.strip() else "unknown",
        "page_title": title,
        "meta_description": description,
        "meta_presence": "present" if description else "unknown",
        "canonical_url": canonical,
        "contact_page": links.get("contact_page"),
        "about_page": links.get("about_page"),
        "services_page": links.get("services_page"),
        "public_emails": emails,
        "public_phones": phones,
        "social_links": socials,
        "structured_data_types": structured,
        "kind": "FACT",
    }


def _page_links(source: str, *, base: Optional[str]) -> Dict[str, Optional[str]]:
    found: Dict[str, Optional[str]] = {
        "contact_page": None, "about_page": None, "services_page": None,
    }
    for raw_href, _label in _LINK_RE.findall(source):
        href = (raw_href or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        lowered = href.lower()
        absolute = urljoin(base, href) if base else href
        if found["contact_page"] is None and any(h in lowered for h in _CONTACT_HINTS):
            found["contact_page"] = absolute
        elif found["about_page"] is None and any(h in lowered for h in _ABOUT_HINTS):
            found["about_page"] = absolute
        elif found["services_page"] is None and any(h in lowered for h in _SERVICES_HINTS):
            found["services_page"] = absolute
        if all(found.values()):
            break
    return found


def _social_links(source: str) -> Dict[str, str]:
    socials: Dict[str, str] = {}
    for name, pattern in _SOCIAL_PATTERNS.items():
        match = pattern.search(source)
        if match:
            socials[name] = match.group(0)
    return socials


def _jsonld_types(source: str) -> List[str]:
    types: List[str] = []
    for raw in _JSONLD_RE.findall(source):
        try:
            payload = json.loads(raw.strip())
        except (TypeError, ValueError):
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            kind = node.get("@type")
            kinds = kind if isinstance(kind, list) else [kind]
            for item in kinds:
                if item and str(item) not in types:
                    types.append(str(item))
    return types[:20]


def facts_from_fetch_result(result: Dict[str, Any], *, url: str) -> Dict[str, Any]:
    """Converte resultado do SafePublicWebClient em FACTs (UNKNOWN != FALSE)."""
    status = (result or {}).get("status")
    if status != "ok":
        return {
            "site_reachable": "unknown",
            "fetch_status": status,
            "fetch_reason": (result or {}).get("reason"),
            "source_url": url,
            "kind": "FACT",
        }
    facts = extract_web_facts((result or {}).get("text") or "", url=url)
    facts["source_url"] = (result or {}).get("url") or url
    facts["fetch_status"] = "ok"
    return facts
