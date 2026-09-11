---
name: provider-integration
description: Criar ou evoluir integração com provider externo para discovery, people, enrichment, email, events, jobs, technographics ou intent. Use para HTTP APIs, adapters, quotas, waterfall, retries, provenance, observabilidade e custo.
---
# Provider Integration

Provider é substituível: external API → adapter → canonical result → registry/waterfall → domain.

Defina capability, custo, quota, latência, reliability, coverage, regiões, credenciais e rate limits.

Estados explícitos: ok, empty, failed, timeout, disabled, quota_exceeded, budget_exceeded, invalid_request, configuration_error.

Segurança: nunca logar token; SSRF protection quando aplicável; validar redirects/domain; limitar resposta; timeout; parsing defensivo; nenhuma coleta invasiva.

Resiliência: retry só se retryable, backoff/jitter quando adequado, idempotência e controle de custo.

Provenance deve responder provider, query lógica, timestamp, id externo, confidence, status, custo e regra de merge.

Waterfall: cheap/free → deterministic filter → paid. Early stop pelos gates do OfferProfile.

Testes com fake adapter: mapping, empty, invalid, timeout, quota, retry, cost, dedupe, provenance, tenant opt-in, early stop.
