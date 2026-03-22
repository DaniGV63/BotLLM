Ready for review
Select text to add comments on the plan
BotLLM v1.0 — Plan de Pruebas, Configuración y Roadmap
Contexto
BotLLM v1.0 está construido y pusheado. Antes de ponerlo en producción real necesitamos:

Configurar todos los servicios externos (Meta, Google, LLM)
Probar localmente con ngrok
Desplegar en Hetzner CX23 y probar en producción
Identificar errores comunes y sus soluciones
Definir features adicionales y roadmap futuro
PARTE 1 — Configuración de permisos y servicios externos
1.1 Meta Developer Console (WhatsApp Business)
Prerrequisitos:

Cuenta de Meta Business verificada
App creada en Meta Developer Console con producto "WhatsApp" añadido
Pasos:

Obtener Phone Number ID — En WhatsApp > Getting Started > copiar el Phone number ID del número de pruebas (o del número de producción si ya lo tienes). Guardarlo para seed.py
Obtener Access Token — En WhatsApp > Getting Started > generar token temporal (60 días) o configurar System User para token permanente. Este es el whatsapp_token que va encriptado en BD
Copiar App Secret — En Settings > Basic > App Secret. Va en META_APP_SECRET del .env
Configurar Webhook — En WhatsApp > Configuration:
Callback URL: https://TU_NGROK_URL/webhook (dev) o https://tudominio.com/webhook (prod)
Verify Token: el UUID que genera seed.py (se muestra en consola al hacer seed)
Suscribirse a: messages
Añadir número de pruebas — En WhatsApp > Getting Started > añadir tu número personal como receptor de pruebas
Token permanente (producción):

Settings > Business Settings > System Users > crear System User
Asignar permiso whatsapp_business_messaging
Generar token → guardar como whatsapp_token del tenant
1.2 Google Cloud Console (Calendar + Gmail)
Prerrequisitos:

Proyecto en Google Cloud Console
Pasos:

Habilitar APIs:
Google Calendar API
Gmail API
Crear credenciales OAuth 2.0:
Tipo: Aplicación web
Redirect URIs autorizados: http://localhost:8000/oauth/callback (dev) + https://tudominio.com/oauth/callback (prod)
Copiar Client ID → .env GOOGLE_CLIENT_ID
Copiar Client Secret → .env GOOGLE_CLIENT_SECRET
Pantalla de consentimiento OAuth:
Tipo: Externo (para pruebas) o Interno (si tienes Workspace)
Scopes: calendar, gmail.send
Añadir tu email como usuario de prueba (si tipo Externo en modo Testing)
Obtener tokens del fisioterapeuta:
Necesitas que el fisio (dueño del calendario) autorice la app
Los tokens (access + refresh) se guardan encriptados en la BD vía panel admin
El access token expira (~1h), el refresh token es persistente
Cómo obtener los tokens iniciales:

Opción rápida: usar OAuth Playground de Google → autorizar con los scopes → copiar access_token y refresh_token → pegarlos en el panel admin /admin > pestaña Google
Opción correcta: implementar flujo OAuth en el panel admin (podría ser feature futura)
1.3 API Key del LLM
OpenAI (opción por defecto):

Ir a platform.openai.com → API Keys → crear key
Guardar en .env como OPENAI_API_KEY
Modelo: gpt-4o-mini (~$0.15/1M input tokens, ~$0.60/1M output tokens)
Gemini (alternativa):

Ir a aistudio.google.com → API Keys → crear
Guardar en .env como GEMINI_API_KEY
Cambiar LLM_PROVIDER=gemini y LLM_MODEL=gemini-2.5-flash
1.4 Claves de encriptación
# ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# SECRET_KEY (JWT)
python -c "import secrets; print(secrets.token_urlsafe(32))"
PARTE 2 — Pruebas en local
2.1 Levantar infraestructura local
# 1. Docker: solo PG + Redis
docker compose up -d

# 2. Migraciones
alembic upgrade head

# 3. Seed (crear tenant) — anotar el verify_token que muestra
python seed.py

# 4. Arrancar uvicorn
uvicorn app.main:app --reload
Verificar: http://localhost:8000/health → {"status": "ok"}

