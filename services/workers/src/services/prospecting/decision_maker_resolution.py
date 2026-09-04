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

        # Determina status baseado na qualidade dos dados
        has_cpf = any(p.document_cpf for p in all_contacts)
        status = "resolved" if has_cpf else "partial"

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
        """Verifica email + identidade."""
        # Email verification
        email_verified = False
        if person.email and mock_mx_check and not self._is_heuristic_source(person):
            try:
                domain = person.email.split("@", 1)[-1].lower()
                email_verified = bool(mock_mx_check(domain))
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
            "verification_status": self._status(person, email_verified, identity_verified),
            "source": person.source,
            "has_email": bool(person.email),
            "has_cpf": bool(person.document_cpf),
        }

    def _is_heuristic_source(self, person: PersonContact) -> bool:
        return person.source == "heuristic" or "heuristic" in (person.source or "")

    def _status(
        self, person: PersonContact, email_verified: bool, identity_verified: bool,
    ) -> str:
        if email_verified and identity_verified:
            return "fully_verified"
        if identity_verified:
            return "identity_verified_no_email"
        if email_verified:
            return "email_verified_no_identity"
        if person.email or person.document_cpf:
            return "partial"
        return "no_email"
