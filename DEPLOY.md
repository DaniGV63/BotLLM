# DEPLOY.md — Guía de Despliegue Atendoo

## Requisitos previos

- **VPS:** Hetzner CX23 (4GB RAM, 2 vCPU, Ubuntu 22.04)
- **Dominio:** registrado y accesible
- **Cloudflare:** cuenta gratuita para DNS
- **GitHub:** repositorio privado con el código

---

## 1. Cloudflare — Configuración DNS

1. Añadir dominio a Cloudflare
2. Cambiar nameservers del registrador a los de Cloudflare
3. Crear registro **A**: `@` → `IP_DEL_VPS`
   - **IMPORTANTE:** Proxy **OFF** (icono gris, "DNS only")
   - Usamos Nginx + Certbot para SSL, no el proxy de Cloudflare
4. Opcional: registro A para `www` → `IP_DEL_VPS`
5. Esperar propagación DNS (puede tardar hasta 24h, normalmente minutos)

---

## 2. Hetzner — Crear VPS

1. Crear servidor CX23 con Ubuntu 22.04
2. Configurar SSH key en la creación
3. **Firewall Hetzner** — abrir puertos:
   - `22` (SSH)
   - `80` (HTTP — redirección a HTTPS + Certbot)
   - `443` (HTTPS)
4. Anotar la IP pública

---

## 3. Primer despliegue

### 3.1 Preparar .env.prod

Copiar `.env.prod.example` a `.env.prod` y rellenar todos los valores:

```bash
cp .env.prod.example .env.prod
# Editar con los valores reales de producción
```

Generar claves:
```bash
# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.2 Ejecutar deploy.sh

```bash
# Copiar .env.prod al servidor
scp .env.prod root@IP_VPS:/opt/atendoo/.env.prod

# Copiar y ejecutar el script de despliegue
scp deploy.sh root@IP_VPS:/root/
ssh root@IP_VPS
chmod +x deploy.sh

# Configurar variables y ejecutar
export DOMAIN="tudominio.com"
export EMAIL="tu@email.com"
export REPO_URL="https://github.com/tu-usuario/Atendoo.git"
./deploy.sh
```

### 3.3 Verificar

```bash
# Health check
curl https://tudominio.com/health

# Panel admin
# Abrir en navegador: https://tudominio.com/admin
```

### 3.4 Configurar webhook en Meta

1. Ir a Meta Developer Console → tu app → WhatsApp → Configuration
2. Cambiar Callback URL a: `https://tudominio.com/webhook`
3. Verificar que Meta valida el webhook correctamente

---

## 4. Despliegues posteriores (actualizaciones)

```bash
ssh root@IP_VPS
cd /opt/atendoo
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head
```

---

## 5. Logs y monitoreo

```bash
# Logs de la app
docker compose -f docker-compose.prod.yml logs -f app

# Logs de nginx
docker compose -f docker-compose.prod.yml logs -f nginx

# Todos los servicios
docker compose -f docker-compose.prod.yml logs -f

# Uso de recursos
docker stats
```

---

## 6. Backup y restauración

### Backup automático (v1.2.0+)
El backup se ejecuta automáticamente al arrancar uvicorn. Guarda tenants + admin_users + env keys en JSON con tokens desencriptados. Rotación: últimos 7 backups.

### Backup manual (aplicación)
```bash
# Desde el directorio del proyecto
python backup_tenant.py
# → backups/backup_full_YYYY-MM-DD_HHMMSS.json

# Restaurar desde backup
python restore_tenant.py backups/backup_full_YYYY-MM-DD_HHMMSS.json
```

### Backup raw PostgreSQL (dump completo)
```bash
# Backup
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U fisiobot_prod fisiobot > backup_$(date +%Y%m%d).sql

# Restore
cat backup.sql | docker compose -f docker-compose.prod.yml exec -T db \
  psql -U fisiobot_prod fisiobot
```

---

## 7. Certificados SSL

Renovación automática configurada por `deploy.sh` (cron a las 3:00 AM).

```bash
# Verificar estado de certificados
certbot certificates

# Verificar cron
crontab -l

# Renovación manual si necesario
certbot renew --dry-run
```

---

## 8. Comandos útiles

```bash
# Reiniciar todos los servicios
docker compose -f docker-compose.prod.yml restart

# Reiniciar solo la app (tras cambio de .env.prod)
docker compose -f docker-compose.prod.yml restart app

# Parar todo
docker compose -f docker-compose.prod.yml down

# Parar todo y borrar volúmenes (CUIDADO: borra BD)
docker compose -f docker-compose.prod.yml down -v

# Ejecutar comando dentro del contenedor app
docker compose -f docker-compose.prod.yml exec app python seed.py

# Ver estado de servicios
docker compose -f docker-compose.prod.yml ps
```

---

## 9. Dev vs Prod — Diferencias

| Aspecto | Dev (local) | Prod (VPS) |
|---------|------------|------------|
| Compose | `docker-compose.yml` (solo db+redis) | `docker-compose.prod.yml` (todo) |
| App | `uvicorn app.main:app --reload` directo | Contenedor Docker (2 workers) |
| Webhook | ngrok tunnel temporal | Dominio real + HTTPS |
| DB host | `localhost:5432` | `db:5432` (red interna Docker) |
| Redis | Sin password, puerto expuesto | `requirepass`, sin puerto expuesto |
| SSL | No | Let's Encrypt + Nginx |
| .env | `.env` (localhost) | `.env.prod` (nombres de servicio Docker) |
| Meta URL | `https://xxx.ngrok.io/webhook` | `https://tudominio.com/webhook` |
| Coste | Solo tokens LLM | VPS ~4€/mes + tokens LLM |
