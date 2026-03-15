#!/usr/bin/env bash
# ============================================================================
# backup-level.sh — Backup inteligente por level do crawl
#
# Uso:
#   ./scripts/backup-level.sh              # Detecta levels prontos e faz backup
#   ./scripts/backup-level.sh --force      # Força backup mesmo com levels em andamento
#   ./scripts/backup-level.sh --check      # Só mostra o progresso, sem fazer backup
#
# Gera: ./backups/catcar_L{N}_{done}done_{timestamp}.sql.gz
# Estratégia: cada backup é COMPLETO (snapshot do banco inteiro)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Detectar compose file
COMPOSE_FILE=""
if [[ -f "${PROJECT_DIR}/docker-compose.prod.yml" ]] && docker compose -f "${PROJECT_DIR}/docker-compose.prod.yml" ps -q postgres &>/dev/null; then
    COMPOSE_FILE="-f docker-compose.prod.yml"
fi

DB_CONTAINER="${DB_CONTAINER:-$(cd "$PROJECT_DIR" && docker compose $COMPOSE_FILE ps -q postgres 2>/dev/null || echo 'api-car-postgres-1')}"
DB_USER="${DB_USER:-catcar}"
DB_NAME="${DB_NAME:-catcar}"

MODE="${1:-auto}"

mkdir -p "$BACKUP_DIR"

echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║          BACKUP POR LEVEL — CatCar                      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Coletar progresso de cada level ─────────────────────────────
LEVEL_STATS=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tA -c "
SELECT
    level,
    SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done,
    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
    SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS processing,
    COUNT(*) AS total
FROM crawl_queue
GROUP BY level
ORDER BY level;
")

# Mostrar progresso
echo -e "${YELLOW}▸ Progresso atual:${NC}"
echo -e "  ${BOLD}Level   Done      Pending   Processing  Total     Status${NC}"
echo -e "  ────── ──────── ──────── ────────── ──────── ──────────"

MAX_COMPLETE_LEVEL=0
CURRENT_LEVEL=0

while IFS='|' read -r level done pending processing total; do
    [[ -z "$level" ]] && continue

    if [[ "$pending" -eq 0 && "$processing" -eq 0 && "$done" -gt 0 ]]; then
        status="${GREEN}✓ COMPLETO${NC}"
        if [[ "$level" -gt "$MAX_COMPLETE_LEVEL" ]]; then
            MAX_COMPLETE_LEVEL=$level
        fi
    elif [[ "$done" -gt 0 ]]; then
        pct=$(echo "scale=1; $done * 100 / $total" | bc)
        status="${YELLOW}⟳ ${pct}%${NC}"
        if [[ "$CURRENT_LEVEL" -eq 0 ]]; then
            CURRENT_LEVEL=$level
        fi
    else
        status="  aguardando"
    fi

    LEVEL_NAME=""
    case $level in
        1) LEVEL_NAME="Brands" ;;
        2) LEVEL_NAME="Models" ;;
        3) LEVEL_NAME="Years" ;;
        4) LEVEL_NAME="Categories" ;;
        5) LEVEL_NAME="Subgroups" ;;
        6) LEVEL_NAME="Parts" ;;
    esac

    printf "  L%-5s %-8s %-8s %-10s %-8s %b\n" \
        "${level}(${LEVEL_NAME})" "$done" "$pending" "$processing" "$total" "$status"
done <<< "$LEVEL_STATS"

echo ""

# Tabelas de dados
echo -e "${YELLOW}▸ Dados coletados:${NC}"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT relname AS tabela, n_live_tup AS linhas
FROM pg_stat_user_tables
WHERE n_live_tup > 0 AND schemaname = 'public'
ORDER BY n_live_tup DESC;
"

DB_SIZE=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tA -c "
SELECT pg_size_pretty(pg_database_size('$DB_NAME'));
")
echo -e "  Tamanho do banco: ${CYAN}${DB_SIZE}${NC}"
echo ""

# ── Modo check: só mostra, não faz backup ──────────────────────
if [[ "$MODE" == "--check" ]]; then
    if [[ $MAX_COMPLETE_LEVEL -gt 0 ]]; then
        echo -e "${GREEN}Levels 1-${MAX_COMPLETE_LEVEL} estão completos. Pronto para backup.${NC}"
    else
        echo -e "${YELLOW}Nenhum level totalmente completo ainda.${NC}"
    fi
    exit 0
fi

# ── Decidir se faz backup ──────────────────────────────────────
if [[ "$MODE" != "--force" ]]; then
    if [[ $MAX_COMPLETE_LEVEL -eq 0 ]]; then
        echo -e "${YELLOW}Nenhum level novo completo. Use --force para backup mesmo assim.${NC}"
        exit 0
    fi
fi

# Determinar label do backup
if [[ $MAX_COMPLETE_LEVEL -gt 0 ]]; then
    LABEL="L${MAX_COMPLETE_LEVEL}_complete"
else
    LABEL="L${CURRENT_LEVEL}_partial"
fi

# Contar total de registros done
TOTAL_DONE=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tA -c "
SELECT COUNT(*) FROM crawl_queue WHERE status='done';
" | tr -d '[:space:]')

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
BACKUP_FILE="${BACKUP_DIR}/catcar_${LABEL}_${TOTAL_DONE}done_${TIMESTAMP}.sql.gz"

echo -e "${YELLOW}→ Gerando backup: ${CYAN}$(basename $BACKUP_FILE)${NC}"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" \
    --no-owner --no-privileges \
    | gzip > "$BACKUP_FILE"

FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ BACKUP CONCLUÍDO                                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Arquivo:  ${CYAN}$(basename $BACKUP_FILE)${NC}"
echo -e "  Tamanho:  ${CYAN}${FILE_SIZE}${NC}"
echo -e "  Levels:   ${CYAN}1-${MAX_COMPLETE_LEVEL} completos${NC}"
echo -e "  URLs done: ${CYAN}${TOTAL_DONE}${NC}"
echo ""
echo -e "${YELLOW}Próximo passo:${NC} suba para o Google Drive como checkpoint de segurança."
echo ""

# Listar todos backups existentes
echo -e "${YELLOW}▸ Backups existentes:${NC}"
ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null | awk '{print "  " $5 "  " $9}' || echo "  Nenhum"
