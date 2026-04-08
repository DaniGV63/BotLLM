# Onboarding WhatsApp — Guía paso a paso para nuevo cliente

Guía completa para activar el bot de WhatsApp de Atendoo para un nuevo cliente (fisioterapeuta).
Incluye configuración de Meta Business Suite, Meta Developers, y conexión con el servidor.

**Tiempo estimado:** 30-60 minutos (sin contar propagación DNS ni verificación de negocio).

---

## Glosario de roles

En todo el documento se usan estos roles. Es importante no confundirlos:

| Rol | Quién es | Ejemplo |
|-----|----------|---------|
| **Tú (administrador Atendoo)** | El desarrollador/operador que configura todo. Usa su cuenta personal de Meta. | Daniel (cuenta Facebook personal, email daniel.gomezverde@...) |
| **El fisio (cliente/tenant)** | El fisioterapeuta que contrata Atendoo. Su número de teléfono será el del bot. | Clínica Fisio Madrid (teléfono +34 6XX XXX XXX) |
| **Los pacientes** | Usuarios finales que escriben al bot por WhatsApp. | Pacientes del fisio |

### Qué cuenta/email se usa en cada paso:

| Paso | Cuenta que se usa | Por qué |
|------|-------------------|---------|
| 1. Meta Business | **Tu cuenta personal** de Facebook/Meta | Tú administras el portfolio de todos los clientes |
| 2. Meta Developers | **Tu cuenta personal** de Meta Developers | Tú creas y gestionas las apps |
| 3-4. WABA y pago | **Tu cuenta** en Meta Business Suite | El portfolio es tuyo; la tarjeta puede ser del fisio o tuya |
| 5. Registrar número | **El número del fisio** (su móvil/SIM) | Es el número que los pacientes verán en WhatsApp |
| 6. Registro API | **Token del System User** (técnico, no personal) | Llamada API, no importa quién la ejecuta |
| 7. System User | **Tu cuenta** en Meta Business Suite | Tú gestionas los usuarios del sistema |
| 8-9. Webhook | **Token del System User** + **tu cuenta** en Meta Developers | Configuración técnica |
| 10. Tenant en BD | **Panel superadmin de Atendoo** (tu login) | Datos del fisio en la BD |
| 12. Test E2E | **Cualquier móvil** (tuyo, del fisio, de un paciente) | Enviar un "Hola" al número del bot |

---

## Requisitos previos

- [ ] Servidor Atendoo desplegado y funcionando (ver `DEPLOY.md`)
- [ ] Tenant creado en BD con `seed.py` o panel superadmin
- [ ] Número de teléfono **del fisio** (SIM real, NO VoIP/virtual) — este será el número del bot
- [ ] Ese número **NO debe tener WhatsApp instalado** (el fisio debe desinstalarlo antes de empezar)
- [ ] **Tu** cuenta personal de Facebook/Meta (la del administrador de Atendoo)
- [ ] Tarjeta de crédito/débito para método de pago en Meta (puede ser tuya o del fisio)

---

## Paso 1: Crear cuenta Meta Business (si no existe)

> **Quién:** Tú (administrador Atendoo), con tu cuenta personal de Facebook.

