# Data Engine — preparação remota e runbook do piloto real

> **RUNBOOK · 2026-09-18.** Este documento separa o que pode ser preparado sem arquivos reais do que exige ação do operador em uma máquina com espaço, rede e PostgreSQL.

## Objetivo

Deixar o Data Engine pronto para que, ao voltar ao computador, a única etapa manual relevante seja obter os arquivos oficiais do snapshot escolhido e executar o procedimento reproduzível. O primeiro piloto permanece sem outreach e sem provider pago.

## Cenário congelado do primeiro piloto

- Vertente: Landing Pages;
- segmento: clínicas de psicologia;
- CNAE: 8650-0/03;
- município: Araraquara/SP;
- código IBGE: 3503208;
- situação: ativa;
- fontes externas pagas: desabilitadas;
- Commercial Dimensions: shadow;
- outreach: desabilitado;
- objetivo: validar o Data Engine, não produzir 20 leads artificialmente.

## O que pode ser concluído sem dados reais

Pode ser feito em CI/fixtures/revisão estática:

- contrato de snapshot, manifest, scope, staging, membership e ativação;
- validação de filtros CNAE/UF/município/situação;
- testes de CNPJ numérico e alfanumérico conforme contrato implementado;
- fail-closed para mês inexistente/RUNNING/FAILED;
- idempotência e concorrência;
- smoke sintético do recorte Araraquara;
- garantia de custo externo R$0 no piloto;
- documentação e checklist;
- inspeção de índices/query-count;
- garantia de que o snapshot filtrado não se apresenta como nacional;
- definição do relatório final e critérios de decisão.

Não pode ser honestamente concluído sem dados reais:

- compatibilidade do parser com o snapshot oficial escolhido;
- quantidade real de empresas;
- cobertura e qualidade de CNAE secundário;
- falsos positivos/negativos reais;
- tamanho final em disco e tempo real de ingestão;
- comportamento do Registry com distribuição real;
- qualidade real de entity resolution;
- cobertura real de sites/pessoas/contatos;
- evidência comercial/conversão.

## Arquivos mínimos

O operador deve primeiro resolver o snapshot oficial e inspecionar o conteúdo disponível. Para o contrato atual:

- **Estabelecimentos** é obrigatório para descobrir CNPJ completo, CNAE, situação e geografia;
- **Empresas** é necessário quando o piloto pretende enriquecer razão social/porte/capital no mesmo snapshot;
- **CNAE** fornece labels/descrições; o código de CNAE do filtro não depende da label para funcionar.

Não baixar arquivos adicionais como Sócios/Simples apenas por completude. O piloto deve obedecer minimização. Se a distribuição oficial continuar particionada em múltiplos ZIPs de Estabelecimentos/Empresas, o filtro local reduz **persistência**, não necessariamente **download**: é preciso processar as partições que possam conter linhas do município/CNAE, porque a partição não é assumida como geográfica.

## Procedimento quando estiver no computador

1. Atualizar a branch/HEAD candidato e confirmar working tree limpa.
2. Resolver uma única vez o snapshot oficial mais recente disponível e congelar `AAAA-MM`.
3. Registrar origem oficial e data de acesso. Não usar espelho silenciosamente.
4. Baixar somente as famílias necessárias ao contrato acima e extrair em `dados-registry/` (gitignored).
5. Gerar/validar `manifest.json` com mês, layout, encoding, origem, tamanho e SHA-256 de cada arquivo.
6. Subir PostgreSQL 16 e aplicar migrations até o head; repetir `alembic upgrade head` para provar idempotência.
7. Importar **sem ativar** com o escopo `UF=SP, municipio=3503208, CNAE=8650-0/03, situação=ativa`.
8. Conferir ledger, rejects, staging, scope persistido e contagens antes da ativação.
9. Executar smoke explicitamente preso ao snapshot solicitado.
10. Revisar uma amostra manual de empresas antes de tornar o snapshot ACTIVE.
11. Ativar explicitamente. Confirmar que health e busca default resolvem exatamente o ACTIVE.
12. Rodar discovery Registry do cenário e auditar entity resolution/deduplicação.
13. Só então habilitar Public Web no limite configurado, mantendo paid providers e outreach desligados.
14. Registrar latência, bytes, tamanho de banco, candidatos, principais/secundários, materializações, duplicatas, falhas e custo externo.
15. Encerrar com exatamente uma decisão: `PILOT DATA PIPELINE VALIDATED`, `PILOT NEEDS FIXES` ou `PILOT BLOCKED`.

## Comandos-base

Executar de `services/workers`, adaptando nomes de arquivos ao snapshot real:

```bash
alembic upgrade head
alembic upgrade head

python -m src.scripts.import_registry \
  --snapshot-month AAAA-MM \
  --manifest ../../dados-registry/manifest.json \
  --estabelecimentos ../../dados-registry/<estabelecimentos...> \
  --empresas ../../dados-registry/<empresas...> \
  --cnaes ../../dados-registry/<cnaes...> \
  --uf SP \
  --municipio-cod 3503208 \
  --cnae 8650-0/03 \
  --situacao 02
```

Não adicionar `--activate` na primeira passagem. A ativação deve ocorrer somente depois da auditoria pré-ACTIVE.

## Evidência a registrar

O relatório do piloto precisa distinguir:

- **download size**: bytes dos arquivos oficiais obtidos;
- **raw/extracted size**: bytes após extração;
- **database size**: crescimento real do PostgreSQL;
- **working-set memory**: pico de memória do processo;
- **tempo**: download, parse/import, ativação e busca;
- **qualidade**: candidatos, ativos, CNAE principal/secundário, falsos positivos, duplicatas, rejeições;
- **custo externo**: esperado R$0 no cenário; qualquer chamada paga é falha do piloto;
- **provenance**: snapshot, manifest/hash, scope, source e observed_at.

## Stop conditions

Parar e não “consertar para passar” quando ocorrer:

- layout/encoding oficial divergir do parser;
- manifest/hash/tamanho não bater;
- scope não persistir corretamente;
- snapshot RUNNING/FAILED aparecer na busca;
- ACTIVE anterior for degradado por carga falha;
- filtro CNAE/município produzir varredura ampla inesperada;
- merge de Company por identidade fraca;
- provider pago executar sem autorização;
- `UNKNOWN` virar negativo;
- custo/memória/tempo incompatíveis com a operação.

Achado P1 interrompe o piloto. P2 gera micro-PR antes de continuar. P3 vira evidência/backlog salvo se invalidar a medição.

## Depois do piloto

Somente após o gold standard real:

1. comparar alternativas de discovery remoto, se ainda fizer sentido;
2. decidir o ADR de arquitetura híbrida;
3. avaliar BigQuery/remote provider com a mesma consulta e mesma coorte;
4. comparar cobertura, missing/extra CNPJs, status/CNAE, freshness, latência, bytes e custo;
5. decidir provider de produção sem tornar “free” uma premissa arquitetural.

Até essa comparação, o bulk Registry continua referência e BigQuery permanece hipótese de arquitetura, não dependência da 1.0.