2.2 Probar panel admin
Abrir http://localhost:8000/admin
Login: admin / admin_temporal_2024
Pestaña Datos: verificar datos del tenant, activar/desactivar bot
Pestaña Google: pegar tokens de Google OAuth (access + refresh)
Pestaña Conversaciones: vacía hasta que haya mensajes
2.3 Configurar ngrok
ngrok http 8000
Copiar la URL HTTPS (ej: https://abc123.ngrok.io).

2.4 Configurar webhook en Meta
Meta Developer Console → WhatsApp → Configuration
Callback URL: https://abc123.ngrok.io/webhook
Verify Token: el UUID de seed.py
Click "Verify and Save"
Suscribirse a campo: messages
2.5 Actualizar tokens del tenant
En el panel admin o directamente en BD, asegurarse de que el tenant tiene:

whatsapp_token: access token de Meta
meta_app_secret: App Secret de Meta (si es per-tenant)
whatsapp_phone_number_id: correcto
google_access_token + google_refresh_token: de Google OAuth
2.6 Tests funcionales desde WhatsApp
Enviar mensajes desde tu móvil al número de WhatsApp Business:

#	Test	Mensaje	Respuesta esperada
1	Health check	—	/health responde OK
2	FAQ básica	"¿Qué horario tenéis?"	Responde con horarios de negocio.md
3	FAQ precios	"¿Cuánto cuesta una sesión?"	Responde con precios
4	RGPD	(primer mensaje)	Incluye línea de consentimiento RGPD
5	Agendar cita	"Quiero pedir cita"	Ofrece huecos de Calendar
6	Elegir hora	"El jueves a las 10"	Pide nombre + confirmación
7	Confirmar	"Sí, soy María García"	Crea evento en Calendar, confirma
8	Cancelar cita	"Quiero cancelar mi cita"	Busca cita por teléfono, pide confirmación
9	Confirmar cancel	"Sí, cancela"	Elimina evento de Calendar
10	Derivar humano	"Quiero hablar con una persona"	Envía email al fisio + confirma al paciente
11	Msg no texto	Enviar foto o audio	"Solo puedo leer mensajes de texto"
12	Saludo simple	"Hola"	Saludo breve + "¿en qué puedo ayudarte?"
13	Continuidad	Estar en medio de agendar + decir "sí"	Mantiene contexto de agendar_cita
14	Safety net	LLM devuelve action sin confirmación previa	No ejecuta la acción (log warning)
Verificar en cada test:

Logs en terminal (structlog JSON) — intent detectado, action ejecutada
Panel admin → Conversaciones → ver mensajes con intent y action
Google Calendar → verificar eventos creados/cancelados
Gmail → verificar emails de derivación recibidos
2.7 Tests de edge cases
#	Caso	Qué probar
1	Mensaje duplicado	Enviar mismo mensaje rápido → solo se procesa 1 vez (dedup Redis)
2	Webhook status	Meta envía "delivered"/"read" → devuelve 200, no procesa
3	Expiración 24h	Esperar >24h (o modificar TTL en test) → conversación se resetea
4	Error LLM	Poner API key inválida → fallback + email de alerta
5	Calendar sin token	No configurar Google tokens → error manejado, derivar a humano
6	Bot desactivado	Desactivar bot en admin → verificar que no responde
PARTE 3 — Despliegue en producción (Hetzner)
3.1 Pre-requisitos
 VPS Hetzner CX23 creado (Ubuntu 22.04)
 Dominio registrado
 Dominio apuntando a IP del VPS en Cloudflare (DNS only, proxy OFF)
 Firewall Hetzner: puertos 22, 80, 443 abiertos
 .env.prod preparado con todos los valores reales
3.2 Ejecutar deploy.sh
# Copiar .env.prod al servidor
scp .env.prod root@IP_VPS:/opt/botllm/.env.prod

# Ejecutar deploy
export DOMAIN="tudominio.com"
export EMAIL="tu@email.com"
export REPO_URL="https://github.com/tu-usuario/BotLLM.git"
scp deploy.sh root@IP_VPS:/root/ && ssh root@IP_VPS 'chmod +x deploy.sh && ./deploy.sh'
3.3 Verificaciones post-deploy
# Health check
curl https://tudominio.com/health

# Panel admin
# Navegador: https://tudominio.com/admin

# Logs
ssh root@IP_VPS 'docker compose -f /opt/botllm/docker-compose.prod.yml logs -f app'
3.4 Cambiar webhook en Meta a producción
Meta Developer Console → WhatsApp → Configuration
Cambiar Callback URL de ngrok a: https://tudominio.com/webhook
Verificar
3.5 Repetir tests funcionales
Repetir la tabla de tests de la Parte 2 (§2.6) apuntando al dominio de producción. Verificar que todo funciona igual que en local.

3.6 Token permanente de WhatsApp
El token temporal de Meta expira en 60 días. Para producción:

Meta Business Settings → System Users → crear
Asignar permisos de whatsapp_business_messaging
Generar token permanente
Actualizar en panel admin o BD
PARTE 4 — Posibles errores y troubleshooting
4.1 Errores de configuración
Error	Síntoma	Solución
ENCRYPTION_KEY vacía	Error al arrancar o al encriptar/desencriptar tokens	Generar con Fernet.generate_key() y poner en .env
SECRET_KEY vacía	JWT no funciona → 401 en admin	Generar con secrets.token_urlsafe(32)
META_APP_SECRET incorrecto	Webhook devuelve 403 (HMAC inválido)	Copiar exacto de Meta > Settings > Basic
OPENAI_API_KEY inválida	Error 401 en detect_intent → fallback a "faq" siempre	Verificar key en platform.openai.com
DATABASE_URL wrong host	App no arranca → connection refused	Dev: localhost, Prod: db (nombre servicio Docker)
REDIS_URL wrong host	App arranca pero sin caché → lento	Dev: localhost, Prod: redis (nombre servicio Docker)
4.2 Errores de Meta/WhatsApp
Error	Síntoma	Solución
Webhook no verifica	Meta dice "Callback URL failed"	Verificar: ngrok corriendo, verify_token correcto, app arrancada
Mensajes no llegan	Bot no responde	Verificar: suscripción a messages, número añadido en test, logs del webhook
Error 401 al enviar	Bot recibe pero no responde	whatsapp_token expirado o inválido → regenerar
Rate limit Meta	Error 429	Demasiados mensajes → esperar o solicitar aumento de límite
"This message was not delivered"	Meta no entrega	Número no verificado o fuera de ventana de 24h (regla de Meta)
4.3 Errores de Google Calendar/Gmail
Error	Síntoma	Solución
Token expirado sin refresh	401 al consultar Calendar	Necesita re-autorizar OAuth → obtener nuevos tokens
Scopes insuficientes	403 "Insufficient Permission"	Re-autorizar con scopes calendar + gmail.send
Calendar ID incorrecto	No encuentra huecos	Verificar google_calendar_id en admin (usar "primary" para el calendario principal)
Pantalla de consentimiento no verificada	Solo funciona con usuarios de prueba	En Google Cloud > OAuth consent screen > añadir emails de prueba, o publicar app
Cuota API excedida	Error 429 en Calendar	Google Calendar API tiene 1M queries/día → no debería pasar con 1 clínica
4.4 Errores de Docker/producción
Error	Síntoma	Solución
Nginx 502 Bad Gateway	App no arrancó aún	Esperar a healthcheck de db/redis → docker compose logs app
Certificado SSL inválido	Navegador muestra "Not Secure"	Verificar Cloudflare en DNS only, verificar certbot certificates
Certbot falla	"Challenge failed"	Puerto 80 cerrado en firewall, o Cloudflare proxy ON
OOM Killer	Contenedor se reinicia	docker stats → si >3.5GB, reducir workers a 1
PG "connection refused" en prod	App no conecta a BD	Verificar DATABASE_URL usa db no localhost en .env.prod
Redis AUTH error	"NOAUTH Authentication required"	Verificar REDIS_URL tiene password en .env.prod
Static files 404	Admin no carga CSS	Verificar volumen ./static:/app/static:ro en nginx del compose
Alembic falla en prod	"Target database is not up to date"	Ejecutar docker compose exec app alembic upgrade head manualmente
4.5 Errores de lógica del bot
Error	Síntoma	Solución
Intent siempre "faq"	No agenda citas	API key LLM inválida → fallback permanente. O prompt mal cargado
Horarios inventados	Ofrece huecos que no existen	Calendar no conectado → LLM alucina. Verificar tokens Google
Nombre se pide repetidamente	"¿Cómo te llamas?" cada mensaje	nombre_paciente no se guarda → verificar que conversation.nombre_paciente se persiste
Safety net siempre bloquea	Nunca ejecuta acciones de Calendar	Palabra de confirmación no está en CONFIRMATION_WORDS → revisar agent.py
JSON parse error	generate_response falla	LLM no devuelve JSON válido → verificar que json_mode=True está activo
PARTE 5 — Features que vendrían bien (no implementadas)
5.1 Alta prioridad (impacto inmediato)
Flujo OAuth integrado en el admin — Actualmente hay que copiar tokens manualmente. Un botón "Conectar Google" en el panel admin que haga el flujo OAuth completo sería mucho más cómodo para el fisio.

Recordatorios automáticos — Enviar WhatsApp 24h antes de la cita: "Recuerda que mañana tienes cita a las 10:00. ¿Confirmas o prefieres cancelar?" Esto reduce no-shows. Se implementa con un cron job que revisa Calendar.

Dashboard con métricas básicas — En el admin: total de mensajes hoy/semana, citas agendadas, citas canceladas, tasa de derivación, tiempo medio de respuesta. Son queries simples sobre la tabla messages.

Multi-idioma — El bot actual solo habla español. Detectar idioma del paciente (muchos fisios tienen clientes extranjeros) y responder en su idioma. Basta añadir instrucción al prompt.

Confirmación de cita por WhatsApp — Tras crear cita, enviar mensaje resumen con todos los datos y un recordatorio de la política de cancelación.

5.2 Media prioridad (mejora la experiencia)
Lista de espera — Si no hay huecos disponibles, ofrecer apuntarse a lista de espera. Si se cancela una cita, avisar automáticamente al primero de la lista.

Feedback post-cita — 2h después de la cita, enviar mensaje: "¿Qué tal tu sesión? ¿Quieres agendar la próxima?" Genera engagement y recurrencia.

Historial de citas del paciente — Que el bot pueda decir "Tu última cita fue el 15/03 con servicio X". Requiere almacenar historial de eventos en BD (ahora solo mira Calendar).

Mensajes de ausencia — Si el bot está desactivado (bot_activo=false), enviar mensaje automático: "Estamos fuera de horario, te respondemos mañana a las 9:00."

Rate limiting por paciente — Limitar a X mensajes por minuto por número para evitar spam o loops accidentales.

5.3 Baja prioridad (nice to have)
Múltiples servicios con duración distinta — Ahora asume 60 min. Permitir que el paciente elija servicio y ajustar duración (30, 45, 60, 90 min).

Integración con pasarela de pago — Cobrar señal al agendar para reducir no-shows. Stripe o Redsys.

Analytics de prompts — Loguear tokens usados por conversación para controlar costes. Ya se guarda usage en el LLM response, solo falta persistirlo y mostrarlo.

Backup automático de BD — Cron diario que hace pg_dump y lo sube a S3/B2. Ahora es manual.

Webhook de salud — Enviar ping a servicio externo (UptimeRobot, Healthchecks.io) cada 5 min. Si falla, alerta por email/Telegram.

PARTE 6 — Próximos pasos y roadmap
Inmediato (antes de entregar al fisio)
Rellenar prompts/negocio.md con datos reales del fisioterapeuta (servicios, precios, horarios, dirección, FAQ)
Obtener tokens OAuth del fisio — Que autorice su Google Calendar y Gmail
Probar los 4 flujos end-to-end desde móvil real (FAQ, agendar, cancelar, derivar)
Cambiar contraseña del admin — No dejar admin_temporal_2024
Token permanente de WhatsApp — System User en Meta Business
Corto plazo (v1.1 — primeras semanas)
Flujo OAuth integrado en admin (feature #1)
Recordatorios automáticos 24h antes (feature #2)
Dashboard con métricas (feature #3)
Backup automático de BD (feature #14)
Medio plazo (v1.2 — primer mes)
Multi-idioma (feature #4)
Mensajes de ausencia fuera de horario (feature #9)
Rate limiting por paciente (feature #10)
Analytics de costes LLM (feature #13)
Largo plazo (v2.0 — escalar)
Multi-tenant real — Onboarding de nuevas clínicas via admin. Cada fisio con su propio número de WhatsApp, calendario, y prompts
Panel admin por tenant — Cada fisio gestiona su propio bot sin tocar código
Marketplace de prompts — Templates de negocio.md para distintos tipos de clínicas
Múltiples servicios con duraciones (feature #11)
Lista de espera (feature #6)
Feedback post-cita (feature #7)
Integración con pasarela de pago (feature #12)
App móvil para el fisio (ver citas, bloquear horarios, chatear manualmente)
Monetización potencial
Modelo	Descripción	Precio orientativo
SaaS mensual	Suscripción por clínica	29-49€/mes
Setup + mensual	Cobro de alta + mensualidad	150€ setup + 29€/mes
Por mensaje	Cobro por mensaje procesado	0.02-0.05€/mensaje
Freemium	Gratis hasta X mensajes/mes, luego pago	0€ hasta 100 msgs, luego 29€/mes
Checklist final pre-entrega
□ prompts/negocio.md con datos reales del fisio
□ Tokens de Google OAuth del fisio configurados
□ Token permanente de WhatsApp (System User)
□ 4 flujos probados desde móvil real (FAQ, agendar, cancelar, derivar)
□ Password del admin cambiado
□ SSL funcionando (https://dominio/health)
□ Webhook de Meta apuntando al dominio real
□ Backup de BD configurado (aunque sea manual)
□ Documento de 1 página para el fisio (cómo funciona, qué puede hacer, contacto soporte)