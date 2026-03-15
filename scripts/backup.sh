#!/usr/bin/env bash
# ============================================================================
# backup.sh — Backup do banco PostgreSQL local
#
# Uso:
#   ./scripts/backup.sh                    # Backup completo
#   ./scripts/backup.sh --tables-only      # Só tabelas de dados (sem crawl_queue)
#
# Gera arquivo em: ./backups/catcar_YYYY-MM-DD_HH-MM.sql.gz
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuração do banco (pode vir de .env)
DB_CONTAINER="${DB_CONTAINER:-api-car-postgres-1}"
DB_USER="${DB_USER:-catcar}"
DB_NAME="${DB_NAME:-catcar}"

TABLES_ONLY=false
if [[ "${1:-}" == "--tables-only" ]]; then
    TABLES_ONLY=true
fi

mkdir -p "$BACKUP_DIR"

echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         BACKUP — CatCar Database             ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# Mostrar estado atual do banco
echo -e "${YELLOW}→ Estado atual do banco:${NC}"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
    schemaname || '.' || relname AS tabela,
    n_live_tup AS linhas
FROM pg_stat_user_tables
WHERE n_live_tup > 0
ORDER BY n_live_tup DESC;
"

echo -e "${YELLOW}→ Tamanho do banco:${NC}"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT pg_size_pretty(pg_database_size('$DB_NAME')) AS tamanho;
"

# Gerar backup
if $TABLES_ONLY; then
    BACKUP_FILE="${BACKUP_DIR}/catcar_data_${TIMESTAMP}.sql.gz"
    echo -e "${YELLOW}→ Backup apenas dados (sem crawl_queue/crawl_jobs)...${NC}"
    docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" \
        --no-owner --no-privileges \
        --exclude-table='crawl_queue' \
        --exclude-table='crawl_jobs' \
        | gzip > "$BACKUP_FILE"
else
    BACKUP_FILE="${BACKUP_DIR}/catcar_full_${TIMESTAMP}.sql.gz"
    echo -e "${YELLOW}→ Backup completo (com queue de crawl)...${NC}"
    docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" \
        --no-owner --no-privileges \
        | gzip > "$BACKUP_FILE"
fi

# Verificar resultado
FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo ""
echo -e "${GREEN}✓ Backup concluído!${NC}"
echo -e "  Arquivo: ${CYAN}${BACKUP_FILE}${NC}"
echo -e "  Tamanho: ${CYAN}${FILE_SIZE}${NC}"
echo ""

# Mostrar progresso da queue (se existe)
echo -e "${YELLOW}→ Progresso da crawl_queue:${NC}"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT level,
       SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done,
       SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
       SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed
FROM crawl_queue
GROUP BY level
ORDER BY level;
" 2>/dev/null || echo "  (sem dados de queue)"

echo ""
echo -e "${GREEN}Para restaurar na VPS:${NC}"
echo -e "  scp ${BACKUP_FILE} user@vps:/opt/catcar/backups/"
echo -e "  ssh user@vps 'cd /opt/catcar && ./scripts/restore.sh backups/$(basename $BACKUP_FILE)'"
