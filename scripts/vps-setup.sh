#!/usr/bin/env bash
# ============================================================================
# vps-setup.sh — Setup inicial da VPS para o projeto CatCar
#
# Uso (na VPS como root):
#   curl -sSL <raw-url> | bash
#   ou:
#   scp scripts/vps-setup.sh user@vps:/tmp/ && ssh user@vps 'bash /tmp/vps-setup.sh'
#
# Instala: Docker, Docker Compose, cria estrutura em /opt/catcar
# Testado em: Ubuntu 22.04 / 24.04 / Debian 12
# ============================================================================
set -euo pipefail

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="/opt/catcar"

echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      VPS SETUP — CatCar API                  ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Verificar se é root ──────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "Este script precisa ser executado como root (sudo)"
    exit 1
fi

# ── 2. Atualizar sistema ────────────────────────────────────────
echo -e "${YELLOW}→ Atualizando sistema...${NC}"
apt-get update -qq
apt-get upgrade -y -qq

# ── 3. Instalar dependências básicas ────────────────────────────
echo -e "${YELLOW}→ Instalando dependências...${NC}"
apt-get install -y -qq \
    ca-certificates curl gnupg lsb-release \
    git htop tmux unzip

# ── 4. Instalar Docker ──────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}→ Instalando Docker...${NC}"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
else
    echo -e "${GREEN}✓ Docker já instalado${NC}"
fi

# ── 5. Criar estrutura do projeto ───────────────────────────────
echo -e "${YELLOW}→ Criando estrutura do projeto...${NC}"
mkdir -p "$PROJECT_DIR"/{backups,logs}

# ── 6. Configurar swap (importante para VPS com pouca RAM) ──────
TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
if [[ $TOTAL_RAM_MB -lt 8192 ]]; then
    if [[ ! -f /swapfile ]]; then
        echo -e "${YELLOW}→ Criando swap de 4GB (RAM < 8GB)...${NC}"
        fallocate -l 4G /swapfile
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    else
        echo -e "${GREEN}✓ Swap já configurado${NC}"
    fi
fi

# ── 7. Configurar firewall básico ───────────────────────────────
echo -e "${YELLOW}→ Configurando firewall...${NC}"
if command -v ufw &> /dev/null; then
    ufw allow OpenSSH
    ufw allow 8000/tcp  # API
    ufw --force enable
else
    echo "  ufw não encontrado, pulando firewall"
fi

# ── 8. Otimizar sysctl para banco de dados ──────────────────────
echo -e "${YELLOW}→ Otimizando kernel para PostgreSQL...${NC}"
cat > /etc/sysctl.d/99-catcar.conf << 'SYSCTL'
# Shared memory para PostgreSQL
vm.overcommit_memory = 1
vm.swappiness = 10
# Network
net.core.somaxconn = 1024
net.ipv4.tcp_tw_reuse = 1
SYSCTL
sysctl --system > /dev/null 2>&1

# ── 9. Criar .env de produção ───────────────────────────────────
if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
    echo -e "${YELLOW}→ Criando .env de produção...${NC}"
    ADMIN_KEY=$(openssl rand -hex 24)
    DB_PASS=$(openssl rand -hex 16)
    cat > "${PROJECT_DIR}/.env" << EOF
# Gerado automaticamente em $(date)
POSTGRES_PASSWORD=${DB_PASS}
DATABASE_URL=postgresql+asyncpg://catcar:${DB_PASS}@postgres:5432/catcar
REDIS_URL=redis://redis:6379/0
ADMIN_API_KEY=${ADMIN_KEY}
LOG_LEVEL=INFO
EOF
    chmod 600 "${PROJECT_DIR}/.env"
    echo -e "${GREEN}✓ .env criado com senhas aleatórias${NC}"
    echo -e "  Admin API Key: ${CYAN}${ADMIN_KEY}${NC}"
else
    echo -e "${GREEN}✓ .env já existe${NC}"
fi

# ── Resumo ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           SETUP CONCLUÍDO!                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Próximos passos:"
echo -e "  1. Enviar código do projeto:"
echo -e "     ${CYAN}scp -r ./* user@vps:${PROJECT_DIR}/${NC}"
echo -e ""
echo -e "  2. Ou usar o script de deploy:"
echo -e "     ${CYAN}./scripts/deploy.sh user@vps${NC}"
echo -e ""
echo -e "  3. Na VPS, subir os containers:"
echo -e "     ${CYAN}cd ${PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d${NC}"
echo -e ""
echo -e "  4. Restaurar backup local:"
echo -e "     ${CYAN}./scripts/restore.sh backups/<arquivo>.sql.gz${NC}"
echo -e ""
echo -e "  5. Retomar o crawl:"
echo -e "     ${CYAN}docker compose exec -d -T worker python run_crawl.py --resume <JOB_ID> --level 6${NC}"
