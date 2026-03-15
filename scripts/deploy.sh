#!/usr/bin/env bash
# ============================================================================
# deploy.sh — Enviar código e backup para a VPS
#
# Uso:
#   ./scripts/deploy.sh user@vps                  # Só código
#   ./scripts/deploy.sh user@vps --with-backup     # Código + último backup
#   ./scripts/deploy.sh user@vps --backup-only     # Só backup
#   ./scripts/deploy.sh user@vps --resume          # Código + backup + retomar crawl
#
# O script envia os arquivos necessários, faz build dos containers,
# e opcionalmente restaura o banco e retoma o crawl.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REMOTE_DIR="/opt/catcar"

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Args
VPS_HOST="${1:-}"
ACTION="${2:-code}"

if [[ -z "$VPS_HOST" ]]; then
    echo "Uso: $0 user@vps [--with-backup|--backup-only|--resume]"
    exit 1
fi

echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        DEPLOY — CatCar para VPS              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  VPS: ${CYAN}${VPS_HOST}${NC}"
echo -e "  Dir: ${CYAN}${REMOTE_DIR}${NC}"
echo ""

# ── Função: enviar código ───────────────────────────────────────
send_code() {
    echo -e "${YELLOW}→ Enviando código para VPS...${NC}"

    # Criar diretórios remotos
    ssh "$VPS_HOST" "mkdir -p ${REMOTE_DIR}/{scripts,backups,docker}"

    # Enviar apenas arquivos necessários (excluir snapshots, imagens, etc)
    rsync -avz --progress \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='.pytest_cache' \
        --exclude='*.png' \
        --exclude='*.yaml' \
        --exclude='test.db' \
        --exclude='backups/' \
        --exclude='.playwright-cli/' \
        --exclude='venv/' \
        --exclude='.env' \
        --exclude='node_modules/' \
        "$PROJECT_DIR/" "$VPS_HOST:${REMOTE_DIR}/"

    echo -e "${GREEN}✓ Código enviado${NC}"
}

# ── Função: enviar backup ──────────────────────────────────────
send_backup() {
    echo -e "${YELLOW}→ Procurando último backup...${NC}"

    # Achar backup mais recente
    LATEST_BACKUP=$(ls -t "$PROJECT_DIR/backups/"*.sql.gz 2>/dev/null | head -1)

    if [[ -z "$LATEST_BACKUP" ]]; then
        echo -e "${RED}✗ Nenhum backup encontrado em ./backups/${NC}"
        echo -e "  Execute primeiro: ${CYAN}./scripts/backup.sh${NC}"
        return 1
    fi

    FILE_SIZE=$(du -h "$LATEST_BACKUP" | cut -f1)
    echo -e "  Arquivo: ${CYAN}$(basename $LATEST_BACKUP)${NC} (${FILE_SIZE})"

    echo -e "${YELLOW}→ Enviando backup para VPS...${NC}"
    rsync -avz --progress "$LATEST_BACKUP" "$VPS_HOST:${REMOTE_DIR}/backups/"
    echo -e "${GREEN}✓ Backup enviado${NC}"

    REMOTE_BACKUP="${REMOTE_DIR}/backups/$(basename $LATEST_BACKUP)"
    echo "$REMOTE_BACKUP"
}

# ── Função: build e restart na VPS ─────────────────────────────
build_remote() {
    echo -e "${YELLOW}→ Build dos containers na VPS...${NC}"
    ssh "$VPS_HOST" "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml build"
    echo -e "${GREEN}✓ Build concluído${NC}"

    echo -e "${YELLOW}→ Subindo containers...${NC}"
    ssh "$VPS_HOST" "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d"
    echo -e "${GREEN}✓ Containers rodando${NC}"
}

# ── Função: restaurar backup na VPS ────────────────────────────
restore_remote() {
    local backup_path="$1"
    echo -e "${YELLOW}→ Restaurando backup na VPS...${NC}"
    ssh "$VPS_HOST" "cd ${REMOTE_DIR} && bash scripts/restore.sh ${backup_path}" <<< "y"
    echo -e "${GREEN}✓ Banco restaurado${NC}"
}

# ── Função: retomar crawl ──────────────────────────────────────
resume_crawl() {
    echo -e "${YELLOW}→ Buscando último job_id...${NC}"
    JOB_ID=$(ssh "$VPS_HOST" "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml exec -T postgres psql -U catcar -d catcar -tA -c 'SELECT MAX(id) FROM crawl_jobs;'" 2>/dev/null | tr -d '[:space:]')

    if [[ -z "$JOB_ID" || "$JOB_ID" == "" ]]; then
        echo -e "${RED}✗ Nenhum job encontrado no banco${NC}"
        return 1
    fi

    echo -e "  Job ID: ${CYAN}${JOB_ID}${NC}"
    echo -e "${YELLOW}→ Retomando crawl (detached)...${NC}"
    ssh "$VPS_HOST" "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml exec -d -T worker python run_crawl.py --resume ${JOB_ID} --level 6"
    echo -e "${GREEN}✓ Crawl retomado em background!${NC}"
}

# ── Executar conforme a ação ───────────────────────────────────
case "$ACTION" in
    --backup-only)
        send_backup
        ;;
    --with-backup)
        send_code
        send_backup
        build_remote
        ;;
    --resume)
        send_code
        BACKUP_PATH=$(send_backup)
        build_remote
        restore_remote "$BACKUP_PATH"
        resume_crawl
        ;;
    *)
        send_code
        build_remote
        ;;
esac

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           DEPLOY CONCLUÍDO!                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Comandos úteis na VPS:"
echo -e "    ${CYAN}ssh ${VPS_HOST}${NC}"
echo -e "    ${CYAN}cd ${REMOTE_DIR}${NC}"
echo -e "    ${CYAN}docker compose -f docker-compose.prod.yml logs -f worker${NC}  # Ver logs"
echo -e "    ${CYAN}./scripts/status.sh${NC}                                       # Ver progresso"
