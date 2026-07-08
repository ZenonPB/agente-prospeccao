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
- `models.py` — todos os modelos, migration rodada com `raw_technical_data`

### Em andamento 🟡
- `scoring_service.py` — qualificação via Groq (a criar)
- `main.py` — `run_enrichment_and_scoring` aguarda scoring

### Pendências conhecidas
- `places_service.py`: `search_places` ainda é síncrono, main chama com `await`
- `main.py`: filtro de duplicata usa `and` Python em vez de `&` SQLAlchemy
- `main.py`: scoring não integrado ainda (TODO no código)
- `technical_enrichment_service.py`: AsyncClient instanciado no `__init__`

### Próximo passo imediato
1. Criar `src/services/scoring_service.py` com `AIScoringService`
2. Corrigir `places_service.py` para async
3. Corrigir bug do filtro de duplicata no `main.py`
4. Integrar scoring em `run_enrichment_and_scoring`