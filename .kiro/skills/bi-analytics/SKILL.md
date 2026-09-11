---
name: bi-analytics
description: Projetar ou implementar métricas, BI, dashboards, filtros cruzados, funil, provider analytics, TAM, attribution e learning analytics. Use em services/api analytics e apps/web relatórios/dashboard.
---
# BI & Analytics

Antes de criar gráfico, defina grain, numerator, denominator, time field, dimensions, tenant scope, unknown e attribution.

Dimensões: organization, offer/profile/version, campaign, segment, geography, provider, source, owner, channel, stage, period, persona.

Métricas:
Coverage: company_match_rate, person_match_rate, actionable_contact_rate, verified_email_rate/phone_rate.
Quality: duplicate_rate, stale_rate, bounce_rate, wrong_person_rate.
Commercial: reply, positive_reply, meeting, proposal, win, revenue.
Intelligence: Precision@K, signal_lift, intent_lift.
Cost: cost_per_candidate/qualified/actionable/meeting/won.

Sample size sempre visível. Zero != ausência. Evite double counting. Revenue deve ser atribuído à opportunity/offer/version correta. Snapshots históricos não devem ser reescritos por regra nova.

Teste semântica com fixtures pequenas e números calculáveis à mão.
