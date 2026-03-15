#!/usr/bin/env bash
# ============================================================================
# status.sh — Verificar progresso do crawl
#
# Uso:
#   ./scripts/status.sh              # Status completo
#   ./scripts/status.sh --watch      # Atualizar a cada 30s
# ============================================================================
set -euo pipefail

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Detectar compose file
COMPOSE_FILE=""
if [[ -f "docker-compose.prod.yml" ]]; then
    COMPOSE_FILE="-f docker-compose.prod.yml"
fi

DB_CONTAINER="${DB_CONTAINER:-$(docker compose $COMPOSE_FILE ps -q postgres 2>/dev/null || echo 'api-car-postgres-1')}"
DB_USER="${DB_USER:-catcar}"
DB_NAME="${DB_NAME:-catcar}"

show_status() {
    clear 2>/dev/null || true
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║               CatCar — Status do Crawl                      ║${NC}"
    echo -e "${CYAN}║               $(date '+%Y-%m-%d %H:%M:%S')                           ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Containers
    echo -e "${YELLOW}▸ Containers:${NC}"
    docker compose $COMPOSE_FILE ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
        docker ps --filter "name=api-car" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""

    # Queue progress
    echo -e "${YELLOW}▸ Progresso por Level:${NC}"
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT
        level,
        CASE level
            WHEN 1 THEN 'Brands'
            WHEN 2 THEN 'Models'
            WHEN 3 THEN 'Years'
            WHEN 4 THEN 'Categories'
            WHEN 5 THEN 'Subgroups'
            WHEN 6 THEN 'Parts'
        END AS tipo,
        SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done,
        SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
        SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS processing,
        SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
        CASE
            WHEN COUNT(*) > 0
            THEN ROUND(SUM(CASE WHEN status='done' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 1) || '%'
            ELSE '0%'
        END AS progresso
    FROM crawl_queue
    GROUP BY level
    ORDER BY level;
    " 2>/dev/null || echo "  Sem dados de queue"
    echo ""

    # Data tables
    echo -e "${YELLOW}▸ Dados coletados:${NC}"
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT
        relname AS tabela,
        n_live_tup AS linhas,
        pg_size_pretty(pg_total_relation_size(relid)) AS tamanho
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY n_live_tup DESC;
    " 2>/dev/null
    echo ""

    # DB size
    echo -e "${YELLOW}▸ Tamanho do banco:${NC}"
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tA -c "
    SELECT pg_size_pretty(pg_database_size('$DB_NAME'));
    " 2>/dev/null
    echo ""

    # Recent errors
    echo -e "${YELLOW}▸ Últimos erros:${NC}"
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT level, LEFT(url, 60) AS url, LEFT(error_message, 80) AS erro
    FROM crawl_queue
    WHERE status = 'failed'
    ORDER BY processed_at DESC NULLS LAST
    LIMIT 5;
    " 2>/dev/null || echo "  Sem erros"

    # Crawl job info
    echo ""
    echo -e "${YELLOW}▸ Jobs de crawl:${NC}"
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT id, status, created_at, started_at
    FROM crawl_jobs
    ORDER BY id DESC LIMIT 3;
    " 2>/dev/null || echo "  Sem jobs"
}

# Watch mode
if [[ "${1:-}" == "--watch" ]]; then
    while true; do
        show_status
        echo ""
        echo -e "${CYAN}Atualizando em 30s... (Ctrl+C para sair)${NC}"
        sleep 30
    done
else
    show_status
fi
