"""ContactEnrichmentService — enriquece contatos (decisores) com e-mail e LinkedIn.

Multi-provider com ordem de precedência e fallback transparente, 100% passivo
(Lei 12.737/2012 — nunca probe, nunca injetar, nunca testar auth):

E-mail:
1. Hunter.io — se `HUNTER_API_KEY` existir (opcional, BYOK futura).
2. Receita Federal (CNPJ) — reusa `CnpjService` (sócios/administradores).
3. Heurística determinística — `primeiro.ultimo@dominio` com confidence baixa.

LinkedIn (perfil do decisor):
1. Busca passiva em buscador público (Bing HTML, sem API paga) por
   `"<nome>" <empresa> linkedin` + extração da URL do resultado.
2. Heurística de URL — `linkedin.com/in/<primeiro-ultimo>` + validação
   passiva `HEAD` (HTTP 200 indica que a página existe publicamente).

Regras de negócio (docs/business-rules.md):
- `confidence >= 50` → contato apto para outreach.
- E-mail genérico de empresa (contato@, comercial@) → confidence 50-69.
- LinkedIn encontrado com URL validada → soma pontos de confidence.

Saída: lista de dicts normalizados + persistência em `Contact` (upsert).
"""
import asyncio
import hashlib
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.settings import settings  # noqa: E402
from database.models import Contact, ContactRole, Lead, LeadStatus  # noqa: E402

logger = logging.getLogger(__name__)

# Validação de sintaxe de e-mail (item 3.6) — simples e sem dependência nova.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")


def is_valid_email_syntax(email: Optional[str]) -> bool:
    """True se o e-mail tem sintaxe válida (sem resolver MX — sem rede)."""
    return bool(email and _EMAIL_RE.match(email.strip()))


# Campos sensíveis (LGPD) removidos do `raw_data` persistido de contatos.
_SENSITIVE_RAW_KEYS = (
    "cnpj_cpf_do_socio", "cpf", "taxId", "tax_id", "document", "document_cpf",
    "faixa_etaria", "faixa_etária", "nationality", "nascimento", "birthdate",
)


def _sanitize_raw(raw: Any) -> Optional[Dict[str, Any]]:
    """Remove campos pessoais sensíveis do payload cru antes de persistir
    (item 4.7 — minimização LGPD: CPF/faixa etária não são necessários para
    o fluxo de vendas)."""
    if not isinstance(raw, dict):
        return raw
    return {k: v for k, v in raw.items() if k.lower() not in _SENSITIVE_RAW_KEYS}


LINKEDIN_ALIAS_RE = re.compile(r"^([a-zA-Z0-9-]+)$", re.IGNORECASE)
GENERIC_EMAIL_PREFIXES = ("contato", "comercial", "info", "contato@", "sac",
                          "vendas", "geral", "admin", "rh", "financeiro")
HUNTER_SEARCH_URL = "https://api.hunter.io/v2/domain-search"
HUNTER_FINDER_URL = "https://api.hunter.io/v2/email-finder"

# Item 4.7 — mais fontes de contato além da Receita:
# - `_EMAIL_FIND_RE`: extração de e-mails em texto livre (sem âncoras), com
#   de-ofuscação de padrões comuns (' [at] ', '(dot)', entidades HTML).
# - `_PHONE_FIND_RE`: telefones BR públicos (com DDD) nas páginas de contato.
_EMAIL_FIND_RE = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+",
)
_PHONE_RE_WITH_DDD = re.compile(r"(?:\(\d{2,3}\)|\b\d{2,3})\s*\d{4,5}[-\s]?\d{4}")
_PHONE_RE_RUN = re.compile(r"\d{10,11}")

CONTACT_PATHS = ("/", "/contato", "/fale-conosco", "/contact")


