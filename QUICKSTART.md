# Guia de Inicialização - Agente Prospecção

> **Modo automático (Windows, sem Docker):** o jeito mais fácil é dar **duplo
> clique em `scripts\setup.cmd`** (setup completo uma única vez) e depois em
> **`scripts\dev.cmd`** (sobe tudo). Ou rode manualmente:
> `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1` e depois
> `.\scripts\dev.ps1 start`. O setup baixa um PostgreSQL embarcado (sem instalar
> nada), cria os venvs, gera o `.env`/`.env.local` com segredos automáticos, roda
> migrations e seed. Pule os passos 1–2 abaixo se usou o modo automático.

## Passo 1: Iniciar o Docker Desktop

Antes de rodar o script, você precisa **iniciar o Docker Desktop manualmente**:

1. Abra o **Docker Desktop** (ícone na área de trabalho ou menu Iniciar)
2. Aguarde até aparecer "Docker Desktop is running" na barra de tarefas
3. Confirme que está rodando executando:
   ```powershell
   docker ps
   ```

## Passo 2: Configurar o Banco de Dados

Se é a **primeira vez** rodando o sistema, execute estas etapas:

### 2.1 Subir o PostgreSQL
```powershell
docker-compose up -d db
```

### 2.2 Rodar as Migrações
```powershell
cd services\workers
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
```

### 2.3 Popular Templates de Scoring (opcional mas recomendado)
```powershell
python -m src.seeds.scoring_templates
```

## Passo 3: Iniciar o Sistema

Agora sim, rode o script de desenvolvimento:

```powershell
cd ..\..  # Voltar para a raiz do projeto
.\scripts\dev.ps1 start
```

O script abrirá duas janelas:
- **Janela 1**: API FastAPI rodando em `http://localhost:8000`
- **Janela 2**: Frontend Next.js rodando em `http://localhost:3001`

## Passo 4: Acessar o Sistema

1. Abra o navegador em: **http://localhost:3001**
2. Clique em **"Cadastre-se grátis"**
3. Crie sua conta (será o owner da organização)
4. Pronto! Você pode começar a criar campanhas de prospecção

---

## Comandos Úteis

### Ver status dos serviços
```powershell
.\scripts\dev.ps1 status
```

### Parar todos os serviços
```powershell
.\scripts\dev.ps1 stop
```

### Reiniciar tudo
```powershell
.\scripts\dev.ps1 restart
```

### Ver logs do PostgreSQL
```powershell
docker-compose logs db
```

### Acessar o banco diretamente
```powershell
docker exec -it agente-prospeccao-db-1 psql -U postgres -d agente_prospeccao
```

---

## Solução de Problemas Comuns

### Erro: "não existe a coluna follow_ups.attempts"
**Causa**: Migração pendente do banco de dados.  
**Solução**: Execute `alembic upgrade head` na pasta `services/workers` (veja Passo 2.2)

### Erro: "failed to connect to docker API"
**Causa**: Docker Desktop não está rodando.  
**Solução**: Inicie o Docker Desktop e aguarde aparecer "running" na bandeja do sistema.

### API não inicia ou dá erro de imports
**Causa**: Dependências não instaladas ou venv não ativado.  
**Solução**: 
```powershell
cd services\api
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Web não carrega ou mostra erro 500
**Causa**: Frontend não consegue conectar na API.  
**Solução**: Verifique se `apps/web/.env.local` tem `NEXT_PUBLIC_API_URL=http://localhost:8000`

### Porta 8000 ou 3001 já está em uso
**Solução**: 
```powershell
# Descobrir qual processo está usando a porta 8000
netstat -ano | findstr :8000

# Matar o processo (substitua <PID> pelo número da coluna PID)
taskkill /PID <PID> /F
```

---

## Estrutura de Diretórios

```
agente-prospeccao/
├── .env                          # Configurações gerais (GROQ, Google, Hunter.io)
├── apps/
│   └── web/
│       ├── .env.local            # Configurações do Next.js (NextAuth)
│       └── src/                  # Código do frontend
├── services/
│   ├── api/                      # FastAPI REST + WebSocket
│   │   ├── venv/                 # Ambiente virtual Python
│   │   └── main.py               # Ponto de entrada da API
│   └── workers/                  # Coleta/Enriquecimento/Scoring
│       ├── venv/                 # Ambiente virtual Python
│       ├── migrations/           # Migrações Alembic
│       └── src/
│           ├── main.py           # Script de worker
│           └── seeds/            # Seeds do banco
└── scripts/
    └── dev.ps1                   # Script de inicialização Windows
```
