#!/bin/bash
# bootstrap_server.sh — Setup inicial del VPS Hetzner para Atendoo
# Ejecutar UNA SOLA VEZ como root, justo después de instalar Ubuntu 22.04 limpio.
# Idempotente: si se ejecuta dos veces, no rompe nada.
#
# Uso:
#   scp -i ~/.ssh/id_ed25519 scripts/bootstrap_server.sh root@46.225.215.129:/tmp/
#   ssh -i ~/.ssh/id_ed25519 root@46.225.215.129 'bash /tmp/bootstrap_server.sh'

set -euo pipefail

echo "========================================"
echo " Atendoo — Bootstrap servidor"
echo " $(date)"
echo "========================================"

# ---------------------------------------------------------------------------
# 1. Actualizaciones base del sistema
# ---------------------------------------------------------------------------
echo "[1/11] Actualizando paquetes del sistema..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq

# ---------------------------------------------------------------------------
# 2. Paquetes base necesarios
# ---------------------------------------------------------------------------
echo "[2/11] Instalando paquetes base..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    curl \
    git \
    ufw \
    fail2ban \
    unattended-upgrades \
    ca-certificates \
    gnupg \
    lsb-release

# ---------------------------------------------------------------------------
# 3. Docker (instalación oficial desde docker.com, no el paquete Ubuntu)
# ---------------------------------------------------------------------------
echo "[3/11] Instalando Docker..."
if ! command -v docker &>/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin
    systemctl enable --now docker
    echo "  Docker instalado: $(docker --version)"
else
    echo "  Docker ya instalado — omitiendo"
fi

# ---------------------------------------------------------------------------
# 4. Certbot (para certificados SSL Let's Encrypt)
# ---------------------------------------------------------------------------
echo "[4/11] Instalando Certbot..."
if ! command -v certbot &>/dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq certbot
    echo "  Certbot instalado: $(certbot --version)"
else
    echo "  Certbot ya instalado — omitiendo"
fi

# ---------------------------------------------------------------------------
# 5. Usuario deploy
# ---------------------------------------------------------------------------
echo "[5/11] Configurando usuario deploy..."
if ! id deploy &>/dev/null; then
    adduser --disabled-password --gecos "" deploy
    echo "  Usuario deploy creado"
else
    echo "  Usuario deploy ya existe — omitiendo creación"
fi

# Añadir al grupo docker (permite ejecutar docker sin sudo)
usermod -aG docker deploy

# Copiar clave SSH autorizada de root a deploy
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
if [ -f /root/.ssh/authorized_keys ]; then
    cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
    chmod 600 /home/deploy/.ssh/authorized_keys
    chown -R deploy:deploy /home/deploy/.ssh
    echo "  Clave SSH copiada a deploy"
fi

# ---------------------------------------------------------------------------
# 6. Sudo granular — solo comandos necesarios para mantenimiento
# ---------------------------------------------------------------------------
echo "[6/11] Configurando sudo granular para deploy..."
cat > /etc/sudoers.d/deploy << 'SUDOERS'
deploy ALL=(root) NOPASSWD: \
    /usr/bin/apt-get update, \
    /usr/bin/apt-get upgrade -y, \
    /usr/bin/certbot *, \
    /usr/bin/systemctl reload nginx, \
    /usr/bin/systemctl restart nginx
SUDOERS
chmod 440 /etc/sudoers.d/deploy
echo "  Sudo granular configurado"

# ---------------------------------------------------------------------------
# 7. Hardening SSH
# IMPORTANTE: NO reiniciar SSH hasta el final, después de verificar acceso deploy
# ---------------------------------------------------------------------------
echo "[7/11] Configurando hardening SSH..."
# Deshabilitar login de root por SSH
sed -i 's/^#*PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
# Deshabilitar autenticación por contraseña (solo clave SSH)
sed -i 's/^#*PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
# Asegurar que autenticación por clave pública está habilitada
sed -i 's/^#*PubkeyAuthentication .*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
echo "  SSH hardening configurado (se aplicará al reiniciar SSH al final)"

# ---------------------------------------------------------------------------
# 8. Firewall UFW
# ---------------------------------------------------------------------------
echo "[8/11] Configurando firewall UFW..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP (redirige a HTTPS via nginx)
ufw allow 443/tcp  # HTTPS
ufw --force enable
echo "  Firewall activado: SSH + HTTP + HTTPS"

# ---------------------------------------------------------------------------
# 9. Fail2ban (protección contra fuerza bruta SSH)
# ---------------------------------------------------------------------------
echo "[9/11] Configurando fail2ban..."
cat > /etc/fail2ban/jail.local << 'FAIL2BAN'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port    = ssh
logpath = %(sshd_log)s
backend = %(sshd_backend)s
FAIL2BAN
systemctl enable --now fail2ban
systemctl restart fail2ban
echo "  Fail2ban activado (max 3 intentos SSH, ban 1h)"

# ---------------------------------------------------------------------------
# 10. Unattended upgrades (parches de seguridad automáticos)
# ---------------------------------------------------------------------------
echo "[10/11] Habilitando actualizaciones de seguridad automáticas..."
DEBIAN_FRONTEND=noninteractive dpkg-reconfigure --priority=low unattended-upgrades
echo "  Unattended-upgrades configurado"

# ---------------------------------------------------------------------------
# 11. Directorio del proyecto
# ---------------------------------------------------------------------------
echo "[11/11] Preparando directorio del proyecto..."
mkdir -p /opt/atendoo/shared/backups
chown -R deploy:deploy /opt/atendoo
echo "  /opt/atendoo listo (propietario: deploy)"

# ---------------------------------------------------------------------------
# Reiniciar SSH — ÚLTIMO PASO
# ADVERTENCIA: Abre una segunda terminal y verifica que puedes entrar como
# deploy ANTES de cerrar esta sesión de root.
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo " Bootstrap completado."
echo ""
echo " ANTES DE CERRAR ESTA SESIÓN:"
echo " Abre otra terminal y verifica:"
echo "   ssh -i ~/.ssh/id_ed25519 deploy@$(curl -s ifconfig.me 2>/dev/null || echo '<IP>')"
echo ""
echo " Si el acceso como deploy funciona, ejecuta:"
echo "   systemctl restart ssh"
echo ""
echo " Si NO funciona, NO reinicies SSH — root seguirá accesible."
echo "========================================"
