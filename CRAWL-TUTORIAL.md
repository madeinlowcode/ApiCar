# Tutorial: Como Retomar e Operar o Crawl com Claude Code

Este documento serve como guia para o Claude Code operar o crawler do CatCar.
Leia este arquivo INTEIRO antes de executar qualquer comando.

---

## Visão Geral do Projeto

O CatCar é um crawler que extrai dados do site catcar.info (catálogo de peças automotivas).
Os dados são organizados em 6 níveis hierárquicos:

```
Level 1: Brands      (31+ marcas)
Level 2: Models      (modelos por marca/mercado)
Level 3: Years       (anos/variantes de cada modelo)
Level 4: Categories  (10 categorias de peças por ano)
Level 5: Subgroups   (subgrupos dentro de cada categoria)
Level 6: Parts       (peças individuais — objetivo final)
```

**Stack**: Python 3.12 + Playwright + SQLAlchemy async + PostgreSQL + Redis
**Containers**: docker-compose com 4 serviços (api, worker, postgres, redis)

---

## Arquitetura do Crawler

### Componentes Principais

| Arquivo | Função |
|---------|--------|
| `crawler/engine.py` | Orquestrador — processa URLs, detecta formato, chama parsers |
| `crawler/state.py` | Gerenciador de fila (crawl_queue no PostgreSQL) |
| `crawler/browser.py` | Pool de browsers Playwright |
| `crawler/rate_limiter.py` | Rate limiting (2-5s entre requests) |
| `run_crawl.py` | Script principal de execução com monitoramento |
| `crawler/parsers/` | Parsers por nível (homepage, brand_models, etc.) |

### Banco de Dados — Tabelas de Controle

**crawl_jobs**: Representa uma execução do crawl
- `id`, `status` (pending/running/completed/failed), `started_at`, `completed_at`

**crawl_queue**: Fila persistente de URLs para processar
- `id`, `job_id` (FK), `url`, `level` (1-6), `status` (pending/processing/done/failed)
- `retries` / `max_retries` (default 3)
- `parent_brand_id`, `parent_model_id`, etc. (contexto hierárquico)
- Usa `FOR UPDATE SKIP LOCKED` para claims atômicos

### Banco de Dados — Tabelas de Dados

```
brands → markets → models → model_years → parts_categories → subgroups → parts
```

Cada entidade tem `catalog_url` para referência ao site original.

---

## Como Verificar o Estado Atual

### 1. Verificar se os containers estão rodando

```bash
docker compose ps
```

Todos os 4 devem estar "Up": api, worker, postgres, redis.
Se algum estiver parado:

```bash
docker compose up -d
```

Para produção (VPS):
```bash
docker compose -f docker-compose.prod.yml up -d
```

### 2. Ver progresso do crawl

```bash
./scripts/status.sh
```

Ou modo contínuo (atualiza a cada 30s):
```bash
./scripts/status.sh --watch
```

### 3. Verificação manual via SQL

```bash
docker compose exec -T postgres psql -U catcar -c "
SELECT level,
       SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done,
       SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
       SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed
FROM crawl_queue
GROUP BY level ORDER BY level;
"
```

### 4. Ver dados coletados

```bash
docker compose exec -T postgres psql -U catcar -c "
SELECT relname AS tabela, n_live_tup AS linhas
FROM pg_stat_user_tables WHERE n_live_tup > 0 ORDER BY n_live_tup DESC;
"
```

### 5. Identificar o job_id atual

```bash
docker compose exec -T postgres psql -U catcar -tA -c "SELECT MAX(id) FROM crawl_jobs;"
```

---

## Como Retomar o Crawl

### Cenário 1: Crawl parou (máquina desligou, container reiniciou)

```bash
# 1. Garantir que containers estão rodando
docker compose up -d

# 2. Descobrir o job_id
JOB_ID=$(docker compose exec -T postgres psql -U catcar -tA -c "SELECT MAX(id) FROM crawl_jobs;")
echo "Job ID: $JOB_ID"

# 3. Retomar em background (detached)
docker compose exec -d -T worker python run_crawl.py --resume $JOB_ID --level 6
```

O `--resume` automaticamente:
- Reseta URLs stuck em "processing" (mais de 5 min) para "pending"
- Continua processando de onde parou

### Cenário 2: Restaurar de um backup

```bash
# 1. Restaurar o backup
./scripts/restore.sh backups/catcar_L4_complete_XXXX.sql.gz

# 2. Subir containers
docker compose up -d

# 3. Encontrar job_id e retomar
JOB_ID=$(docker compose exec -T postgres psql -U catcar -tA -c "SELECT MAX(id) FROM crawl_jobs;")
docker compose exec -d -T worker python run_crawl.py --resume $JOB_ID --level 6
```

### Cenário 3: Código foi atualizado (novo parser, fix de bug)

O container worker usa código COPIADO (não volume mount). Após alterar código:

```bash
# Opção A: Rebuild completo
docker compose down worker
docker compose build worker
docker compose up -d worker

# Opção B: Hot-copy (mais rápido, sem rebuild)
docker cp crawler/. api-car-worker-1:/app/crawler/
docker cp shared/. api-car-worker-1:/app/shared/
docker compose restart worker

# Depois retomar
JOB_ID=$(docker compose exec -T postgres psql -U catcar -tA -c "SELECT MAX(id) FROM crawl_jobs;")
docker compose exec -d -T worker python run_crawl.py --resume $JOB_ID --level 6
```

---

## Backups por Level

### Estratégia de segurança

Cada backup é um snapshot COMPLETO do banco. O nome indica o progresso:

```
catcar_L3_complete_1949done_2026-03-15_10-30.sql.gz  ← levels 1-3 completos
catcar_L4_complete_12000done_2026-03-16_08-00.sql.gz  ← levels 1-4 completos
```

