# Decisões Técnicas

Consulte este arquivo antes de modificar qualquer módulo.
Se uma decisão precisar ser revertida, documente aqui o motivo.

## Ativas

| Decisão | Motivo |
|---|---|
| Tudo async (httpx.AsyncClient) | Consistência entre serviços; enriquecimento é I/O-bound |
| httpx em vez de requests | Suporte nativo a async; escolha explícita do dev |
| Google Places API (New) em vez de scraping | Oficial, sem risco de bloqueio, dados estruturados |
| Groq para IA | Free tier generoso, latência baixa |
| llama-3.1-8b para scoring | Tarefa simples de classificação não precisa de 70B |
| llama-3.3-70b para mensagens | Geração de texto de qualidade exige modelo maior |
| PostgreSQL em vez de Mongo | Relacional, robusto, compartilhado entre workers e Next.js |
| Contacts como tabela separada de Lead | Um lead pode ter múltiplos decisores e fontes |
| raw_technical_data como JSONB | Permite reprocessar scoring sem revisitar o site |
| LinkedIn não automatizado | Risco de ban inaceitável; IA gera, humano envia |
| Scoring salvo mesmo se LLM falhar | Resiliência: dados técnicos não se perdem por falha de API |

## ADRs Detalhados

Ver `docs/decisions/` para o raciocínio completo de cada decisão.

| Decisão | Motivo |
|---|---|---|
| Credentials (email/senha) em vez de OAuth externo no MVP | OAuth exige domínio público e configuração externa; email/senha funciona localmente sem dependências; tabela users já existia com password_hash |
| JWT em vez de session cookies na API | Frontend NextAuth usa JWT strategy; API FastAPI valida o mesmo token para manter sessão consistente sem backend de sessão separado |
| bcrypt em vez de argon2 | bcrypt é suficiente para o caso de uso, tem suporte nativo em Python, e é mais simples de configurar sem dependências extras de sistema |

## ADRs de Segurança (Revisão 2026-07-09)

| Decisão | Motivo |
|---|---|
| `JWT_SECRET` deve ser configurado via pydantic-settings (`settings.py`), não via `os.getenv` direto | Consistência com workers (coding-standards.md); validação em startup (fail fast se env var faltar); facilita teste com injeção de config |
| Rate limiting em auth endpoints (login/register) | Prevenir brute force; implementar como middleware FastAPI (ex: `slowapi`) ou via nginx se em produção |
| WebSocket /ws/{job_id} requer autenticação | Impedir que terceiros escutem eventos de pipeline sem token válido |
| `getSession()` não deve ser chamado em toda request de API | Substituir por leitura do token do store Zustand ou cookie — `getSession()` faz fetch HTTP a cada chamada, dobrando latência |

## Comentários: português, mínimos e apenas quando necessário

A partir de 2026-07-09, todo o código usa:
- Comentários em português
- Apenas comentários necessários (obviedades como `// Leads` antes de `export function useLeads` foram removidos)
- Docstrings em português e apenas quando a função não é autoexplicativa

## Fixes Aplicados (2026-07-09)

| Decisão | Motivo |
|---|---|
| Extrair enrich+scoring para `enrichment_orchestrator.process_single_lead()` | Eliminar duplicação entre `main.py` e `pipeline_worker.py`; manutenção em um só lugar |
| slowapi para rate limiting | Biblioteca madura, decorator simples, suporte a Redis futuro |
| Token cache em memória no frontend | Elimina chamada HTTP `getSession()` em cada request de API; cache é populado após login/register |
| WebSocket auth via query param `?token=` | `WebSocket` browser não permite headers customizados; query param é o padrão da indústria |

## Issues Conhecidas (resolvidas)

Todas as 11 issues da revisão de segurança foram corrigidas. Ver `docs/roadmap.md` seção "Segurança & Qualidade de Código — Status ✅ Resolvido".