def _normalize_text(text: str) -> str:
    """Lowercase + remove acentos (para comparação de tokens de nome/e-mail)."""
    import unicodedata
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def _extract_emails_from_html(html: Optional[str]) -> List[str]:
    """Extrai e-mails de um HTML, desofuscando padrões anti-bot comuns.

    Trata ' [at] '/'[dot]' (e variantes entre parênteses), entidades HTML
    (`&#64;`/`&#46;`) e remove pontuação de frase dos arredores.
    """
    if not html:
        return []
    text = re.sub(r"\s*(?:\[|\()(?:at|dot)(?:\]|\))\s*",
                  lambda m: "@" if "at" in m.group(0).lower() else ".",
                  html, flags=re.IGNORECASE)
    text = text.replace("&#64;", "@").replace("&#46;", ".")
    emails: List[str] = []
    for em in _EMAIL_FIND_RE.findall(text):
        em = em.rstrip(".,;:)]}>\"'")
        if not is_valid_email_syntax(em):
            continue
        low = em.lower()
        if low not in emails:
            emails.append(low)
    return emails


def _extract_phone_from_html(html: Optional[str]) -> List[str]:
    """Extrai telefones BR válidos (10-11 dígitos, com DDD) do HTML."""
    if not html:
        return []
    phones: List[str] = []
    for m in _PHONE_RE_WITH_DDD.finditer(html):
        digits = "".join(ch for ch in m.group(0) if ch.isdigit())
        if len(digits) in (10, 11) and digits not in phones:
            phones.append(digits)
    for m in _PHONE_RE_RUN.finditer(html):
        digits = m.group(0)
        if digits not in phones:
            phones.append(digits)
    return phones


def _pick_site_email(site_emails: List[str], domain: Optional[str]) -> Tuple[Optional[str], int]:
    """Escolhe o melhor e-mail publicado no site para outreach.

    Prioriza e-mails do próprio domínio e prefixos não-genéricos (ex.: um
    'mariana@' em vez de 'comercial@'). E-mail genérico publicado (contato@/
    comercial@) fica com confidence 50-69 (regra de negócio); e-mail específico
    publicado sobe para 75.
    """
    if not site_emails:
        return None, 0
    domain_match = [e for e in site_emails if e.rsplit("@", 1)[-1] == domain] if domain else []
    candidates = domain_match or site_emails
    non_generic = [e for e in candidates if e.split("@")[0] not in GENERIC_EMAIL_PREFIXES]
    pick = non_generic[0] if non_generic else candidates[0]
    confidence = 75 if pick in domain_match and pick in non_generic else 69
    return pick, confidence


def _pick_email_for_name(candidates: List[str], name: Optional[str]) -> Optional[str]:
    """Escolhe dentre e-mails de uma página de busca aquele cujo local part
    combina com tokens do nome do decisor (ex.: joao.silva → 'joao'/'silva').
    """
    name = _normalize_text(name or "")
    tokens = set(re.findall(r"[a-z0-9]+", name))
    if not tokens:
        return None
    scored: List[Tuple[int, int, str]] = []
    for em in candidates:
        local_tokens = set(re.findall(r"[a-z0-9]+", em.split("@")[0].lower()))
        overlap = len(tokens & local_tokens)
        if overlap > 0:
            scored.append((overlap, len(em), em))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][2] if scored else None


def _domain_from_website(website: Optional[str]) -> Optional[str]:
    """Extrai o domínio de uma URL (ex.: https://www.firma.com.br → firma.com.br)."""
    if not website:
        return None
    url = website.strip().lower()
    url = re.sub(r"^[a-z]+://", "", url)
    url = url.split("/")[0].split("?")[0].split("#")[0]
    url = re.sub(r"^www\.", "", url)
    parts = url.split(".")
    if len(parts) >= 2 and parts[-1] in ("com", "net", "org", "br", "com.br",
                                         "net.br", "org.br", "co", "info",
                                         "gov", "edu", "io", "dev", "me"):
        return url
    return url


def _slugify_username(name: str) -> str:
    """Gera o slug do perfil LinkedIn a partir do nome (primeiro-ultimo)."""
    import unicodedata
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_name = "".join(c for c in normalized if not unicodedata.combining(c))
    cleaned = re.sub(r"[^\w\s]", "", ascii_name).strip().lower()
    parts = [p for p in re.split(r"\s+", cleaned) if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}-{parts[-1]}"


def _is_valid_linkedin_username(username: str) -> bool:
    return bool(username) and bool(LINKEDIN_ALIAS_RE.match(username))