1. Ir a **[business.facebook.com](https://business.facebook.com)**
2. Pulsar **"Crear cuenta"**
3. Rellenar:
   - **Nombre del portfolio:** nombre del negocio del fisio (ej. "Clínica Fisio Madrid")
   - **Nombre y email:** los tuyos (tú administras el portfolio)
4. Confirmar email

### Dónde se guarda:
| Dato | Dónde |
|------|-------|
| Portfolio empresarial ID | Anotar para referencia interna |

---

## Paso 2: Crear app en Meta Developers

> **Quién:** Tú, con tu cuenta de Meta Developers (misma que tu Facebook personal).

1. Ir a **[developers.facebook.com](https://developers.facebook.com)** → **"Mis aplicaciones"** → **"Crear aplicación"**
2. Seleccionar tipo: **"Empresa"**
3. Nombre de la app: nombre descriptivo (ej. "Bot Fisio Madrid")
4. Asociar al portfolio empresarial creado en el paso 1
5. Pulsar **"Crear"**

### Añadir producto WhatsApp:
1. En el panel de la app → **"Añadir producto"**
2. Buscar **"WhatsApp"** → **"Configurar"**
3. Seleccionar el portfolio empresarial correcto

### Dónde se guarda:
| Dato | Dónde |
|------|-------|
| App ID | Visible en la barra superior de Meta Developers |
| App Secret (`META_APP_SECRET`) | Meta Developers → Configuración de la aplicación → Básica → Clave secreta → `.env.prod` |

---

## Paso 3: Crear cuenta de WhatsApp Business (WABA)

> **Quién:** Tú, en Meta Business Suite.

Al configurar WhatsApp en el paso anterior, Meta crea automáticamente una WABA. Verificar:

1. **Meta Business Suite** → **Ajustes** (engranaje) → **Cuentas** → **Cuentas de WhatsApp**
2. Debería aparecer una WABA con el nombre del negocio
3. Anotar el **Identificador** (WABA ID)

### Importante — Evitar WABAs duplicadas:
- Si aparecen varias WABAs, quedarse solo con UNA
- Eliminar las sobrantes con los "..." → Eliminar
- Un número de teléfono solo puede pertenecer a UNA WABA

### Dónde se guarda:
| Dato | Dónde |
|------|-------|
| WABA ID | Meta Business Suite + BD del tenant (`whatsapp_business_account_id`) |

---

## Paso 4: Añadir método de pago a la WABA

> **Quién:** Tú, en Meta Business Suite. La tarjeta puede ser tuya o del fisio (según acuerdo comercial).

1. **Meta Business Suite** → **Facturación y pagos** → pestaña **"Cuentas de WhatsApp Business"**
2. Buscar la WABA del cliente → **"Añadir método de pago"**
3. Introducir tarjeta de crédito/débito

### Nota sobre costes:
- Las primeras 1000 conversaciones/mes iniciadas por el cliente son **gratuitas**
- Solo se cobra si el bot inicia la conversación con un template message
- Para el uso normal (pacientes escriben primero) el coste es ~0€

---

## Paso 5: Registrar el número de teléfono del fisio

> **Quién:** Tú configuras en Meta Developers, pero el **número es del fisio** (su móvil/SIM). El fisio necesita tener el teléfono a mano para recibir el SMS de verificación.

### Pre-requisito: desinstalar WhatsApp del teléfono del fisio
El número que se va a registrar en la Cloud API **no puede tener WhatsApp instalado** simultáneamente. El fisio debe:
1. Hacer backup de sus chats de WhatsApp (si quiere conservarlos)
2. Desinstalar WhatsApp del teléfono
3. Mantener la SIM activa (necesaria para recibir SMS de verificación)

### Registrar en Meta:
1. **Meta Developers** (con tu cuenta) → tu app → **WhatsApp** → **Configuración de la API**
2. En **"Paso 1: Selecciona números de teléfono"**, sección **"Desde"**:
   - Si el número no aparece → pulsar **"Añadir número de teléfono"** (Step 5 del panel)
   - Introducir **el número del fisio** con código de país (ej. `+34 6XX XXX XXX`)
   - Seleccionar verificación por **SMS** o **Llamada**
   - El fisio recibe el código en su teléfono → te lo dicta → lo introduces en Meta
3. Anotar el **Phone Number ID** que aparece bajo el desplegable "Desde"

### Dónde se guarda:
| Dato | Dónde |
|------|-------|
| Phone Number ID | Meta Developers + BD del tenant (`whatsapp_phone_number_id`) |
| Número de teléfono | BD del tenant |

---

## Paso 6: Completar registro del número en la Cloud API

Después de añadir el número, su estado aparecerá como **"Pendiente"** en:
- Meta Business Suite → Ajustes → Cuentas → Cuentas de WhatsApp → [WABA] → Números de teléfono

Para activarlo, ejecutar en terminal (sustituir `<PHONE_NUMBER_ID>` y `<TOKEN>`):

```powershell
$token = "<TOKEN_DEL_SYSTEM_USER>"
$phoneId = "<PHONE_NUMBER_ID>"
$pin = "<PIN_6_DIGITOS>"
curl.exe -X POST "https://graph.facebook.com/v25.0/$phoneId/register" -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "{`"messaging_product`": `"whatsapp`", `"pin`": `"$pin`"}"
```

El PIN es un código de 6 dígitos que TÚ eliges (verificación en dos pasos). **Apuntarlo** — necesario si se re-registra el número.

Respuesta esperada: `{"success": true}`

Verificar que el estado cambia a **"Conectado"** en Meta Business Suite.

### Dónde se guarda:
| Dato | Dónde |
|------|-------|
| PIN 2FA del número | Documento interno / gestor de contraseñas (NO en código) |

---

## Paso 7: Crear System User y generar token permanente

> **Quién:** Tú, en Meta Business Suite. Este usuario es técnico (no es una persona real), sirve para que el servidor de Atendoo se autentique con la API de Meta.

1. **Meta Business Suite** → **Ajustes** → **Usuarios** → **Usuarios del sistema**
2. Pulsar **"+ Añadir"**
3. Nombre: algo descriptivo (ej. "Bot Atendoo")
4. Rol: **Admin**
5. Pulsar **"Crear"**

### Asignar activos al System User:

**Método A — Desde el System User:**
1. Seleccionar el System User recién creado
2. Pestaña **"Activos asignados"** → **"Añadir activos"**
3. Añadir:
   - **Aplicaciones** → [nombre de la app] → **Control total**
   - **Cuentas de WhatsApp** → [WABA del fisio] → **Control total**

**Método B — Desde la WABA (usar si el Método A no muestra la WABA):**

Este es el camino que suele funcionar cuando la WABA no aparece en la lista de activos:

1. En el menú lateral izquierdo → **Cuentas** → **Cuentas de WhatsApp**
2. Seleccionar la WABA del fisio en la lista central
3. Pulsar el botón **"Asignar acceso"** (parte superior de los detalles de la cuenta)
4. En el buscador, seleccionar el System User (ej. "Bot Atendoo" o "Integración Landbot")
5. Activar el interruptor de **"Control total"** (o "Administrar cuenta de WhatsApp")
6. Pulsar **"Asignar"**

Verificar: volver a **Usuarios del sistema** → seleccionar el System User → pestaña "Activos asignados" → debería aparecer la WABA con "Control total".

Si los permisos no se reflejan inmediatamente en las llamadas API, pulsar **"Generar identificador"** para crear un token fresco.

### Generar token permanente:
1. En la pantalla del System User → **"Generar identificador"**
2. Seleccionar la **app** correcta
3. Caducidad: **Nunca**
4. Scopes (permisos): marcar:
   - `whatsapp_business_management`
   - `whatsapp_business_messaging`
5. **"Generar identificador"** → **copiar el token inmediatamente** (no se puede ver después)

### Dónde se guarda:
| Dato | Dónde |
|------|-------|
| System User ID | Meta Business Suite (referencia) |
| Token permanente | BD del tenant (`whatsapp_token`, cifrado con Fernet). Se configura desde panel superadmin o script Python |

---

## Paso 8: Suscribir la app a la WABA

Este paso es **crítico** — sin él, los mensajes no llegan al webhook.

```powershell
$token = "<TOKEN_DEL_SYSTEM_USER>"
$wabaId = "<WABA_ID>"
curl.exe -X POST "https://graph.facebook.com/v25.0/$wabaId/subscribed_apps" -H "Authorization: Bearer $token"
```

Respuesta esperada: `{"success": true}`

---

## Paso 9: Configurar webhook

1. **Meta Developers** → tu app → **WhatsApp** → **Configuración**
2. Sección **"Webhook"**:
   - **URL de devolución de llamada:** `https://<DOMINIO>/webhook`
   - **Identificador de verificación:** el valor de `META_VERIFY_TOKEN` del `.env.prod`
3. Pulsar **"Verificar y guardar"**
4. En la tabla de **"Campos de webhook"**, suscribir: **`messages`** (toggle azul)

### Dónde se guarda:
| Dato | Dónde |
|------|-------|
| META_VERIFY_TOKEN | `.env.prod` en el VPS |
| Webhook URL | Meta Developers (configuración de la app) |

---

## Paso 10: Configurar datos del tenant en BD

Asegurarse de que el tenant en la BD tiene todos los campos correctos:

| Campo BD | Valor |
|----------|-------|
| `whatsapp_phone_number_id` | Phone Number ID del paso 5 |
| `whatsapp_token` | Token del System User del paso 7 (se cifra automáticamente) |
| `name` | Nombre del negocio |
| `bot_name` | Nombre del bot (ej. "Asistente de Clínica Fisio") |
| `timezone` | `Europe/Madrid` (o la que corresponda) |

Configurar desde:
- **Panel superadmin** (`https://<DOMINIO>/admin` → login como superadmin)
- O con script Python dentro del contenedor

---

## Paso 11: Activar modo producción

1. **Meta Developers** → barra superior → toggle **"En desarrollo"** → **"En producción"**
2. Si pide verificación de negocio:
   - Meta Business Suite → Centro de seguridad → Verificación de la empresa
   - Subir documentos (NIF, escrituras, alta censal)
   - Esperar aprobación (10 min - 14 días)
3. Si permite cambiar sin verificación → activar directamente

### Modo desarrollo vs producción:
| Aspecto | Desarrollo | Producción |
|---------|-----------|------------|
| Destinatarios | Solo 5 registrados manualmente | Cualquiera |
| Mensajes/24h | 250 conversaciones | Según tier |
| Webhook | Funciona normal | Funciona normal |
| Coste | Gratuito | 1000 conv. gratis/mes |

**Para demos sin verificación de empresa:** el modo desarrollo funciona bien con hasta 5 números de prueba.

---

## Paso 12: Test E2E

> **Quién:** Cualquier persona (tú, el fisio, un paciente de prueba). El que envía el mensaje actúa como paciente.

1. Abrir logs del servidor en una terminal:
   ```bash
   ssh -i <CLAVE_SSH> root@<IP_VPS> "docker logs <NOMBRE_CONTENEDOR_APP> --tail 20 -f"
   ```

2. Desde un móvil (que NO sea el del fisio/bot), buscar **el número del fisio** en WhatsApp y enviar **"Hola"**
   - Si el número no aparece en WhatsApp: esperar 10-15 minutos tras el registro

3. Verificar en los logs:
   - `webhook_received` — mensaje recibido ✓
   - `intent_detected` — intención clasificada ✓
   - `response_generated` — respuesta generada ✓
   - `message_sent` — respuesta enviada ✓

4. Verificar que llega la respuesta al WhatsApp del móvil que envió el mensaje

---

## Resumen de credenciales por cliente

| Credencial | Dónde se genera | Dónde se almacena |
|------------|----------------|-------------------|
| App ID | Meta Developers (auto) | Referencia interna |
| App Secret (`META_APP_SECRET`) | Meta Developers → Config → Básica | `.env.prod` |
| WABA ID | Meta Business Suite → Cuentas WA | BD tenant + referencia |
| Phone Number ID | Meta Developers → WA → API Setup | BD tenant |
| Token System User (permanente) | Meta Business Suite → Usuarios sistema | BD tenant (cifrado Fernet) |
| PIN 2FA del número | Elegido al registrar | Gestor de contraseñas |
| META_VERIFY_TOKEN | Generado manualmente | `.env.prod` |
| META_APP_SECRET | Meta Developers | `.env.prod` |
| Webhook URL | Configurado en Meta | Meta Developers |

---

## Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| No llegan webhooks | App no suscrita a la WABA | Ejecutar paso 8 (`subscribed_apps`) |
| Error "Object does not exist" | System User sin permisos sobre la WABA | Ejecutar paso 7 (asignar activos) |
| Número en estado "Pendiente" | Falta registro vía API | Ejecutar paso 6 (`/register`) |
| "Falta método de pago" al enviar template | WABA sin tarjeta | Ejecutar paso 4 |
| Número no aparece en WhatsApp | Registro reciente, propagación | Esperar 10-15 min |
| `curl` falla en PowerShell | PS usa alias `curl` = `Invoke-WebRequest` | Usar `curl.exe` en lugar de `curl` |
| Número duplicado en dos WABAs | Creación accidental | Eliminar WABA sobrante |
| Bot no responde pero logs OK | Token expirado o incorrecto en BD | Regenerar token (paso 7) y actualizar en BD |

---

## Fase 3: Verificación post-deploy (pendiente)

Tras completar el onboarding de WhatsApp, ejecutar estas verificaciones:

- [ ] 3.1 Health check: `curl https://<DOMINIO>/health`
- [ ] 3.2 SSL y headers: `curl -I https://<DOMINIO>`
- [ ] 3.3 Landing page: verificar en navegador + OG tags
- [ ] 3.4 robots.txt: `curl https://<DOMINIO>/robots.txt`
- [ ] 3.5 Panel admin: login, calendario, chat WebSocket
- [ ] 3.6 Test E2E WhatsApp: enviar "Hola" al bot ← ya hecho en paso 12
- [ ] 3.7 Google OAuth: autorizar Google Calendar desde panel admin
- [ ] 3.8 Email routing: verificar envío de emails
- [ ] 3.9 Rate limiting login: 11 intentos → 429 en el intento 11
