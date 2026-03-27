#!/bin/bash
# deploy.sh — Despliegue de Attendoo en Hetzner CX23 (Ubuntu 22.04)
#
# Primer despliegue:
#   scp deploy.sh root@IP_VPS:/root/
#   ssh root@IP_VPS
#   chmod +x deploy.sh && ./deploy.sh
#
# ANTES de ejecutar:
#   1. Dominio apuntando al VPS en Cloudflare (DNS only, proxy OFF)
#   2. Firewall Hetzner: puertos 22, 80, 443 abiertos

set -euo pipefail

# === CONFIGURAR ESTAS VARIABLES ===
DOMAIN="${DOMAIN:-TU_DOMINIO.com}"
EMAIL="${EMAIL:-tu@email.com}"
REPO_URL="${REPO_URL:-https://github.com/TU_USUARIO/Attendoo.git}"
APP_DIR="/opt/attendoo"

echo "============================================"
echo "  Attendoo — Despliegue en producción"
echo "  Dominio: $DOMAIN"
echo "============================================"
echo ""

# --- 1. Actualizar sistema ---
echo "=== 1/9 Actualizando sistema ==="
apt update && apt upgrade -y

# --- 2. Instalar Docker ---
echo "=== 2/9 Instalando Docker ==="
if ! command -v docker &> /dev/null; then
    apt install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt update
    apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    echo "Docker instalado correctamente."
else
    echo "Docker ya está instalado, saltando."
fi

# --- 3. Instalar Certbot ---
echo "=== 3/9 Instalando Certbot ==="
if ! command -v certbot &> /dev/null; then
    apt install -y certbot
    echo "Certbot instalado."
else
    echo "Certbot ya está instalado, saltando."
fi

# --- 4. Clonar repositorio ---
echo "=== 4/9 Clonando repositorio ==="
if [ -d "$APP_DIR" ]; then
    echo "Directorio $APP_DIR ya existe. Haciendo git pull..."
    cd "$APP_DIR" && git pull origin main
else
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# --- 5. Verificar .env.prod ---
echo "=== 5/9 Verificando .env.prod ==="
if [ ! -f "$APP_DIR/.env.prod" ]; then
    echo ""
    echo "ERROR: No se encontró .env.prod"
    echo "Cópialo al servidor con:"
    echo "  scp .env.prod root@$(hostname -I | awk '{print $1}'):$APP_DIR/.env.prod"
    echo ""
    echo "Usa .env.prod.example como plantilla."
    exit 1
fi
echo ".env.prod encontrado."

# --- 6. Obtener certificado SSL ---
echo "=== 6/9 Obteniendo certificado SSL ==="
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    mkdir -p /var/www/certbot
    certbot certonly --standalone \
        -d "$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --non-interactive
    echo "Certificado SSL obtenido."
else
    echo "Certificado ya existe para $DOMAIN, saltando."
fi

# --- 7. Configurar dominio en nginx.conf ---
echo "=== 7/9 Configurando dominio en nginx.conf ==="
sed -i "s/TU_DOMINIO.com/$DOMAIN/g" "$APP_DIR/nginx.conf"
echo "Dominio configurado: $DOMAIN"

# --- 8. Build y arrancar ---
echo "=== 8/9 Construyendo y arrancando servicios ==="
cd "$APP_DIR"
docker compose -f docker-compose.prod.yml up -d --build
echo "Servicios arrancados."

# --- 9. Migraciones y seed ---
echo "=== 9/9 Ejecutando migraciones ==="
sleep 5  # Esperar a que PG esté listo
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head
echo "Migraciones completadas."

echo ""
read -p "¿Ejecutar seed.py (primer tenant)? [s/N]: " run_seed
if [[ "$run_seed" =~ ^[sS]$ ]]; then
    docker compose -f docker-compose.prod.yml exec -T app python seed.py
    echo "Seed completado."
fi

# --- Configurar renovación automática de certificados ---
echo ""
echo "=== Configurando renovación automática de SSL ==="
CRON_CMD="0 3 * * * certbot renew --quiet --deploy-hook 'docker compose -f $APP_DIR/docker-compose.prod.yml exec -T nginx nginx -s reload'"
(crontab -l 2>/dev/null | grep -v "certbot renew"; echo "$CRON_CMD") | crontab -
echo "Cron configurado para renovación SSL a las 3:00 AM."

# --- Resumen ---
echo ""
echo "============================================"
echo "  Despliegue completado"
echo "============================================"
echo ""
echo "Verifica:"
echo "  https://$DOMAIN/health"
echo "  https://$DOMAIN/admin"
echo ""
echo "IMPORTANTE:"
echo "  Actualiza el webhook en Meta Developer Console:"
echo "  URL: https://$DOMAIN/webhook"
echo ""
echo "Logs:"
echo "  docker compose -f $APP_DIR/docker-compose.prod.yml logs -f"
echo ""
