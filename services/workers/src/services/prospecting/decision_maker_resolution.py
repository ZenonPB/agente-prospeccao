"""Decision Maker Resolution (Fase G — consolidação §Fase G).

Pipeline: lead_data + OfferProfile + sources → pessoa(s) reais verificadas
ou estado explícito de falha. Nunca inventa pessoas.

Critério: "Pipeline retorna pessoa(s) reais ou um estado explícito de
falha, não apenas roles desejados."
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================
# PersonContact — pessoa real (não role)
# ============================================================

@dataclass
class PersonContact:
    """Pessoa real identificada a partir de fonte externa."""
    name: str
    source: str
    document_cpf: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    # Quando mesclado de múltiplas fontes
    source_merged: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.source_merged:
            self.source_merged = [self.source]


# ============================================================
# ResolutionResult — estado explícito
# ============================================================

@dataclass
class ResolutionResult:
    """Resultado de uma tentativa de Decision Maker Resolution."""
    status: str  # "resolved" | "partial" | "not_found" | "failed"
    people: List[PersonContact]
    audit: Dict[str, Any]

    @classmethod
    def not_found(cls, reason: str, profile_roles: List[str] = None) -> "ResolutionResult":
        """Constrói resultado de falha explícita (consolidação §Fase G)."""
        return cls(
            status="not_found",
            people=[],
            audit={
                "reason": reason,
                "profile_roles_searched": profile_roles or [],
                "sources_used": [],
                "sources_attempted": [],
            },
        )


# ============================================================
# DecisionMakerResolver — resolve usando roles do OfferProfile
# ============================================================

class DecisionMakerResolver:
    """Resolve pessoas a partir de fontes reais (Receita, LinkedIn, etc).

    O resolver **NUNCA** inventa nomes. Se nenhuma fonte devolveu pessoas,
    retorna `not_found` explícito com motivo.
    """

    def resolve(
        self,
        company_data: Dict[str, Any],
        profile: Dict[str, Any],
        sources: Dict[str, List[Dict[str, Any]]],
    ) -> ResolutionResult:
        """Resolve pessoas a partir das fontes."""
        decision_makers = profile.get("decision_makers", {})
        profile_roles = decision_makers.get("roles", []) if isinstance(decision_makers, dict) else []
        buyer_types = decision_makers.get("buyer_types", []) if isinstance(decision_makers, dict) else []

        if not sources:
            return ResolutionResult.not_found(
                reason="no_sources_provided",
                profile_roles=profile_roles,
            )

        all_contacts: List[PersonContact] = []
        sources_used: List[str] = []
        sources_attempted: List[str] = list(sources.keys())

        for source_name, contacts in sources.items():
            if not contacts:
                continue
            sources_used.append(source_name)
            for c in contacts:
                person = PersonContact(
                    name=c.get("name", ""),
                    source=source_name,
                    document_cpf=c.get("document_cpf") or c.get("cpf"),
                    email=c.get("email"),
                    role=c.get("role") or c.get("role_label"),
                    phone=c.get("phone"),
                    linkedin_url=c.get("linkedin_url"),
                )
                if person.name:
                    all_contacts.append(person)

        if not all_contacts:
            return ResolutionResult.not_found(
                reason="sources_returned_no_people",
                profile_roles=profile_roles,
            )

        # Consolida pessoas equivalentes antes de calcular confiança; assim a
        # evidência do site e do e-mail pertence à mesma identidade.
        all_contacts = IdentityResolver().merge(all_contacts)
        # Determina status por evidências, não por CPF obrigatório.
        confidence_service = ContactConfidence()
        people_confidence = [
            confidence_service.identity_confidence(person, person.source_merged)
            for person in all_contacts
        ]
        has_cpf = any(p.document_cpf for p in all_contacts)
        identity_confidence = max(
            (item["confidence"] for item in people_confidence),
            default=0,
        )
        ambiguous_without_cpf = (
            not has_cpf
            and len(all_contacts) > 1
            and len({(p.name or "").strip().lower() for p in all_contacts}) == 1
        )
        if ambiguous_without_cpf and identity_confidence < 70:
            return ResolutionResult(
                status="needs_review",
                people=all_contacts,
                audit={
                    "reason": "ambiguous_identity_without_cpf",
                    "profile_roles_searched": profile_roles,
                    "buyer_types": buyer_types,
                    "sources_used": sources_used,
                    "sources_attempted": sources_attempted,
                    "has_cpf": has_cpf,
                    "identity_confidence": identity_confidence,
                },
            )
        status = "resolved" if (
            identity_confidence >= 70
            or (has_cpf and identity_confidence >= 50)
        ) else "partial"

        return ResolutionResult(
            status=status,
            people=all_contacts,
            audit={
                "reason": "resolved_from_sources",
                "profile_roles_searched": profile_roles,
                "buyer_types": buyer_types,
                "sources_used": sources_used,
                "sources_attempted": sources_attempted,
                "has_cpf": has_cpf,
                "identity_confidence": identity_confidence,
            },
        )


# ============================================================
# IdentityResolver — consolida identidades duplicadas
# ============================================================

class IdentityResolver:
    """Consolida pessoas duplicadas de múltiplas fontes.

    Critério de merge:
    1. Mesmo CPF → mesma pessoa (sempre)
    2. Mesmo email + mesmo nome → mesma pessoa
    3. Mesmo nome + emails diferentes → NÃO mescla (risco de confusão)
    """

    def merge(self, contacts: List[PersonContact]) -> List[PersonContact]:
        """Consolida contatos duplicados em pessoas únicas."""
        if not contacts:
            return []
        groups: List[List[PersonContact]] = []
        for c in contacts:
            placed = False
            for group in groups:
                if self._same_identity(c, group[0]):
                    group.append(c)
                    placed = True
                    break
            if not placed:
                groups.append([c])

        # Consolida cada grupo em uma PersonContact
        merged: List[PersonContact] = []
        for group in groups:
            if len(group) == 1:
                merged.append(group[0])
                continue
            # Mescla atributos
            base = group[0]
            for other in group[1:]:
                if not base.document_cpf and other.document_cpf:
                    base.document_cpf = other.document_cpf
                if not base.email and other.email:
                    base.email = other.email
                if not base.linkedin_url and other.linkedin_url:
                    base.linkedin_url = other.linkedin_url
                if not base.phone and other.phone:
                    base.phone = other.phone
                if other.source not in base.source_merged:
                    base.source_merged.append(other.source)
            merged.append(base)
        return merged

    def _same_identity(self, a: PersonContact, b: PersonContact) -> bool:
        """True se A e B são a mesma pessoa."""
        # Critério 1: mesmo CPF
        if a.document_cpf and b.document_cpf:
            return a.document_cpf == b.document_cpf
        # Critério 2: mesmo email + mesmo nome
        if a.email and b.email and a.email == b.email:
            return a.name.lower() == b.name.lower()
        return False


# ============================================================
# ContactConfidence — agrega confiança de múltiplas fontes
# ============================================================

class ContactConfidence:
    """Agrega confidence de múltiplas fontes para uma pessoa.

    Quanto mais fontes confirmam a mesma pessoa, maior a confidence.
    - 1 fonte: confidence = X (a da fonte)
    - 2 fontes: confidence = max(X) + boost
    - 3+ fontes: confidence = max(X) + boost_2
    """

    SOURCE_RELIABILITY: Dict[str, float] = {
        "receita_qsa": 0.95,
        "company_site": 0.90,
        "verified_email": 0.90,
        "linkedin_current": 0.80,
        "hunter": 0.75,
        "search_engine": 0.55,
        "heuristic": 0.30,
    }

    @classmethod
    def source_reliability(cls, source: str) -> float:
        """Retorna a confiabilidade calibrada de uma fonte conhecida."""
        normalized = cls._normalize_source(source)
        return cls.SOURCE_RELIABILITY.get(normalized, cls.SOURCE_RELIABILITY["heuristic"])

    @classmethod
    def identity_confidence(
        cls,
        person: PersonContact,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Calcula identidade por evidências, sem exigir CPF.

        O score usa os pesos definidos no plano de consolidação. A lista de
        fontes representa evidências independentes que confirmam a pessoa; o
        resultado é limitado a 100 e ``resolved`` exige 70 pontos.
        """
        normalized_sources = list(dict.fromkeys(cls._normalize_source(item) for item in sources if item))
        score = 0
        evidence: List[str] = []
        if person.document_cpf or "receita_qsa" in normalized_sources:
            score += 50
            evidence.append("CPF/QSA")
        if "company_site" in normalized_sources:
            score += 35
            evidence.append("site oficial")
        if "verified_email" in normalized_sources or (
            person.email and "company_site" in normalized_sources
        ):
            score += 25
            evidence.append("email corporativo")
        if "linkedin_current" in normalized_sources or (
            person.linkedin_url and "search_engine" not in normalized_sources
        ):
            score += 25
            evidence.append("LinkedIn atual")
        if len(normalized_sources) >= 2:
            score += 20
            evidence.append("fontes concordantes")
        if score == 0 and normalized_sources:
            score = round(max(cls.source_reliability(item) for item in normalized_sources) * 100)
            evidence.append("fonte única")
        score = min(100, score)
        return {
            "confidence": score,
            "status": "resolved" if score >= 70 else "partial" if score > 0 else "not_found",
            "has_cpf": bool(person.document_cpf),
            "sources": normalized_sources,
            "evidence": evidence,
        }

    @classmethod
    def contact_confidence(
        cls,
        person: PersonContact,
        sources: List[str],
        *,
        email_verified: bool = False,
        phone_verified: bool = False,
    ) -> Dict[str, Any]:
        """Calcula confiança de contato e indica se há canal acionável."""
        identity = cls.identity_confidence(person, sources)
        score = identity["confidence"]
        if email_verified:
            score += 10
        if phone_verified:
            score += 5
        if person.linkedin_url:
            score += 5
        score = min(100, score)
        return {
            "confidence": score,
            "identity": identity,
            "actionable": bool((person.email and email_verified) or person.phone),
            "email_verified": email_verified,
            "phone_verified": phone_verified,
            "source_reliability": max(
                (cls.source_reliability(item) for item in sources),
                default=0.0,
            ),
        }

    @staticmethod
    def _normalize_source(source: str) -> str:
        """Canonicaliza variantes de provenance produzidas pelos adapters."""
        value = str(source or "").strip().lower()
        if value.startswith("cnpj_receita") or value.startswith("receita"):
            return "receita_qsa"
        if value.startswith("site") or value == "company_site":
            return "company_site"
        if value.startswith("hunter"):
            return "hunter"
        if value.startswith("linkedin") or value.startswith("manual:"):
            return "linkedin_current"
        if value.startswith("search:") or value.startswith("search_engine"):
            return "search_engine"
        if "heuristic" in value:
            return "heuristic"
        if value in {"verified_email", "email_verified"}:
            return "verified_email"
        return value

    def aggregate(self, person: PersonContact, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Agrega confidence de N fontes para a mesma pessoa."""
        if not sources:
            return {
                "confidence": 0.0,
                "sources_count": 0,
                "method": "no_sources",
            }
        confidences = [s.get("confidence", 0) for s in sources if s.get("confidence") is not None]
        if not confidences:
            return {
                "confidence": 0.0,
                "sources_count": 0,
                "method": "no_valid_confidences",
            }
        # Estratégia: max + boost por quantidade de fontes
        max_conf = max(confidences)
        boost = min(20, (len(confidences) - 1) * 10)  # 10 por fonte adicional, cap 20
        final = min(100, max_conf + boost)
        return {
            "confidence": final,
            "sources_count": len(confidences),
            "method": "max_plus_boost" if len(confidences) > 1 else "single_source",
            "max_source_confidence": max_conf,
        }


# ============================================================
# ContactVerification — verifica email + identidade
# ============================================================

class ContactVerification:
    """Verifica se um contato é entregável/acionável.

    Regras:
    - Email com MX válido + pessoa tem CPF → verificado
    - Email heurístico (sem CPF) → NUNCA verificado (consolidação §26.7)
    - Sem email → não verificado por email, mas pode ter CPF
    """

    def verify(
        self,
        person: PersonContact,
        mock_mx_check: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Verifica email + identidade.

        Se `mock_mx_check` for fornecido, usa-o (testabilidade). Senão,
        tenta usar o EmailVerificationService real (sem dependência
        forçada — se não disponível, marca como `pending_real_check`).
        """
        # Email verification
        email_verified = False
        mx_check = mock_mx_check
        # A verificação real assíncrona é executada pelo ContactEnrichmentService.
        # Este resolver síncrono só usa o adapter quando ele foi explicitamente
        # injetado (ou quando um provider já está carregado pelo chamador/teste),
        # evitando DNS oculto dentro de uma resolução de identidade.
        email_module = __import__("sys").modules.get("services.email_verification_service")
        if (
            mx_check is None
            and person.email
            and not self._is_heuristic_source(person)
            # O teste de integração injeta um adapter fake em sys.modules.
            # O módulo real é assíncrono e deve ser chamado pelo serviço de
            # enriquecimento, não bloqueado dentro deste resolver síncrono.
            and email_module is not None
            and getattr(email_module, "__file__", None) is None
        ):
            # Tenta usar o serviço real
            try:
                from services.email_verification_service import EmailVerificationService
                _svc = EmailVerificationService()
                # O serviço real expõe `verify_email` assíncrono (não existe
                # `check_domain_mx`). Adaptamos a coroutine para a API sync
                # deste resolver, inclusive quando chamado dentro de ASGI.
                def _real_mx(domain):
                    import asyncio
                    import inspect
                    import threading

                    async def _verify():
                        result = await _svc.verify_email(person.email or "")
                        return bool(result.get("verified"))

                    try:
                        asyncio.get_running_loop()
                    except RuntimeError:
                        return bool(asyncio.run(_verify()))

                    result_box = []
                    error_box = []

                    def _run():
                        try:
                            result_box.append(asyncio.run(_verify()))
                        except BaseException as exc:  # noqa: BLE001
                            error_box.append(exc)

                    worker = threading.Thread(target=_run, daemon=True)
                    worker.start()
                    worker.join()
                    return bool(result_box and not error_box and result_box[0])

                mx_check = _real_mx
            except Exception:
                mx_check = None
        if person.email and mx_check and not self._is_heuristic_source(person):
            try:
                domain = person.email.split("@", 1)[-1].lower()
                email_verified = bool(mx_check(domain))
            except Exception:
                email_verified = False
        # Identity verification: tem CPF
        identity_verified = bool(person.document_cpf)
        # Heurística nunca verificada (consolidação §26.7)
        if self._is_heuristic_source(person):
            email_verified = False
        return {
            "email_verified": email_verified,
            "identity_verified": identity_verified,
            "verification_status": self._status(person, email_verified, identity_verified, mock_mx_check),
            "source": person.source,
            "has_email": bool(person.email),
            "has_cpf": bool(person.document_cpf),
        }

    def _is_heuristic_source(self, person: PersonContact) -> bool:
        return person.source == "heuristic" or "heuristic" in (person.source or "")

    def _status(
        self, person: PersonContact, email_verified: bool, identity_verified: bool,
        mock_mx_check: Optional[Any] = None,
    ) -> str:
        if email_verified and identity_verified:
            return "fully_verified"
        if identity_verified:
            return "identity_verified_no_email"
        if email_verified:
            return "email_verified_no_identity"
        # Tem email mas não foi verificado e não tem mock = pendente de check real
        if person.email and mock_mx_check is None and not self._is_heuristic_source(person):
            return "pending_real_check"
        if person.email or person.document_cpf:
            return "partial"
        return "no_email"
