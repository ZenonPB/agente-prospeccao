# Fix: Detecção de plataformas SaaS de terceiros no scoring

> **Status: ✅ Entregue (2026-09-01, branch `fix/scoring-erp-webapps`).**
> Todas as mudanças listadas abaixo foram implementadas — ver também a sessão
> correspondente em `docs/context.md` ("scoring de ERP/webapps corrigido").
> A entrega cobriu as 5 mudanças previstas **e ampliou** o template
> "Aplicações Web / ERP" com sinais cadastrais (porte, idade, CNAE, capital
> social) que estavam faltando para a venda B2B de sistemas web completos.

## Problema

A IA de scoring não reconhecia que leads já usam plataformas de pedidos (anota.ai, iFood, etc.). Tratava `pedido.anota.ai` como "site próprio do lead" e gerava facts falsos ("área logada detectada", "menção a sistema"), fazendo o LLM concluir que o lead tem "processos manuais que podem ser automatizados" — quando na verdade ele JÁ tem solução digital.

**Exemplo concreto:** Restaurante Terraço com `https://pedido.anota.ai/loja/restaurante-novo-terrao` recebia score 85 com reasoning: "O site institucional não apresenta portal ou área logada, e não menciona nenhum sistema ou ERP, indicando processos manuais que podem ser automatizados." — completamente errado, pois o lead já usa anota.ai para pedidos.

## Plataformas reconhecidas

anota.ai, iFood (com e sem subdomínio de pedidos), Rappi, Aimpire, Pedidos Já, Pedidosky.

## Plataformas a reconhecer

anota.ai, iFood, Rappi, Aimpire, Pedidos Já, Pedidosky

---

## Mudança 1 — `domain_utils.py`: Adicionar plataformas SaaS

**Arquivo:** `services/workers/src/services/domain_utils.py`

### Adicionar a `_MARKETPLACE_DOMAINS` (linha ~46):

```python
_MARKETPLACE_DOMAINS = {
    "instadelivery.com.br",
    "ifood.com.br",
    "pedidosja.com.br",
    "cardapioja.com",
    "deliveryextra.com",
    "menuqr.com.br",
    "foodzap.com.br",
    # --- novos ---
    "anota.ai",
    "ifood.com",
    "rappi.com",
    "aimpire.com",
    "pedidosky.com.br",
}
```

### Adicionar a `_SUBDOMAIN_SOCIAL_ROOTS` (linha ~59):

```python
_SUBDOMAIN_SOCIAL_ROOTS = (
    "whatsapp.com",
    "wa.me",
    "canva.com",
    "canva.link",
    "instagram.com",
    # --- novos ---
    "anota.ai",
    "ifood.com",
    "rappi.com",
    "aimpire.com",
    "pedidosky.com.br",
)
```

**Efeito:** `normalize_domain("https://pedido.anota.ai/loja/...")` → `None`. O lead é tratado como "sem site próprio" para dedupe.

---

## Mudança 2 — `technical_enrichment_service.py`: Não falsificar `login_portal_found`

**Arquivo:** `services/workers/src/services/technical_enrichment_service.py`

No `_check_ux()` (linha ~303), antes de checar `login_portal_found`, verificar se o host é de terceiros:

```python
def _check_ux(self, html_content: Optional[str], website_url: Optional[str] = None) -> Dict[str, Any]:
    # ...现有代码...

    # NOVO: se o website é de plataforma SaaS de terceiros, NÃO detectar
    # login_portal_found nem system_mention_found — esses pertencem ao
    # SaaS, não ao lead.
    from services.domain_utils import _clean_domain, _is_non_own_website_domain
    host = _clean_domain(website_url) if website_url else None
    is_third_party = _is_non_own_website_domain(host) if host else False

    if not is_third_party:
        result["login_portal_found"] = bool(
            re.search(
                r'login|área\s+do\s+cliente|área\s+do\s+aluno|'
                r'portal\s+do\s+(cliente|aluno)|meu\s+painel|'
                r'[\'"](?:/)?(?:login|painel|area-do-cliente|portal)[/\'"]',
                html_lower,
            )
        )
    # else: login_portal_found permanece False (default)

    if not is_third_party:
        result["system_mention_found"] = bool(
            re.search(r'\bsistema\b|\berp\b|\bsoftware\b', html_lower)
        )
    # else: system_mention_found permanece False (default)
```

**Atenção:** O método `_check_ux` precisa receber `website_url` como parâmetro. Verificar onde é chamado em `enrich_website()` e passar a URL.

**Efeito:** Facts "Área logada/portal/painel presente" e "Menção a sistema/ERP/software" NÃO são gerados para leads que usam plataformas de terceiros.

---

## Mudança 3 — `scoring_service.py`: Novo fact determinístico

**Arquivo:** `services/workers/src/services/scoring_service.py`

Em `extract_technical_facts()` (linha ~455), adicionar após os facts de UX:

