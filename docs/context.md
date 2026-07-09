# agente-prospeccao — Context

> Leia este arquivo primeiro. Ele indica o que ler em seguida.

## Leitura obrigatória antes de qualquer tarefa

1. `docs/architecture.md` — estrutura do sistema, stack, serviços
2. `docs/business-rules.md` — regras de negócio, pipeline, status dos leads
3. `docs/roadmap.md` — o que está pronto, em andamento e planejado

## Consulte antes de modificar

- `docs/decisions.md` — decisões técnicas tomadas e motivos
- `docs/coding-standards.md` — padrões obrigatórios de código
- `docs/agents.md` — regras específicas para agentes de IA

## Estado atual (atualizar a cada sessão)

### Pronto ✅
- `places_service.py` — coleta via Google Places API (async)
- `technical_enrichment_service.py` — análise passiva de sites (async)
- `scoring_service.py` — qualificação via Groq (llama-3.1-8b-instant)
- `models.py` — todos os modelos, migration rodada com `raw_technical_data`
- `main.py` — `run_enrichment_and_scoring` integrado com scoring
- Filtro de duplicata corrigido (usa `&` SQLAlchemy)

### Em andamento 🟡
- Nenhum no momento

### Pendências conhecidas
- `technical_enrichment_service.py`: AsyncClient instanciado no `__init__` (deveria ser por uso)

### Próximo passo imediato
1. Criar `src/services/contact_enrichment_service.py` (fase 2)
2. Criar `src/services/outreach_service.py` (fase 3)
3. Criar frontend Next.js (fase 2)