### Fazer backup quando um level termina

```bash
./scripts/backup-level.sh           # Auto-detecta levels completos
./scripts/backup-level.sh --check   # Só mostra progresso, sem backup
./scripts/backup-level.sh --force   # Força backup mesmo incompleto
```

### Fluxo recomendado

1. `./scripts/status.sh` → verificar se level N está 100%
2. `./scripts/backup-level.sh` → gerar backup
3. Upload do `.sql.gz` para Google Drive (segurança)
4. Crawl continua automaticamente para o próximo level

### Restaurar de backup

```bash
./scripts/restore.sh backups/catcar_L4_complete_XXXX.sql.gz
```

⚠️ **ATENÇÃO**: o restore APAGA todo o banco atual e substitui pelo backup.
Sempre faça um backup do estado atual antes de restaurar outro.

---

## 3 Grupos de Marcas

### Grupo 1 — Compatíveis (21 marcas) ✅ CRAWL ATIVO
Volkswagen, Audi, Seat, Skoda, BMW, Mercedes, Toyota, Lexus, Ford, Opel,
Renault, Peugeot, Citroën, Fiat, Alfa Romeo, Lancia, Mitsubishi, Suzuki,
Mazda, Volvo, Porsche

Todas usam os parsers existentes. O crawl está rodando para estas.

### Grupo 2 — Year-First (8 marcas) 🔧 PARSER PENDENTE
Nissan, Subaru, Infiniti, Hyundai, Kia, Honda, Chrysler, Mazda(parcial)

Estas marcas têm seleção de ano ANTES do modelo (invertido).
Precisa do `YearFirstParser` — ainda não implementado.

### Grupo 3 — Especiais (3 marcas) 🔍 INVESTIGAÇÃO PENDENTE
Dacia, Vauxhall, Jaguar

Layout diferente dos demais, precisa investigação individual.

---

## Detecção Automática de Formato (Level 3)

O `engine.py` detecta 4 formatos diferentes no level 3 pelo h1 da página:

| h1 | Formato | Exemplo | Handler |
|----|---------|---------|---------|
| (tabela anos) | VW-style: tabela com anos | VW, BMW, Toyota | `ModelYearsParser` |
| "Main groups" | Ford-style: sem anos, direto categorias | Ford | `_handle_no_year_page()` |
| "Main group" | Mercedes-style: sem anos, categorias em tabela | Mercedes | `_handle_no_year_table_categories()` |
| "Model" + columnheader | Mitsubishi-style: sub-modelos | Mitsubishi | `_handle_submodel_page()` |

Para marcas sem seleção de ano, o sistema cria um `model_year` sintético (year=0).

---

## Solução de Problemas

### Crawl parou e não retoma
```bash
# Verificar se há items em "processing" (stuck)
docker compose exec -T postgres psql -U catcar -c "
SELECT COUNT(*) FROM crawl_queue WHERE status='processing';
"

# Reset manual se necessário
docker compose exec -T postgres psql -U catcar -c "
UPDATE crawl_queue SET status='pending', retries=retries
WHERE status='processing' AND processed_at < NOW() - INTERVAL '10 minutes';
"
```

### Muitos erros em um level
```bash
# Ver erros recentes
docker compose exec -T postgres psql -U catcar -c "
SELECT level, LEFT(error_message, 100) AS erro, COUNT(*)
FROM crawl_queue WHERE status='failed'
GROUP BY level, LEFT(error_message, 100)
ORDER BY COUNT(*) DESC LIMIT 10;
"

# Reprocessar items com erro (dar mais uma chance)
docker compose exec -T postgres psql -U catcar -c "
UPDATE crawl_queue SET status='pending', retries=0
WHERE status='failed' AND level=3;
"
```

### Container worker usando muita memória
```bash
# Ver uso de recursos
docker stats --no-stream

# Reiniciar worker
docker compose restart worker
```

### Ver logs do worker em tempo real
```bash
docker compose logs -f worker --tail 100
```

---

## Variáveis de Ambiente

```bash
DATABASE_URL=postgresql+asyncpg://catcar:catcar@postgres:5432/catcar
REDIS_URL=redis://redis:6379/0
ADMIN_API_KEY=change-me-in-production
LOG_LEVEL=INFO
```

Para local: as credenciais default são `catcar:catcar`.
Para VPS: o script `vps-setup.sh` gera senhas aleatórias no `.env`.

---

## Estimativas

| Level | URLs estimadas | Tempo estimado | Tamanho DB |
|-------|---------------|----------------|------------|
| 1-2 | ~200 | ~15 min | ~2 MB |
| 3 | ~6.000 | ~8 horas | ~5 MB |
| 4 | ~30.000 | ~24 horas | ~20 MB |
| 5 | ~500.000 | ~1 semana | ~2 GB |
| 6 | ~10.000.000 | ~3 semanas | ~57 GB |

Rate limiting: ~20 URLs/min (2-5s delay entre requests).

---

## Resumo de Comandos Essenciais

```bash
# Status
./scripts/status.sh                    # Dashboard completo
./scripts/status.sh --watch            # Monitoramento contínuo

# Backup
./scripts/backup-level.sh             # Backup quando level completa
./scripts/backup-level.sh --check     # Só ver progresso
./scripts/backup.sh                    # Backup genérico

# Retomar crawl
JOB_ID=$(docker compose exec -T postgres psql -U catcar -tA -c "SELECT MAX(id) FROM crawl_jobs;")
docker compose exec -d -T worker python run_crawl.py --resume $JOB_ID --level 6

# Restaurar backup
./scripts/restore.sh backups/<arquivo>.sql.gz

# Logs
docker compose logs -f worker --tail 100
```
