# Onboarding Google OAuth — Atendoo

Guía para autorizar Google Calendar + Gmail en un tenant nuevo.
Ejecutar tras el deploy inicial y antes de activar el bot con pacientes reales.

---

## Prerequisitos

- Tenant creado en BD (via panel superadmin o seed)
- Variables `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` configuradas en `.env.prod`
- App desplegada y accesible en el dominio de producción

---

## Paso 1 — Configurar redirect URI en Google Cloud Console

1. Ir a [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials
2. Click en el OAuth 2.0 Client ID de Atendoo
3. En **Authorized redirect URIs** → verificar que está: `https://<DOMINIO>/oauth/callback`
4. Si no está, añadirla y guardar

> Para atendoo.app: `https://atendoo.app/oauth/callback`

---

## Paso 2 — Obtener JWT de SuperAdmin

En PowerShell (desde cualquier máquina):

```powershell
$r = Invoke-RestMethod -Method POST -Uri https://<DOMINIO>/admin/login `
  -ContentType "application/json" `
  -Body '{"username": "superadmin", "password": "<PASSWORD>"}'
$TOKEN = $r.access_token
```

El token dura 1 año. Para referencia, el token actual está en `.env.prod` bajo `SUPERADMIN_JWT`.

---

## Paso 3 — Obtener el tenant_id

```powershell
Invoke-RestMethod -Uri https://<DOMINIO>/superadmin/tenants `
  -Headers @{Authorization="Bearer $TOKEN"}
```

Buscar el tenant por `slug` o `nombre_negocio` y copiar su `id` (UUID).

```powershell
$TENANT_ID = "<UUID del tenant>"
```

---

## Paso 4 — Obtener la URL de consent de Google

```powershell
$resp = Invoke-WebRequest `
  -Uri "https://<DOMINIO>/oauth/google/start?tenant_id=$TENANT_ID" `
  -Headers @{Authorization="Bearer $TOKEN"} `
  -MaximumRedirection 0 -UseBasicParsing -ErrorAction SilentlyContinue
$resp.RawContent -split "`n" | Select-String "location:"
```

El resultado es una URL `https://accounts.google.com/o/oauth2/v2/auth?...`.

> ⚠️ El `state` de esa URL expira en **10 minutos**. Completar el siguiente paso antes.

---

## Paso 5 — Autorizar en el navegador

1. Copiar la URL completa del paso anterior
2. Pegarla en el navegador
3. Loguearse con la **cuenta Google del fisio/clínica** (la que tiene el Google Calendar con las citas y desde la que se envían emails)
4. Autorizar los permisos: **Google Calendar** + **Gmail Send**
5. Google redirige a `https://<DOMINIO>/oauth/callback`
6. Debe aparecer: **"✓ Google autorizado — Tokens guardados para \<Nombre Negocio\>"**

---

## Paso 6 — Verificar

Opción rápida: enviar un WhatsApp al bot pidiendo una cita. Si responde con slots disponibles del calendario, Google Calendar está funcionando.

Opción técnica desde el VPS:

```bash
docker exec atendoo-prod-app-1 python -c "
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from sqlalchemy import select
import uuid

async def main():
    async with AsyncSessionLocal() as s:
        r = await s.execute(select(Tenant).where(Tenant.id == uuid.UUID('$TENANT_ID')))
        t = r.scalar_one()
        print('access_token:', 'OK' if t.google_access_token else 'VACÍO')
        print('refresh_token:', 'OK' if t.google_refresh_token else 'VACÍO')

asyncio.run(main())
"
```

Ambos deben mostrar `OK`.

---

## Notas

- El **refresh_token** solo lo devuelve Google la primera vez que se autoriza, o si se fuerza con `prompt=consent` (ya configurado en el código). Si se pierde, hay que revocar el acceso en [myaccount.google.com/permissions](https://myaccount.google.com/permissions) y repetir el flujo.
- La cuenta que autoriza debe ser la misma que tiene acceso al Google Calendar configurado en `google_calendar_id` del tenant.
- Si el fisio cambia de cuenta Google, hay que repetir este proceso con la nueva cuenta.
