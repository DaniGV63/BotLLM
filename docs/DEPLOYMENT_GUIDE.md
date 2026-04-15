# Guía de Despliegue Atendoo — Explicación en profundidad

Esta guía está pensada para leerse de principio a fin una vez y consultarse
puntualmente después. Explica cada comando con el nivel de detalle necesario
para entender qué pasa en el servidor, por qué funciona, y qué romper si te
equivocas.

---

## Índice

1. [Arquitectura del sistema](#1-arquitectura-del-sistema)
2. [Conectarse al servidor](#2-conectarse-al-servidor)
3. [Subir archivos al servidor](#3-subir-archivos-al-servidor)
4. [Actualizar el código](#4-actualizar-el-código)
5. [El comando más importante: docker compose up](#5-el-comando-más-importante-docker-compose-up)
6. [Aplicar migraciones de base de datos](#6-aplicar-migraciones-de-base-de-datos)
7. [Ver logs en tiempo real](#7-ver-logs-en-tiempo-real)
8. [Reiniciar sin recompilar](#8-reiniciar-sin-recompilar)
9. [Ver estado de los contenedores](#9-ver-estado-de-los-contenedores)
10. [Backups de la base de datos](#10-backups-de-la-base-de-datos)
11. [Restaurar un backup](#11-restaurar-un-backup)
12. [El flujo completo con CI/CD](#12-el-flujo-completo-con-cicd)
13. [Backup, wipe y reset del servidor](#13-backup-wipe-y-reset-del-servidor)
14. [Reglas absolutas](#14-reglas-absolutas)
15. [Qué hacer si algo falla](#15-qué-hacer-si-algo-falla)

---

## 1. Arquitectura del sistema

Antes de los comandos, conviene tener la imagen clara de lo que hay en el
servidor:

```
Internet
    │
    ▼
Hetzner VPS (Ubuntu 22.04)
    │  IP: 46.225.215.129
    │
    ├── nginx (contenedor Docker, puertos 80/443)
    │       │  Recibe todo el tráfico HTTPS
    │       │  Sirve archivos estáticos (JS, CSS, imágenes)
    │       │  Redirige el resto a la app
    │       ▼
    ├── app  (contenedor Docker, puerto interno 8000)
    │       │  FastAPI + Python — la lógica del bot
    │       │  2 workers uvicorn
    │       ├── se conecta a ──→ db  (PostgreSQL)
    │       └── se conecta a ──→ redis
    │
    ├── db   (contenedor Docker, sin puerto expuesto al exterior)
    │       PostgreSQL 15 — fuente de verdad de todos los datos
    │       Datos guardados en volumen Docker: postgres_data
    │
    └── redis (contenedor Docker, sin puerto expuesto)
            Cache de sesiones, deduplicación de mensajes
            Datos guardados en volumen Docker: redis_data
```

Los cuatro contenedores están en una **red interna Docker** llamada `internal`.
Solo nginx tiene puertos expuestos al exterior (80 y 443). La app, db y redis
son invisibles desde internet — solo se hablan entre ellos dentro del servidor.

Los archivos del proyecto están en `/opt/atendoo/` en el servidor. Este
directorio es un clon git del repositorio, en la rama `deployment`.

---

## 2. Conectarse al servidor

```bash
ssh -i ~/.ssh/id_ed25519 deploy@46.225.215.129
```

**¿Qué es SSH?**
SSH (Secure Shell) es el protocolo estándar para ejecutar comandos en una
máquina remota de forma cifrada. Es como tener un terminal del servidor en tu
ordenador local.

**Trocitos del comando:**
- `ssh` → el cliente SSH (viene instalado en macOS/Linux, en Windows con Git Bash o PowerShell)
- `-i ~/.ssh/id_ed25519` → indica qué clave privada usar para autenticarse. Es como tu "contraseña" pero en formato archivo. Sin ella, el servidor rechaza la conexión.
- `deploy` → el usuario con el que entras. Desde 2026-04-14, nunca `root`.
- `@` → separador usuario/servidor
- `46.225.215.129` → la IP pública del VPS Hetzner

**¿Cómo funciona la autenticación por clave?**
Tienes dos archivos:
- `~/.ssh/id_ed25519` → clave **privada** (solo en tu PC, nunca compartas)
- `~/.ssh/id_ed25519.pub` → clave **pública** (está en el servidor en `/home/deploy/.ssh/authorized_keys`)

Cuando te conectas, el servidor genera un reto matemático que solo puede
resolverse con la clave privada. Si tu PC la tiene, entras. Sin ella, denegado.

**¿Cuándo usarlo?**
Para debugging y emergencias. Los deploys normales son automáticos via GitHub
Actions — no necesitas conectarte manualmente.

**Errores comunes:**
- `Permission denied (publickey)` → clave incorrecta o usuario equivocado
- `Connection timed out` → IP incorrecta o firewall bloqueando puerto 22
- `Connection refused` → SSH no está corriendo en el servidor

---

## 3. Subir archivos al servidor

```bash
scp -i ~/.ssh/id_ed25519 archivo_local deploy@46.225.215.129:/ruta/remota/
```

**¿Qué es SCP?**
SCP (Secure Copy Protocol) copia archivos entre tu PC y el servidor usando la
misma conexión SSH. Es como `cp` pero entre máquinas.

**Ejemplos reales:**

```bash
# Subir .env.prod al servidor (solo la primera vez o si cambian secretos)
scp -i ~/.ssh/id_ed25519 .env.prod deploy@46.225.215.129:/opt/atendoo/.env.prod

# Subir el script de bootstrap
scp -i ~/.ssh/id_ed25519 scripts/bootstrap_server.sh root@46.225.215.129:/tmp/

# Subir un backup de Bitwarden al servidor para restaurar
scp -i ~/.ssh/id_ed25519 pg_backup.sql.gz deploy@46.225.215.129:/opt/atendoo/shared/backups/
```

**¿Cuándo usarlo?**
- Primera vez para subir `.env.prod` (tiene los secretos que no van al repo)
- Para subir backups de tu PC al servidor
- Para descargar archivos del servidor a tu PC (invierte origen y destino)

**Descargar desde servidor:**
```bash
# Descargar un backup desde el servidor a tu PC
scp -i ~/.ssh/id_ed25519 deploy@46.225.215.129:/opt/atendoo/shared/backups/pg_2026-04-14.sql.gz ./
```

---

## 4. Actualizar el código

```bash
cd /opt/atendoo
git fetch origin deployment
git reset --hard origin/deployment
```

**¿Qué hacen estos comandos?**

`git fetch origin deployment`:
- Descarga los últimos commits de GitHub **sin aplicarlos todavía**
- `origin` → el nombre del repositorio remoto (GitHub)
- `deployment` → la rama que usamos en producción

`git reset --hard origin/deployment`:
- Aplica los commits descargados, **descartando cualquier cambio local**
- `--hard` → modo sin piedad: el directorio queda exactamente igual que en GitHub
- Si hay algún archivo modificado manualmente en el servidor, se pierde

**¿Por qué `reset --hard` en lugar de `pull`?**
En producción queremos que el servidor sea siempre una copia exacta del
repositorio. `git pull` puede fallar con conflictos si alguien modificó algo en
el servidor. `reset --hard` nunca falla y garantiza sincronía total.

**IMPORTANTE:** Actualizar el código **no actualiza la app que está corriendo**.
Los contenedores Docker siguen usando el código que tenían cuando se construyeron.
Para que el código nuevo entre en producción, hay que reconstruir la imagen
(paso siguiente).

---

## 5. El comando más importante: docker compose up

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Este es el comando central del deploy. Entenderlo bien evita el 90% de los
problemas.

**¿Qué hace cada parte?**

`docker compose`:
- Herramienta que orquesta múltiples contenedores Docker juntos
- Lee un archivo de configuración (el `-f`) que describe qué contenedores
  hay, cómo se conectan, qué volúmenes usan, etc.

`-f docker-compose.prod.yml`:
- Usa el archivo de configuración de **producción** (no el de desarrollo)
- Hay dos archivos: `docker-compose.yml` (local, solo db+redis) y
  `docker-compose.prod.yml` (prod, todos los servicios)
- Si omites `-f`, Docker busca `docker-compose.yml` y el deploy fallaría
  porque no tiene la app ni nginx

`up`:
- Asegura que todos los servicios definidos estén corriendo
- Si un contenedor ya corre, lo deja (a menos que uses `--build`)
- Si un contenedor no existe, lo crea

`-d` (detached):
- Ejecuta los contenedores en segundo plano
- Sin `-d`, el terminal se quedaría pegado mostrando logs hasta que pulses Ctrl+C
  y los contenedores se pararían

`--build`:
- **Esta flag es crítica.** Reconstruye la imagen Docker desde el `Dockerfile`
  con el código actual del directorio.
- Sin `--build`: Docker usa la imagen que ya tiene en caché, que fue construida
  con el código antiguo. El `git pull` sirve de nada.
- Con `--build`: Docker lee el `Dockerfile`, copia el código nuevo dentro de
  la imagen, instala dependencias si cambiaron, y lanza la app con el código nuevo.

**¿Por qué "algunas features se veían y otras no" antes del CI/CD?**
Porque se ejecutó `git pull` pero no se hizo `docker compose up -d --build`.
O porque sí se hizo pero el navegador tenía caché de JS antiguo (resuelto
con `Cache-Control: no-cache` en nginx).

**¿Cuánto tarda?**
- Si no cambiaron dependencias (`requirements.txt`): ~30-60 segundos
- Si cambiaron dependencias: 2-5 minutos (descarga paquetes nuevos)
- La primera vez (imagen desde cero): 5-10 minutos

**¿Qué pasa con los datos durante el rebuild?**
Los datos de PostgreSQL y Redis están en **volúmenes Docker** (`postgres_data`,
`redis_data`). Los volúmenes son independientes de los contenedores — reconstruir
la imagen no los toca. Los datos están seguros.

---

## 6. Aplicar migraciones de base de datos

```bash
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head
```

**¿Qué son las migraciones?**
Cuando el código cambia la estructura de la base de datos (nueva tabla, nueva
columna, índice nuevo), esos cambios están codificados en archivos de migración
en `alembic/versions/`. Alembic los aplica en orden, sin borrar datos existentes.

**¿Qué hace cada parte?**

`docker compose -f docker-compose.prod.yml exec`:
- Ejecuta un comando dentro de un contenedor que ya está corriendo

`-T`:
- Deshabilita la pseudo-terminal (necesario cuando el output va a un script o
  tubería, no a un terminal interactivo)

`app`:
- El nombre del servicio donde ejecutar el comando (el contenedor de FastAPI)

`alembic upgrade head`:
- `alembic` → herramienta de migraciones para SQLAlchemy
- `upgrade` → aplicar migraciones pendientes
- `head` → hasta la última migración disponible

**¿Es seguro ejecutarlo si ya estaba actualizado?**
Sí. Alembic registra qué migraciones ya se aplicaron. Si no hay nuevas, no hace
nada. Es idempotente.

**¿Cuándo hay que ejecutarlo?**
Después de cada deploy que incluya archivos en `alembic/versions/`. En la práctica,
el workflow de CI/CD lo hace siempre — es inofensivo ejecutarlo de más.

---

## 7. Ver logs en tiempo real

```bash
# Solo la app
docker compose -f docker-compose.prod.yml logs -f app

# Solo nginx
docker compose -f docker-compose.prod.yml logs -f nginx

# Todos los servicios a la vez
docker compose -f docker-compose.prod.yml logs -f

# Últimas 100 líneas y luego en vivo
docker compose -f docker-compose.prod.yml logs -f --tail=100 app
```

**¿Qué muestra?**
Los logs de la app (FastAPI/uvicorn) muestran cada request que recibe,
errores de Python, mensajes de WhatsApp procesados, llamadas al LLM, etc.

**¿Cómo salir?**
`Ctrl+C` — para de mostrar logs pero no para los contenedores.

**Cuándo usarlo:**
- Justo después de un deploy para verificar que la app arrancó sin errores
- Cuando un usuario reporta un error: ver qué pasó en el momento
- Para depurar por qué el bot no responde

---

## 8. Reiniciar sin recompilar

```bash
docker compose -f docker-compose.prod.yml restart app
```

**¿Cuándo sirve?**
Solo cuando cambias algo en `.env.prod` y quieres que el proceso lo re-lea.
Los procesos en Python leen las variables de entorno al arrancar — un restart
las carga de nuevo.

**¿Cuándo NO sirve?**
Para aplicar cambios de código. Si modificaste Python, JS, etc., necesitas
`up -d --build`. Un `restart` deja el código viejo.

**Analogía:**
- `restart` → apagar y encender el ordenador (mismo SO, mismos programas)
- `up -d --build` → reinstalar el SO con una versión nueva (código actualizado)

---

## 9. Ver estado de los contenedores

```bash
docker compose -f docker-compose.prod.yml ps
```

**Output esperado (todo OK):**
```
NAME              STATUS          PORTS
atendoo-app-1     healthy         
atendoo-db-1      healthy         
atendoo-nginx-1   Up              0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
atendoo-redis-1   healthy         
```

**¿Qué significa `healthy`?**
El healthcheck configurado está pasando. Para `app`: `curl localhost:8000/health`
devuelve 200. Para `db`: `pg_isready` confirma que PostgreSQL acepta conexiones.

**Si ves `unhealthy` o `starting`:**
- `starting` → acabas de hacer `up`, espera 15-30 segundos
- `unhealthy` → el healthcheck falla → ver logs para el motivo

---

## 10. Backups de la base de datos

```bash
# Backup completo de PostgreSQL (todos los datos)
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U $POSTGRES_USER $POSTGRES_DB \
  | gzip > shared/backups/pg_$(date +%F).sql.gz
```

**¿Qué es pg_dump?**
La herramienta oficial de PostgreSQL para exportar toda la base de datos a un
archivo SQL. El archivo contiene instrucciones `CREATE TABLE`, `INSERT`, etc.
que reproducen la base de datos exactamente.

**¿Qué es gzip?**
Compresión. Un dump sin comprimir puede pesar 50MB, comprimido baja a 5-10MB.
El `|` (pipe) conecta la salida de `pg_dump` directamente a `gzip` sin crear
un archivo intermedio.

**¿Qué datos incluye?**
Todo: tenants, conversaciones, mensajes, citas, clases grupales, inscripciones,
RGPD, tokens cifrados. Es un backup completo.

**Cron de backup automático** (configurar una vez en el servidor):
```bash
# Como usuario deploy, añadir al crontab:
crontab -e

# Añadir esta línea (backup a las 3 AM todos los días):
0 3 * * * cd /opt/atendoo && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U $POSTGRES_USER $POSTGRES_DB | gzip > shared/backups/pg_$(date +\%F).sql.gz && find shared/backups -name 'pg_*.sql.gz' -mtime +14 -delete
```

---

## 11. Restaurar un backup

```bash
# Restaurar un backup de PostgreSQL
gunzip -c shared/backups/pg_2026-04-14.sql.gz \
  | docker compose -f docker-compose.prod.yml exec -T db \
    psql -U $POSTGRES_USER $POSTGRES_DB
```

**¿Qué hace?**
- `gunzip -c` → descomprime el archivo a stdout (sin crear archivo intermedio)
- `|` → pasa el SQL al siguiente comando
- `psql -U $USER $DB` → ejecuta el SQL en PostgreSQL

**ADVERTENCIA:** Esto añade datos encima de lo que ya hay. Si la tabla ya tiene
datos y el backup también, pueden surgir conflictos de clave primaria. Para un
restore limpio, primero hay que vaciar la BD:

```bash
# Vaciar la BD antes de restaurar (solo si el restore es a BD limpia)
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U $POSTGRES_USER -c "DROP DATABASE $POSTGRES_DB; CREATE DATABASE $POSTGRES_DB;" postgres
```

---

## 12. El flujo completo con CI/CD

Con GitHub Actions configurado, el flujo normal es:

```
Tu PC                    GitHub                   Servidor Hetzner
──────                   ──────                   ────────────────
git commit -m "feat: x"
git push origin deployment ──→ Detecta el push
                              Lanza workflow
                              deploy.yml
                                   │
                                   ├── Guarda .last_good_commit
                                   ├── pg_dump (backup previo)
                                   ├── git reset --hard
                                   ├── docker compose up -d --build
                                   ├── alembic upgrade head
                                   └── curl /health (6 intentos)
                                            │
                              Si falla ─────┤
                              (rollback)    └── git reset al commit anterior
                                                docker compose up -d --build

                         Workflow completado ──→ 
                              (verde o rojo)
```

**¿Dónde ver el progreso?**
GitHub → tu repositorio → pestaña **Actions** → **Deploy to Hetzner** → el
último run. Ves cada paso en tiempo real con su output.

**¿Cuánto tarda el deploy completo?**
- Código Python cambia: ~2-3 minutos
- Dependencias cambian: ~5-8 minutos
- El healthcheck puede añadir hasta 60 segundos más

**¿Qué pasa si el workflow falla?**
1. Se activa el job `Rollback on failure`
2. El servidor vuelve al commit que había antes del push
3. Recibes una notificación en GitHub (rojo en Actions)
4. Los datos de BD no se revierten (por eso existe el `pg_dump` previo)
5. Tú investigas el error, arreglas el código, y haces otro push

---

## 13. Backup, wipe y reset del servidor

Este capítulo describe el proceso de partir de cero: hacer backup completo de
todos los datos críticos, reinstalar el servidor limpio, y restaurar el servicio.

**¿Cuándo hacer esto?**
- Cuando el servidor está en mal estado y no hay solución limpia
- Cuando quieres aplicar el hardening completo (usuario `deploy`, ufw, fail2ban)
  en un servidor que antes corría todo como root
- Si el VPS se compromete y quieres empezar limpio

### Paso 1 — Extraer todos los datos críticos (NO SALTARSE)

> **Esta es la parte más importante.** Los datos de clientes son irreversibles.
> Si se pierden en el wipe, no hay recuperación.

Ejecutar desde tu PC local (no desde el servidor):

```bash
# 1. Backup completo de PostgreSQL
ssh root@46.225.215.129 \
  'cd /opt/atendoo && docker compose -f docker-compose.prod.yml exec -T db \
   pg_dump -U $POSTGRES_USER $POSTGRES_DB' \
  | gzip > pg_backup_pre_reset.sql.gz

# Verificar que no está vacío (mínimo ~100KB si hay datos)
ls -lh pg_backup_pre_reset.sql.gz

# Verificar que no está corrupto
gunzip -t pg_backup_pre_reset.sql.gz && echo "OK — backup íntegro" || echo "CORRUPTO — NO continuar"
```

> Si el dump está vacío o corrupto, **aborta el proceso**. No continúes hasta
> tener un backup válido.

```bash
# 2. Descargar .env.prod (tiene TODOS los secretos: WhatsApp, Google, Fernet key, etc.)
scp -i ~/.ssh/id_ed25519 root@46.225.215.129:/opt/atendoo/.env.prod ./env.prod.backup

# 3. Descargar certificados SSL (para no esperar renovación tras el reset)
ssh root@46.225.215.129 'tar czf /tmp/letsencrypt.tar.gz -C /etc letsencrypt'
scp -i ~/.ssh/id_ed25519 root@46.225.215.129:/tmp/letsencrypt.tar.gz ./letsencrypt-backup.tar.gz
```

**Guardar en Bitwarden inmediatamente:**
- `pg_backup_pre_reset.sql.gz` (adjunto)
- `env.prod.backup` (adjunto — contiene `ENCRYPTION_KEY` Fernet, sin ella los tokens de BD son ilegibles)
- `letsencrypt-backup.tar.gz` (adjunto)

### Paso 2 — Snapshot Hetzner (seguro adicional)

En el panel Hetzner Cloud:
- Servidor → **Snapshots** → **Take Snapshot**
- Esto guarda el estado completo del disco. Si algo sale mal en el restore,
  puedes recuperar el snapshot y tienes el servidor como estaba.

### Paso 3 — Reinstalar Ubuntu desde Hetzner

En el panel Hetzner Cloud:
- Servidor → **Reinstall** → **Ubuntu 22.04**
- Proporcionar la misma clave SSH pública durante la instalación

Después de la reinstalación, el servidor arranca limpio. No hay Docker, no hay
datos, no hay nada en `/opt/atendoo`.

### Paso 4 — Ejecutar bootstrap_server.sh

```bash
# Copiar el script al nuevo servidor
scp -i ~/.ssh/id_ed25519 scripts/bootstrap_server.sh root@46.225.215.129:/tmp/

# Ejecutar (tarda 5-10 minutos)
ssh -i ~/.ssh/id_ed25519 root@46.225.215.129 'bash /tmp/bootstrap_server.sh'
```

El script crea el usuario `deploy`, instala Docker, configura ufw/fail2ban, etc.

### Paso 5 — Verificar acceso como deploy (ANTES de deshabilitar root)

Desde otra terminal:
```bash
ssh -i ~/.ssh/id_ed25519 deploy@46.225.215.129 'whoami && docker ps'
```

Si responde `deploy` y Docker funciona, todo bien. Si falla, **no cierres la
sesión de root** hasta resolver el problema.

### Paso 6 — Deshabilitar login de root

Una vez confirmado que `deploy` funciona:
```bash
# Desde la sesión de root
systemctl restart ssh

# Test desde otra terminal (debe fallar):
ssh -i ~/.ssh/id_ed25519 root@46.225.215.129 'whoami'
# → "Permission denied"

# Test deploy (debe funcionar):
ssh -i ~/.ssh/id_ed25519 deploy@46.225.215.129 'whoami'
# → "deploy"
```

### Paso 7 — Obtener certificados SSL

```bash
# Certbot necesita el puerto 80 libre (no puede haber nginx corriendo todavía)
ssh -i ~/.ssh/id_ed25519 deploy@46.225.215.129
sudo certbot certonly --standalone -d atendoo.app --email tu@email.com --agree-tos -n
```

### Paso 8 — Restaurar datos y arrancar servicios

```bash
# Desde local: subir los backups
scp -i ~/.ssh/id_ed25519 env.prod.backup deploy@46.225.215.129:/opt/atendoo/.env.prod
scp -i ~/.ssh/id_ed25519 pg_backup_pre_reset.sql.gz deploy@46.225.215.129:/opt/atendoo/shared/backups/

# Restaurar certificados SSL (como root si es necesario, o con sudo)
scp -i ~/.ssh/id_ed25519 letsencrypt-backup.tar.gz deploy@46.225.215.129:/tmp/
ssh -i ~/.ssh/id_ed25519 deploy@46.225.215.129 'sudo tar xzf /tmp/letsencrypt-backup.tar.gz -C /etc'

# En el servidor como deploy:
ssh -i ~/.ssh/id_ed25519 deploy@46.225.215.129

cd /opt/atendoo
git clone --branch deployment https://github.com/DaniGV63/BotLLM.git .

# Arrancar solo la base de datos primero
docker compose -f docker-compose.prod.yml up -d db
sleep 15

# Restaurar el backup de PostgreSQL
gunzip -c shared/backups/pg_backup_pre_reset.sql.gz \
  | docker compose -f docker-compose.prod.yml exec -T db \
    psql -U $POSTGRES_USER $POSTGRES_DB

# Arrancar todos los servicios
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head

# Verificar
curl https://atendoo.app/health
```

### Paso 9 — Configurar GitHub Actions para el nuevo servidor

```bash
# Generar clave nueva para CI (en local)
ssh-keygen -t ed25519 -f ~/.ssh/atendoo_ci -N "" -C "atendoo-ci"

# Autorizar en el servidor
ssh-copy-id -i ~/.ssh/atendoo_ci.pub deploy@46.225.215.129
```

Actualizar en GitHub → Settings → Secrets:
- `SSH_KEY` → contenido de `~/.ssh/atendoo_ci` (clave privada)
- El resto de secrets no cambian si la IP es la misma

### Paso 10 — Prueba end-to-end

Hacer un commit trivial (ej: añadir un espacio en un comentario) y push:
```bash
git add .
git commit -m "chore: verificar CI/CD post-reset"
git push origin deployment
```

Verificar en GitHub Actions que el workflow completa en verde.

---

## 14. Reglas absolutas

Estas reglas son irrompibles. Cada una nace de un incidente real o de una
consecuencia catastrófica conocida.

**NUNCA `docker compose down`**
```bash
# MAL — borra los volúmenes con los datos de PostgreSQL
docker compose -f docker-compose.prod.yml down

# BIEN — para contenedores sin borrar datos
docker compose -f docker-compose.prod.yml stop
```
`down` destruye los volúmenes `postgres_data` y `redis_data`. Perderías TODOS
los datos de clientes, conversaciones, configuración de tenant, tokens de
WhatsApp y Google Calendar. No hay recuperación sin un backup previo.

**NUNCA subir `.env.prod` al repositorio**
El `.env.prod` contiene claves de API, tokens OAuth, la clave Fernet para
descifrar datos en BD, y credenciales de PostgreSQL. Si llega a GitHub (aunque
sea privado), invalida todos los secretos y hay que rotar todo.

**NUNCA reutilizar `id_ed25519` para CI/CD**
Tu clave personal no debe ir a GitHub Secrets. Si GitHub se compromete,
comprometen también tu acceso personal. La clave CI (`atendoo_ci`) es
sacrificable: si se filtra, la eliminas del servidor y generas otra sin afectar
tu acceso personal.

**NUNCA hacer deploy sin `--build`**
```bash
# MAL — el código nuevo no entra en los contenedores
git pull
docker compose -f docker-compose.prod.yml up -d

# BIEN — reconstruye la imagen con el código nuevo
git reset --hard origin/deployment
docker compose -f docker-compose.prod.yml up -d --build
```

**NUNCA conectarse como root después del reset**
Root tiene acceso ilimitado. Si alguien roba tu clave SSH y es root, puede
hacer cualquier cosa. El usuario `deploy` tiene permisos acotados — incluso
si se compromete, el daño es limitado.

---

## 15. Qué hacer si algo falla

### La app devuelve 502 Bad Gateway

nginx recibe la petición pero no puede conectarse a la app (puerto 8000).

```bash
# 1. Ver si el contenedor app está corriendo
docker compose -f docker-compose.prod.yml ps

# 2. Si está unhealthy o exited, ver los logs
docker compose -f docker-compose.prod.yml logs --tail=50 app

# 3. Reintentar arranque
docker compose -f docker-compose.prod.yml up -d --build app
```

### Alembic falla con "relation already exists"

La migración intenta crear algo que ya existe.

```bash
# Ver el estado de las migraciones
docker compose -f docker-compose.prod.yml exec app alembic current
docker compose -f docker-compose.prod.yml exec app alembic history

# Marcar la migración como aplicada sin ejecutarla (si sabes que ya está)
docker compose -f docker-compose.prod.yml exec app alembic stamp head
```

### El deploy de CI/CD se queda colgado

Si el job de GitHub Actions no termina:
- Puede ser que `docker compose up --build` esté descargando una imagen grande
- O que `alembic upgrade head` está esperando un lock de BD

Entrar al servidor y ver qué pasa:
```bash
ssh -i ~/.ssh/id_ed25519 deploy@46.225.215.129
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f app
```

### El healthcheck falla pero la app parece funcionar

A veces nginx tarda en arrancar después de la app. El healthcheck de CI/CD hace
6 intentos con 10s de espera cada uno (total 60s). Si necesitas más tiempo,
aumenta los intentos en `.github/workflows/deploy.yml`.

### Rollback manual

Si el rollback automático también falla o no hay `.last_good_commit`:

```bash
# Ver el historial de commits
git log --oneline -10

# Volver a un commit específico
git reset --hard <HASH_DEL_COMMIT>
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head
```