```python
# NOVO: Detectar se o website é plataforma SaaS de terceiros
from services.domain_utils import _clean_domain, _is_non_own_website_domain
website_url = report.get("_website_url")  # precisa ser passado no report
host = _clean_domain(website_url) if website_url else None
if host and _is_non_own_website_domain(host):
    platform_name = _SAAS_PLATFORM_NAMES.get(host.split(".")[-2] + "." + host.split(".")[-1], host)
    facts.append(
        f"Lead usa plataforma SaaS de terceiros: {platform_name} "
        f"(domínio {host} não pertence ao lead — é storefront/plataforma de pedidos)"
    )
```

Também criar um dict de mapeamento de nomes legíveis:

```python
_SAAS_PLATFORM_NAMES = {
    "anota.ai": "Anota AI",
    "ifood.com": "iFood",
    "rappi.com": "Rappi",
    "aimpire.com": "Aimpire",
    "pedidosky.com.br": "Pedidosky",
}
```

**Atenção:** O report precisa conter a URL original do website para que a detecção funcione. Verificar se `enrichment_orchestrator` já passa a URL no report.

**Efeito:** O LLM recebe: "Lead usa plataforma SaaS de terceiros: Anota AI (domínio pedido.anota.ai não pertence ao lead — é storefront/plataforma de pedidos)"

---

## Mudança 4 — `scoring_service.py`: Instrução no prompt de scoring

**Arquivo:** `services/workers/src/services/scoring_service.py`

No `build_prompt()` (linha ~426), adicionar nova instrução #8b após a #8 existente:

```python
# Após a instrução #8 (linha ~442):
lines.append("8b. Se o fact 'Lead usa plataforma SaaS de terceiros' estiver presente, o lead JÁ utiliza")
lines.append("    solução digital para parte de suas operações (ex.: pedidos online via anota.ai, iFood).")
lines.append("    Isso NÃO é 'processo manual' — avalie:")
lines.append("    - Se o serviço vendido é COMPLEMENTAR ao SaaS (ERP integrado, gestão completa),")
lines.append("      o fato de já usar tecnologia é sinal POSITIVO (lead aberto a ferramentas digitais).")
lines.append("    - Se o serviço vendido SUBSTITUI o SaaS, o lead precisa de motivo forte para trocar")
lines.append("      (integração, custo, funcionalidade ausente). Não assuma que o SaaS atual é insuficiente.")
lines.append("    - NUNCA sugira 'automatizar processos manuais' quando o lead já usa plataforma digital.")
```

**Efeito:** O LLM para de sugerir "processos manuais" para leads que já têm sistema.

---

## Mudança 5 — `scoring_templates.py`: Sinal no template "Aplicações Web / ERP"

**Arquivo:** `services/workers/src/seeds/scoring_templates.py`

Na lista `negative_signals` do template "Aplicações Web / ERP" (linha ~146), adicionar:

```python
{
    "label": "Lead já usa plataforma SaaS de pedidos/delivery",
    "description": "anota.ai, iFood, Rappi, Pedidosky, Aimpire etc. — lead já tem solução digital parcial; precisa de motivo forte para migrar",
    "weight_hint": "medium",
},
```

**Efeito:** O template orienta o LLM a considerar a plataforma existente como fator de redução de score.

---

## Arquivos afetados

| # | Arquivo | Mudança |
|---|---|---|
| 1 | `services/workers/src/services/domain_utils.py` | +6 domínios em `_MARKETPLACE_DOMAINS`, +5 raízes em `_SUBDOMAIN_SOCIAL_ROOTS` |
| 2 | `services/workers/src/services/technical_enrichment_service.py` | `login_portal_found/system_mention_found` = False para domínios de terceiros; passar `website_url` para `_check_ux()` |
| 3 | `services/workers/src/services/scoring_service.py` | Novo fact SaaS + instrução #8b no prompt + `_website_url` no report |
| 4 | `services/workers/src/seeds/scoring_templates.py` | Sinal negativo no template "Aplicações Web / ERP" |

## Ordem de execução

1. `domain_utils.py` (base — todos os outros dependem disso)
2. `technical_enrichment_service.py` (usa `domain_utils`)
3. `scoring_service.py` (usa facts limpos)
4. `scoring_templates.py` (independente, mas coeso com as mudanças)

## Riscos / considerações

- Leads que **realmente** têm sistema próprio (domínio próprio + área logada) continuam sendo detectados normalmente — a mudança só afeta domínios de terceiros
- `ifood.com.br` já existe em `_MARKETPLACE_DOMAINS`; `ifood.com` (raiz) precisa ser adicionada a `_SUBDOMAIN_SOCIAL_ROOTS` para cobrir `pedidos.ifood.com.br`
- A detecção de `login_portal_found` para domínios de terceiros precisa usar o host da URL do lead, não o `website` armazenado no banco
- O report técnico precisa passar a URL original do website para que `extract_technical_facts()` possa checar o domínio
- Testar com: `https://pedido.anota.ai/loja/restaurante-novo-terrao`, `https://pedidos.ifood.com.br/loja/...`, `https://www.rappi.com.br/...`
