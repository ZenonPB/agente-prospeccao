# Padrões de Código

## Obrigatórios

- Todo código Python deve ser **async** (usar `async def` + `httpx.AsyncClient`)
- Nunca usar `requests` — usar `httpx`
- Nunca usar `print` — usar `logging`
- Funções com mais de 60 linhas devem ser quebradas
- Todo método público deve ter docstring com Args e Returns
- Tratar exceções de forma granular — nunca `except Exception` sem log
- Usar `try/except/finally` em todas as sessões de banco de dados
- Visar sempre a segurança do sistema, tanto quanto utilizar das melhores práticas e padrões de código para manutenções futuras.
- Nunca commitar chaves de API ou credenciais de acesso ao sistema.
- Nunca commitar arquivos .env, .env.local, .env.*
- Não utilizar variáveis globais desnecessariamente.
- Não utilizar importações absolutas que não sejam necessárias. 

## Banco de Dados

- Nunca alterar migrations antigas — sempre criar nova migration
- Nunca remover colunas em produção — marcar como deprecated primeiro
- Sempre usar SQLAlchemy 2 (não declarative_base legado quando possível)
- Sessões de banco sempre fechadas no `finally`
- Filtros SQLAlchemy usam `&` e `|` — nunca `and`/`or` Python

## Estrutura de Serviços

- Um arquivo por serviço em `src/services/`
- Classe nomeada `XService` (ex: `AIScoringService`)
- Método principal claramente nomeado (ex: `score_lead`, `enrich_website`)
- Serviços não importam outros serviços — orquestração em `enrichment_orchestrator.py`
  (que liga `technical_enrichment_service` + `scoring_service`) ou em `main.py`;
  import cruzado entre serviços é a exceção, não a regra
- Retornar `None` em caso de falha, nunca lançar exceção para o caller

## Variáveis de Ambiente

- Toda config via `settings.py` (pydantic-settings)
- Nunca acessar `os.environ` diretamente nos serviços
- Nunca commitar `.env`

## Testes

- Criar teste para cada serviço novo em `tests/`
- Mockar chamadas externas (Groq, Google, httpx)
- Testar cenário de falha além do caminho feliz