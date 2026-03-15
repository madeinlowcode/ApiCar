#!/usr/bin/env bash
# ============================================================================
# restore.sh — Restaurar backup do PostgreSQL
#
# Uso:
#   ./scripts/restore.sh backups/catcar_full_2026-03-14_15-30.sql.gz
#   ./scripts/restore.sh backups/catcar_data_2026-03-14_15-30.sql.gz
#
# Restaura no container postgres local (ou da VPS).
# ============================================================================
set -euo pipefail

BACKUP_FILE="${1:-}"

if [[ -z "$BACKUP_FILE" ]]; then
    echo "Uso: $0 <backup_file.sql.gz>"
    echo ""
    echo "Backups disponíveis:"
    ls -lh backups/*.sql.gz 2>/dev/null || echo "  Nenhum backup encontrado em ./backups/"
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "Erro: Arquivo não encontrado: $BACKUP_FILE"
    exit 1
fi

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

DB_CONTAINER="${DB_CONTAINER:-api-car-postgres-1}"
DB_USER="${DB_USER:-catcar}"
DB_NAME="${DB_NAME:-catcar}"

echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       RESTORE — CatCar Database              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo -e "  Arquivo: ${CYAN}${BACKUP_FILE}${NC}"
echo -e "  Tamanho: ${CYAN}${FILE_SIZE}${NC}"
echo ""

# Confirmar
echo -e "${RED}ATENÇÃO: Isso vai SUBSTITUIR todos os dados existentes no banco!${NC}"
read -p "Continuar? (y/N): " confirm
if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
    echo "Cancelado."
    exit 0
fi

echo ""
echo -e "${YELLOW}→ Parando worker (se rodando)...${NC}"
docker compose stop worker 2>/dev/null || true

echo -e "${YELLOW}→ Limpando banco existente...${NC}"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c "
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();
" > /dev/null 2>&1 || true

docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c "
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME OWNER $DB_USER;
" 2>/dev/null

echo -e "${YELLOW}→ Restaurando backup...${NC}"
gunzip -c "$BACKUP_FILE" | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" --quiet

echo ""
echo -e "${GREEN}✓ Restore concluído!${NC}"

# Mostrar estado
echo ""
echo -e "${YELLOW}→ Estado do banco restaurado:${NC}"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
    schemaname || '.' || relname AS tabela,
    n_live_tup AS linhas
FROM pg_stat_user_tables
WHERE n_live_tup > 0
ORDER BY n_live_tup DESC;
"

echo -e "${YELLOW}→ Progresso da queue:${NC}"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT level,
       SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done,
       SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending
FROM crawl_queue
GROUP BY level ORDER BY level;
" 2>/dev/null || echo "  (sem dados de queue — backup era --tables-only)"

echo ""
echo -e "${GREEN}Para retomar o crawl:${NC}"
echo -e "  docker compose up -d"
echo -e "  docker compose exec -d -T worker python run_crawl.py --resume <JOB_ID> --level 6"