def _build_linkedin_candidates(name: str) -> List[str]:
    """Monta URLs prováveis do perfil LinkedIn — variantes comuns."""
    slug = _slugify_username(name)
    if not slug:
        return []
    candidates = {slug}
    first = slug.split("-")[0]
    last = slug.split("-")[-1] if "-" in slug else slug
    candidates.add(f"{first}-{last}")
    return [f"https://www.linkedin.com/in/{c}" for c in candidates if _is_valid_linkedin_username(c)]


class ContactEnrichmentService:
    """Enriquece decisores com e-mail e LinkedIn (busca passiva, sem custo)."""

    def __init__(self):
        self.hunter_key: Optional[str] = getattr(settings, "HUNTER_API_KEY", None) or None
        self._http_cache: Dict[str, Optional[str]] = {}
        self._linkedin_validated: Dict[str, bool] = {}
        # Item 4.7 — cache das páginas do site (home + contato) p/ não refetch
        # na mesma rodada (até 3 paths por lead por enriquecimento).
        self._site_cache: Dict[str, Optional[str]] = {}

    def _create_client(self) -> httpx.AsyncClient:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
        return httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=headers)

    # ------------------------------------------------------------------ #
    # Orquestração
    # ------------------------------------------------------------------ #
    async def enrich_contacts(
        self,
        lead: Lead,
        db,
        cnpj: Optional[str] = None,
        max_contacts: int = 3,
    ) -> List[Dict[str, Any]]:
        """Enriquece os contatos de um lead (cria se não existirem).

        - Se o lead tem CNPJ (campo ou company_record), usa Receita Federal.
        - Para cada contato, tenta e-mail (Hunter → heurística) e LinkedIn
          (busca passiva → heurística + validação HEAD).
        - Atualiza `Contact` em upsert; retorna lista serializada.
        """
        existing = (db.query(Contact)
                    .filter(Contact.lead_id == lead.id)
                    .order_by(Contact.is_primary.desc())
                    .limit(max_contacts)
                    .all())

        if not existing:
            existing = await self._contacts_from_receita(lead, db, cnpj)

        results: List[Dict[str, Any]] = []
        async with self._create_client() as client:
            # Item 4.7 — e-mails/telefones públicos do site (página de contato)
            # são buscados UMA vez por lead e reaproveitados por todos os
            # contatos (evita N requisições por decisor).
            site_emails: List[str] = []
            site_phones: List[str] = []
            if lead.website:
                site_emails, site_phones = await self._emails_from_site(client, lead)

            for contact in existing[:max_contacts]:
                await self._enrich_email(client, contact, lead, site_emails, site_phones)
                if contact.email:
                    await self._verify_email(client, contact)
                await self._enrich_linkedin(client, contact, lead)
                contact.confidence = self._recalc_confidence(contact)
                results.append(self._contact_to_dict(contact))

        db.flush()
        return results

    # ------------------------------------------------------------------ #
    # Fonte primária de decisores: Receita Federal
    # ------------------------------------------------------------------ #
    async def _contacts_from_receita(
        self, lead: Lead, db, cnpj: Optional[str],
    ) -> List[Contact]:
        from services.cnpj_service import CnpjService

        target_cnpj = cnpj or (getattr(lead, "cnpj", None) or "")
        if not target_cnpj:
            # Sem CNPJ: cria um contato genérico com o nome do lead.
            generic = Contact(
                lead_id=lead.id,
                name=lead.company_name,
                role=ContactRole.OUTRO,
                role_label="Decisor",
                confidence=30,
                source="lead_name",
            )
            db.add(generic)
            db.flush()
            return [generic]

        svc = CnpjService()
        data = await svc.lookup(target_cnpj)
        contacts: List[Contact] = []
        company_email: Optional[str] = None
        company_phone: Optional[str] = None
        if data and data.get("company"):
            comp = data["company"] or {}
            company_email = (comp.get("email") or "").strip() or None
            company_phone = (comp.get("telefone") or "").strip() or None

        if data and data.get("contacts"):
            for c in data["contacts"]:
                role_enum = c.get("role_enum")
                contact = Contact(
                    lead_id=lead.id,
                    name=c.get("name") or "Decisor",
                    role=role_enum,
                    role_label=c.get("role_label") or role_enum,
                    document_cpf=c.get("document_cpf"),
                    confidence=c.get("confidence", 60),
                    is_primary=c.get("is_primary", False),
                    source=c.get("source") or "cnpj_receita",
                    raw_data=_sanitize_raw(c.get("raw")),
                )
                db.add(contact)
                contacts.append(contact)
        else:
            # CNPJ existe mas sem QSA disponível — fallback genérico.
            generic = Contact(
                lead_id=lead.id,
                name=lead.company_name,
                role=ContactRole.OUTRO,
                role_label="Decisor",
                confidence=30,
                source="cnpj_receita:fallback",
            )
            db.add(generic)
            contacts.append(generic)

        # Item 4.7 — e-mail/telefone cadastral da empresa (Receita) como fonte
        # extra de contato. Ficam em `raw_data`/`phone` para o `_enrich_email`
        # consumir na precedência (site → busca → CNPJ) e auditoria.
        if contacts and company_email:
            primary = contacts[0]
            primary.raw_data = {**(primary.raw_data or {}), "company_email": company_email.lower()}
        if contacts and company_phone:
            primary = contacts[0]
            if not primary.phone:
                primary.phone = company_phone
            primary.raw_data = {**(primary.raw_data or {}), "phone_source": "cnpj"}

        db.flush()
        return contacts

    # ------------------------------------------------------------------ #
    # E-mail: Hunter → site (contato) → busca → CNPJ → heurística (item 4.7)
    # ------------------------------------------------------------------ #
    async def _emails_from_site(
        self, client: httpx.AsyncClient, lead: Lead,
    ) -> Tuple[List[str], List[str]]:
        """E-mails/telefones publicados no site (página de contato) — item 4.7.

        GET passivo da home + caminhos comuns de contato (`/contato`,
        `/fale-conosco`, `/contact`); extrai `mailto:`/e-mails e telefones em
        texto, desofuscando padrões anti-bot. Nenhum probe/prova/injeção
        (Lei 12.737/2012): são páginas que qualquer visitante acessa.
        """
        if not lead.website:
            return [], []
        base = str(lead.website).strip()
        if not base.startswith(("http://", "https://")):
            base = f"https://{base}"
        emails: List[str] = []
        phones: List[str] = []
        visited: set = set()
        for path in CONTACT_PATHS:
            url = f"{base.rstrip('/')}{path}"
            if url in visited:
                continue
            visited.add(url)
            cache_key = f"site:{hashlib.md5(url.encode()).hexdigest()}"
            cached_html = self._site_cache.get(cache_key)
            if cached_html is None:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    cached_html = resp.text
                    self._site_cache[cache_key] = cached_html
                except httpx.RequestError as e:
                    logger.debug("Falha ao buscar página de contato %s: %s", url, e)
                    continue
            for em in _extract_emails_from_html(cached_html):
                if em not in emails:
                    emails.append(em)
            for ph in _extract_phone_from_html(cached_html):
                if ph not in phones:
                    phones.append(ph)
        return emails, phones

    async def _mail_to_company(
        self, client: httpx.AsyncClient, contact: Contact, lead: Lead,
    ) -> Tuple[Optional[str], int, str]:
        """Busca passiva por '<nome> ''<empresa>' email em buscador (item 4.7).

        Reusa a infraestrutura da busca de LinkedIn (DuckDuckGo HTML → Bing).
        Só roda quando o site não divulgou e-mail — limita requisições por rodada.
        """
        name = (contact.name or "").strip()
        company = (lead.company_name or "").strip()
        if not name or not company or name.lower() == company.lower():
            return None, 0, ""
        query = f'"{name}" "{company}" email'
        cache_key = f"em:{hashlib.md5(query.encode()).hexdigest()}"
        cached = self._http_cache.get(cache_key)
        if cached is not None:
            return cached, 60, "search:cached" if cached else ""

        for engine, params in (
            ("duckduckgo", {"q": query, "kl": "br-pt"}),
            ("bing", {"q": query, "count": 10, "mkt": "pt-BR"}),
        ):
            try:
                url = (
                    "https://html.duckduckgo.com/html/"
                    if engine == "duckduckgo"
                    else "https://www.bing.com/search"
                )
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    continue
                candidates = _extract_emails_from_html(resp.text)
                best = _pick_email_for_name(candidates, name)
                if best:
                    self._http_cache[cache_key] = best
                    return best, 60, f"search:{engine}"
            except Exception as e:
                logger.debug("Busca e-mail (%s) falhou para %s: %s", engine, name, e)

        self._http_cache[cache_key] = None
        return None, 0, ""

    async def _enrich_email(
        self, client: httpx.AsyncClient, contact: Contact, lead: Lead,
        site_emails: Optional[List[str]] = None, site_phones: Optional[List[str]] = None,
    ) -> None:
        if contact.email:
            return
        domain = _domain_from_website(lead.website)
        if not domain:
            return

        # 1) Hunter (opcional) — e-mail nomeado, o mais preciso quando existe.
        email, source, conf = await self._email_from_hunter(client, contact, lead, domain)
        if email and source == "hunter":
            self._apply_email(contact, email, "hunter", conf)
            return

        # 2) Site (página de contato) — publicamente divulgado, alta veracidade.
        site_email, site_conf = _pick_site_email(list(site_emails or []), domain)
        if site_email:
            self._apply_email(contact, site_email, "site", site_conf)
            if not contact.phone and site_phones:
                contact.phone = site_phones[0]
                contact.raw_data = {**(contact.raw_data or {}), "phone_source": "site"}
            return

        # 3) Busca passiva em buscador — '<nome> ''<empresa>' email.
        search_email, search_conf, search_src = await self._mail_to_company(
            client, contact, lead,
        )
        if search_email:
            self._apply_email(contact, search_email, search_src or "search", search_conf)
            return

        # 4) E-mail cadastral da empresa (CNPJ/Receita) — salvo em `company_email`.
        cnpj_email = (contact.raw_data or {}).get("company_email")
        if cnpj_email and is_valid_email_syntax(cnpj_email):
            self._apply_email(contact, cnpj_email, "cnpj", 60)
            return

        # 5) Heurística determinística (offline) — nome.sobrenome@dominio.
        heuristic_email, hconf = self._email_heuristic(contact, domain)
        if heuristic_email:
            contact.email = heuristic_email
            if not contact.source or contact.source.startswith("cnpj"):
                contact.source = f"{contact.source or 'cnpj_receita'}:heuristic"
            # Item 3.6: e-mail adivinhado é marcado como não verificado — nunca
            # deve cruzar o gate de outreach automático (confidence >= 50).
            contact.raw_data = {
                **(contact.raw_data or {}),
                "email_source": "heuristic",
                "email_verified": False,
            }

    def _apply_email(
        self, contact: Contact, email: str, source: str, confidence: int,
    ) -> None:
        """Aplica um e-mail encontrado + proveniência e ajusta a fonte do contato."""
        contact.email = email
        if not contact.source or contact.source.startswith("cnpj"):
            contact.source = f"{contact.source or 'cnpj_receita'}:{source}"
        contact.raw_data = {**(contact.raw_data or {}), "email_source": source}
        if confidence:
            contact.confidence = max(contact.confidence or 0, confidence)

    async def _verify_email(
        self, client: httpx.AsyncClient, contact: Contact,
    ) -> None:
        """Verifica a entregabilidade passiva do e-mail (roadmap 4.1).

        - E-mail **heurístico** (adivinhado) NUNCA é marcado verificado: mesmo
          que o domínio tenha MX, o padrão `nome.sobrenome@dominio` não foi
          confirmado — exige validação humana (evita bounce em massa).
        - Demais fontes (Hunter/CNPJ/site): marca `email_verified=True` só se
          o domínio tiver MX e não for descartável (fail-closed).
        - Guarda `email_mx`/`email_verify_reason` em `raw_data` para auditoria.
        """
        from services.email_verification_service import EmailVerificationService

        contact.raw_data = contact.raw_data or {}
        is_heuristic = contact.raw_data.get("email_source") == "heuristic"
        if is_heuristic:
            # Adivinhado: não comprova a caixa — mantém email_verified False.
            if not hasattr(contact, "email_verified"):
                return
            contact.email_verified = False
            return

        if not hasattr(contact, "email_verified"):
            return
        result = await EmailVerificationService().verify_email(contact.email, client=client)
        contact.raw_data = {
            **contact.raw_data,
            "email_mx": result.get("mx"),
            "email_verify_reason": result.get("reason"),
        }
        if result.get("verified"):
            contact.email_verified = True
            contact.email_verified_at = datetime.now(timezone.utc)

    async def _email_from_hunter(
        self, client: httpx.AsyncClient, contact: Contact, lead: Lead,
        domain: str,
    ) -> Tuple[Optional[str], str, int]:
        if not self.hunter_key or not contact.name:
            return None, "", 0
        try:
            resp = await client.get(
                HUNTER_FINDER_URL,
                params={
                    "domain": domain,
                    "full_name": contact.name,
                    "api_key": self.hunter_key,
                },
            )
            if resp.status_code == 200:
                payload = resp.json().get("data", {})
                email = payload.get("email")
                if email and is_valid_email_syntax(email):
                    return email, "hunter", int(payload.get("confidence", 90) or 90)
        except Exception as e:
            logger.debug("Hunter email-finder falhou para %s: %s", domain, e)
        return None, "", 0

    def _email_heuristic(
        self, contact: Contact, domain: str,
    ) -> Tuple[Optional[str], int]:
        name = (contact.name or "").strip()
        if not name:
            return None, 0
        parts = [p for p in re.split(r"\s+", _normalize_text(name)) if p]
        if len(parts) < 2:
            return None, 0
        first = re.sub(r"[^a-z0-9]", "", parts[0])
        last = re.sub(r"[^a-z0-9]", "", parts[-1])
        if not first or not last:
            return None, 0
        # confidence baixa — padrão inferido, não confirmado.
        heuristic = f"{first}.{last}@{domain}"
        return (heuristic, 40) if is_valid_email_syntax(heuristic) else (None, 0)

    # ------------------------------------------------------------------ #
    # LinkedIn: busca passiva → heurística + validação HEAD
    # ------------------------------------------------------------------ #
    async def _enrich_linkedin(
        self, client: httpx.AsyncClient, contact: Contact, lead: Lead,
    ) -> None:
        if contact.linkedin_url:
            return

        url, confidence, source = await self._linkedin_from_search(client, contact, lead)
        if url and confidence >= 50:
            contact.linkedin_url = url
            contact.linkedin_confidence = confidence
            contact.raw_data = {**(contact.raw_data or {}), "linkedin_source": source}
            return

        # Fallback por heurística de URL. Valida via índice de busca quando
        # possível; se o buscador estiver com rate-limit, retorna a URL com
        # confidence baixa ("não validada") para o humano decidir.
        candidate, candidate_conf = await self._linkedin_heuristic(client, contact)
        if candidate:
            contact.linkedin_url = candidate
            contact.linkedin_confidence = candidate_conf
            contact.raw_data = {**(contact.raw_data or {}), "linkedin_source": "heuristic"}

    async def _linkedin_from_search(
        self, client: httpx.AsyncClient, contact: Contact, lead: Lead,
    ) -> Tuple[Optional[str], int, str]:
        """Busca passiva em buscador por '<nome> <empresa> linkedin'.

        Tenta DuckDuckGo HTML (retorna URLs diretas) e cai para Bing quando
        o primeiro estiver com rate-limit (HTTP 202).
        """
        name = (contact.name or "").strip()
        if not name:
            return None, 0, ""
        company = lead.company_name or ""
        query = f"{name} {company} linkedin"
        cache_key = hashlib.md5(query.encode()).hexdigest()
        cached = self._http_cache.get(cache_key)
        if cached is not None:
            return cached, 80, "search:cached" if cached else ""

        for engine, params in (
            ("duckduckgo", {"q": query, "kl": "br-pt"}),
            ("bing", {"q": query, "count": 10, "mkt": "pt-BR"}),
        ):
            try:
                url = (
                    "https://html.duckduckgo.com/html/"
                    if engine == "duckduckgo"
                    else "https://www.bing.com/search"
                )
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    continue
                html = resp.text
                urls = re.findall(
                    r'(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+', html,
                )
                urls = [u if u.startswith("http") else f"https://{u}" for u in urls]
                if urls:
                    slug = _slugify_username(name)
                    parts = set(slug.split("-"))
                    scored = []
                    for u in urls:
                        uname = u.split("/in/")[1].split("?")[0]
                        u_parts = set(re.sub(r"[^a-z0-9-]", "", uname).split("-"))
                        overlap = len(parts & u_parts)
                        scored.append((overlap, len(uname), u))
                    scored.sort(key=lambda x: (-x[0], x[1]))
                    best = scored[0][2]
                    self._http_cache[cache_key] = best
                    return best, 75, f"search:{engine}"
            except Exception as e:
                logger.debug("Busca LinkedIn (%s) falhou para %s: %s", engine, name, e)

        self._http_cache[cache_key] = None
        return None, 0, ""

    async def _linkedin_heuristic(
        self, client: httpx.AsyncClient, contact: Contact,
    ) -> Tuple[Optional[str], int]:
        """Valida candidatos de URL via índice de busca (site:linkedin.com/in/{slug}).

        O LinkedIn bloqueia requisições diretas de bots (HTTP 999), então a
        validação é passiva: se o buscador indexou a URL do perfil, ela existe.
        Se o buscador estiver com rate-limit, retorna a URL com confidence
        baixa ("não validada") para o humano decidir.
        """
        candidates = _build_linkedin_candidates(contact.name or "")
        if not candidates:
            return None, 0

        first_candidate = candidates[0]
        username = first_candidate.split("/in/")[1]

        # 1) Busca em índice (valida existência)
        for engine, params in (
            ("duckduckgo", {"q": f'site:linkedin.com/in/ "{username}"', "kl": "br-pt"}),
            ("bing", {"q": f'site:linkedin.com/in/ "{username}"', "count": 10}),
        ):
            cache_key = f"in:{username}:{engine}"
            if cache_key in self._linkedin_validated:
                if self._linkedin_validated[cache_key]:
                    return first_candidate, 60
                continue
            try:
                url = (
                    "https://html.duckduckgo.com/html/"
                    if engine == "duckduckgo"
                    else "https://www.bing.com/search"
                )
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    continue
                html = resp.text
                exists = f"/in/{username}" in html
                self._linkedin_validated[cache_key] = exists
                if exists:
                    return first_candidate, 60
            except Exception:
                self._linkedin_validated[cache_key] = False

        # 2) Rate-limit/nenhuma evidência → NUNCA assume perfil se não foi confirmado passivamente
        return None, 0

    # ------------------------------------------------------------------ #
    # Confidence e serialização
    # ------------------------------------------------------------------ #
    def _recalc_confidence(self, contact: Contact) -> int:
        """Confiança agregada: base do contato + bônus de canais confirmados.

        Item 3.6 (auditoria): e-mail heurístico (adivinhado, `email_source ==
        "heuristic"`) NUNCA deixa a confiança cruzar o gate de outreach
        automático (>= 50) — o agregado é limitado a 40 para o humano decidir.
        """
        base = contact.confidence or 30
        if contact.email:
            if (contact.raw_data or {}).get("email_source") == "heuristic":
                base = min(base, 40)
            else:
                base = min(100, base + 10)
        if contact.linkedin_url:
            base = min(100, base + 10)
        return base

    def _contact_to_dict(self, c: Contact) -> Dict[str, Any]:
        return {
            "id": str(c.id),
            "name": c.name,
            "role": c.role.value if c.role else None,
            "role_label": c.role_label,
            "email": c.email,
            "phone": c.phone,
            "document_cpf": c.document_cpf,
            "confidence": c.confidence,
            "email_verified": c.email_verified if hasattr(c, "email_verified") else False,
            "email_verified_at": c.email_verified_at.isoformat() if hasattr(c, "email_verified_at") and c.email_verified_at else None,
            "linkedin_url": c.linkedin_url,
            "linkedin_confidence": c.linkedin_confidence,
            "is_primary": c.is_primary,
            "source": c.source,
            "raw_data": c.raw_data,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
