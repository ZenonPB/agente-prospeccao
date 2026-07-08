# Regras para Agentes de IA

> Este arquivo é lido pelo agente no início de cada sessão.
> Seguir estas regras sem exceção.

## Antes de qualquer tarefa

1. Ler `docs/context.md` completo
2. Ler os arquivos indicados como obrigatórios
3. Fazer `/add` dos arquivos relevantes para a tarefa
4. Confirmar o entendimento da tarefa antes de escrever código

## O que nunca fazer

- Nunca usar `requests` — sempre `httpx`
- Nunca usar `print` — sempre `logging`
- Nunca alterar migrations existentes
- Nunca remover colunas do banco
- Nunca criar funções síncronas em serviços (tudo `async`)
- Nunca modificar arquivos fora do escopo da tarefa
- Nunca instalar dependências sem perguntar primeiro
- Nunca inventar APIs ou endpoints — consultar docs reais
- Nunca usar `and`/`or` Python em filtros SQLAlchemy — usar `&`/`|`
- Nunca commitar `.env` ou chaves de API

## O que sempre fazer

- Executar o código após escrever e mostrar o output
- Atualizar `docs/context.md` ao final da sessão
- Preservar docstrings existentes ao refatorar
- Criar testes para código novo
- Perguntar antes de tomar decisões arquiteturais
- Reportar pendências encontradas nos arquivos existentes

## Como entregar uma tarefa

1. Escrever o código
2. Executar e mostrar output
3. Se houver erro, corrigir antes de entregar
4. Listar arquivos modificados
5. Sugerir atualização do `docs/context.md`

## Contexto do projeto

- Stack Python: async, httpx, SQLAlchemy, pydantic-settings, Groq, PostgreSQL
- Próximo passo: ver seção "Próximo passo imediato" em `docs/context.md`
- Dúvidas arquiteturais: consultar `docs/decisions.md` antes de propor mudanças