# DEPLOY.md — Guía de Despliegue Atendoo

> **Convenciones obligatorias (desde 2026-04-14):**
> - Rama de producción: `deployment` (nunca `main`)
> - Usuario SSH en servidor: `deploy` (nunca `root`)
> - Todo deploy pasa por GitHub Actions (push → automático)
> - SSH manual al servidor: solo para debugging y emergencias

---

## Requisitos previos

- **VPS:** Hetzner CX23 (4GB RAM, 2 vCPU, Ubuntu 22.04)
- **Dominio:** registrado y accesible
- **Cloudflare:** cuenta gratuita para DNS
- **GitHub:** repositorio privado con el código
- **Claves SSH:** `id_ed25519` (personal) + `atendoo_ci` (solo para CI/CD)

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

## 3. Primer despliegue (setup inicial)

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

### 3.2 Ejecutar bootstrap_server.sh (una sola vez)

```bash
# Copiar el script al servidor
scp -i ~/.ssh/id_ed25519 scripts/bootstrap_server.sh root@IP_VPS:/tmp/

# Ejecutar como root
ssh -i ~/.ssh/id_ed25519 root@IP_VPS 'bash /tmp/bootstrap_server.sh'
```

El script crea el usuario `deploy`, instala Docker, configura ufw/fail2ban y
deja `/opt/atendoo` listo. Ver `scripts/bootstrap_server.sh` para los detalles.

### 3.3 Obtener SSL con Certbot

Antes del primer `docker compose up`, obtener el certificado (nginx necesita los
certs para arrancar):

```bash
ssh -i ~/.ssh/id_ed25519 root@IP_VPS
certbot certonly --standalone -d atendoo.app --email tu@email.com --agree-tos -n
exit
```

### 3.4 Subir .env.prod y clonar repo

```bash
# Subir .env.prod al servidor
scp -i ~/.ssh/id_ed25519 .env.prod deploy@IP_VPS:/opt/atendoo/.env.prod

# Como usuario deploy, clonar repo
ssh -i ~/.ssh/id_ed25519 deploy@IP_VPS
cd /opt/atendoo
git clone --branch deployment https://github.com/DaniGV63/BotLLM.git .
mkdir -p shared/backups
```

### 3.5 Arrancar servicios

```bash
# Desde el servidor como deploy:
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head

# Verificar
curl https://atendoo.app/health
```

### 3.6 Crear clave SSH para CI/CD

```bash
# En local — genera clave nueva solo para GitHub Actions
ssh-keygen -t ed25519 -f ~/.ssh/atendoo_ci -N "" -C "atendoo-ci"

# Autorizar en el servidor
ssh-copy-id -i ~/.ssh/atendoo_ci.pub deploy@IP_VPS

# Guardar la clave privada en Bitwarden como adjunto
```

### 3.7 Configurar secrets en GitHub

En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valor |
|--------|-------|
| `SSH_HOST` | IP del VPS (ej: `46.225.215.129`) |
| `SSH_USER` | `deploy` |
| `SSH_KEY` | contenido de `~/.ssh/atendoo_ci` (clave privada CI) |
| `SSH_PORT` | `22` |

### 3.8 Configurar webhook en Meta

1. Ir a Meta Developer Console → tu app → WhatsApp → Configuration
2. Cambiar Callback URL a: `https://atendoo.app/webhook`
3. Verificar que Meta valida el webhook correctamente

---

## 4. Despliegues posteriores (modo normal con CI/CD)

```bash
# Hacer cambios en local, commit y push a la rama deployment:
git add <archivos>
git commit -m "feat: descripción del cambio"
git push origin deployment
# → GitHub Actions detecta el push y despliega automáticamente
# → Ver progreso en: GitHub → Actions → Deploy to Hetzner
```

El workflow (`.github/workflows/deploy.yml`) hace:
1. Guarda el commit actual como punto de rollback
2. `pg_dump` antes del deploy (backup automático)
3. `git reset --hard origin/deployment`
4. `docker compose up -d --build`
5. `alembic upgrade head`
6. Healthcheck en `https://atendoo.app/health` (6 intentos × 10s)
7. Si falla: rollback automático al commit anterior

---

## 5. Logs y monitoreo

```bash
# Conectar al servidor (debugging/emergencias)
ssh -i ~/.ssh/id_ed25519 deploy@IP_VPS

# Logs de la app
docker compose -f docker-compose.prod.yml logs -f app

# Logs de nginx
docker compose -f docker-compose.prod.yml logs -f nginx

# Todos los servicios
docker compose -f docker-compose.prod.yml logs -f

# Uso de recursos
docker stats

# Estado de contenedores (healthy/unhealthy)
docker compose -f docker-compose.prod.yml ps
```

---

## 6. Backup y restauración

### Backup automático pre-deploy
El workflow de GitHub Actions hace `pg_dump` antes de cada deploy.
Los backups se guardan en `/opt/atendoo/shared/backups/pre_deploy_FECHA.sql.gz`.
Rotación automática: se borran los de más de 14 días.

### Backup manual (aplicación)
```bash
# Desde el servidor como deploy:
docker compose -f docker-compose.prod.yml exec app python backup_tenant.py
# → /opt/atendoo/backups/backup_full_YYYY-MM-DD_HHMMSS.json

# Restaurar desde backup
docker compose -f docker-compose.prod.yml exec app \
  python restore_tenant.py backups/backup_full_YYYY-MM-DD_HHMMSS.json
```

### Backup raw PostgreSQL
```bash
# Backup completo (desde servidor)
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U $POSTGRES_USER $POSTGRES_DB \
  | gzip > shared/backups/pg_$(date +%F).sql.gz

# Restore
gunzip -c shared/backups/pg_FECHA.sql.gz \
  | docker compose -f docker-compose.prod.yml exec -T db \
    psql -U $POSTGRES_USER $POSTGRES_DB
```

---

## 7. Certificados SSL

Renovación automática: certbot instala un timer systemd que renueva a las 00:00 y 12:00.

```bash
# Verificar estado de certificados
certbot certificates

# Renovación manual si necesario
certbot renew --dry-run
```

---

## 8. Comandos útiles

```bash
# Reiniciar solo la app (tras cambio de .env.prod)
docker compose -f docker-compose.prod.yml restart app

# Parar todo SIN borrar datos
docker compose -f docker-compose.prod.yml stop

# Ver estado de servicios
docker compose -f docker-compose.prod.yml ps

# Ejecutar comando dentro del contenedor app
docker compose -f docker-compose.prod.yml exec app python seed.py

# Rollback manual (si el automático falla)
cd /opt/atendoo
git reset --hard $(cat .last_good_commit)
docker compose -f docker-compose.prod.yml up -d --build
```

> ⛔ **NUNCA ejecutar:**
> ```bash
> docker compose -f docker-compose.prod.yml down   # borra volúmenes → destruye BD
> docker compose -f docker-compose.prod.yml down -v # igual pero más explícito
> ```

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
| Meta URL | `https://xxx.ngrok.io/webhook` | `https://atendoo.app/webhook` |
| Deploy | Manual (uvicorn reload) | GitHub Actions → SSH → docker compose |
| Coste | Solo tokens LLM | VPS ~4€/mes + tokens LLM |
