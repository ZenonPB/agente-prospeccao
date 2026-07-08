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