# Backlog — Atendoo

Última actualización: 2026-05-27. Fuente de verdad para priorización de tareas.

## Resumen

**Deploy Hetzner:** completado 2026-04-06.
**Plan v1.3.0 + v1.5.0 aprobado e implementado.** Versión actual: v1.8.3.
**Último cambio:** negocio.md rediseñado para Physiofitness + plantilla base reutilizable.

---

## Features ya implementadas

| Feature | Versión |
|---|---|
| Bot WhatsApp completo (intent + response) | v1.0 |
| Google Calendar (agendar/cancelar/modificar) | v1.0 |
| Derivar a humano por email (Gmail) | v1.0 |
| Multi-tenant, Redis cache, PG verdad | v1.0 |
| Mejoras UX prompts (emojis, etc.) | v1.1.0 |
| Idempotencia, race condition, rate limiting, bot_activo | v1.1.0 |
| Landing page HTML | v1.1.0 |
| Panel admin 2 niveles (JWT, impersonación) | v1.1.0 |
| Dashboard métricas | v1.1.0 |
| Fix XSS admin.html (escapeHtml) | v1.1.0 |
| Precios con duraciones en negocio.md | v1.1.0 |
| Mutuas respuesta concisa | v1.1.0 |
| Health check GET /health | v1.1.0 |
| Ciclo vida conversaciones (INACTIVA) | v1.2.0 |
| OAuth router Google Calendar/Gmail | v1.2.0 |
| Backup/restore multi-tenant | v1.2.0 |
| Admin panel refactorizado (HTML+JS+CSS) | v1.2.0 |
| Onboarding-status endpoint | v1.2.0 |
| Rename BotLLM → Atendoo | v1.2.0 |
| Ajustes landing page | v1.2.1 |
| Feature flags con planes (SIN_PLAN/FREE_TRIAL/PAID) | v1.2.2 |
| Chat web + respuesta fisio (estado DERIVADA, WS admin) | v1.3.0 |
| WhatsApp bridge derivaciones (prefijos 1., 2.) | v1.3.0 |
| Alerta cancelación <24h por email | v1.3.0 |
| Editar wa_personal_phone + derivation_timeout desde superadmin | v1.4.0 |
| Sesiones grupales (clases recurrentes, aforo, inscripciones) | v1.5.0 |
| Horarios configurables (work_blocks), calendario FullCalendar admin | v1.6.0 |
| Gestión clases grupales migrada al calendario (modal chooser, detalle sesión) | v1.6.1 |
| Tracking RGPD persistido en PG, crash recovery, derivation timeout loop | v1.7.1 |
| Historial citas pasadas (get_past_appointments), intent consultar_historial | v1.7.1 |
| Redesign admin: editar/borrar bloqueos, slotDuration 15min, responsive móvil | v1.7.1 |
| Bugs + UX batch (13 fixes), refetch calendar vía WS | v1.8.1 |
| Bug batch QA (B1, A2-A4, D3, E1) | v1.8.2 |
| Calendar UX polish + nginx URL fix | v1.8.3 |
| negocio.md rediseñado para Physiofitness + negocio_base.md plantilla | v1.8.3 |

---

## Backlog completo

### Bloque A — Infraestructura

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 25 | **FEATURES.md** | ✅ Implementada | Creado en v1.2.2. Inventario de features con planes. |
| 28 | **SSH usuario `deploy` en VPS** | ⏳ Pendiente | Crear usuario deploy, añadir clave SSH, sudoers mínimos. Actualizar docs. |
| 29 | **Pipeline CI/CD GitHub Actions** | ⏳ Pendiente | Push a `deployment` → despliegue automático. Secrets: SSH key + IP. Workflow: git pull + docker compose restart app + alembic upgrade head. |

---

### Bloque B — Comportamiento del bot y calidad IA

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 2 | **Reforzar regla emojis** | ⏳ Pendiente | Prompt existe pero LLM lo incumple. Reforzar con post-proceso en código si hace falta. |
| 3 | **Investigar mensaje duplicado** | ⏳ Pendiente | Sin mecanismo claro en código. Probable: Meta webhook retry. Añadir logs. |
| 4 | **Bot afirmativo sobre servicios** | ✅ Cubierta en v1.8.3 | negocio.md rediseñado con detalle de servicios, mini-triaje, líneas rojas. |
| 5 | **Refresco admin 5s** | ⏳ Pendiente | Cambiar polling de 10s a 5s y verificar. |
| 24 | **Seguridad sesión admin: logout + caché** | ⏳ Pendiente | Blacklist JWT Redis + `Cache-Control: no-store` + verificar token en cada carga. |
| 27 | **Skill /update-status no sincroniza bien** | ⏳ Pendiente | Revisar manualmente cada vez hasta corregir. |
| 30 | **Flujo inteligente de citas (Top 3 huecos)** | 🔲 Pendiente diseño | Problema: bot devuelve muro de texto con todos los huecos. Solución: mostrar los 3 huecos libres más cercanos a la fecha/hora solicitada por el cliente. Requiere cambio en `calendar_service.py` (ordenar y filtrar slots) + prompt. Ver §B1. |
| 31 | **Pipeline QA de prompts (LLM-as-judge)** | 🔲 Pendiente diseño | Sistema automatizado pytest + LLM-as-judge para medir calidad de respuestas. Técnicas: XML tags, multishot, control longitud. Requiere diseño previo. Ver §B2. |

---

### Bloque C — Corto plazo (bajo acoplamiento)

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 6 | **Referidos en contrato-bot** | ⏳ Pendiente | Sin código: +5 EUR descuento si referido. |
| 7 | **Confirmación cita por WhatsApp** | ⏳ Pendiente | Mensaje resumen post-ejecución (fecha, hora, servicio). Hoy solo confirma antes de crear. |
| 8 | **Mensajes de ausencia** | ⏳ Pendiente | bot_activo=false retorna silencioso. Enviar msg automático. |
| 32 | **Notificación WhatsApp al fisio (Meta Template)** | ⏳ Pendiente | Cuando hay nueva derivación, enviar plantilla aprobada por Meta al wa_personal_phone del fisio. Hoy solo Email + WS. Requiere plantilla registrada en Meta Business. |
| 33 | **Restringir wa_personal_phone a superadmin** | ⏳ Pendiente | Sacar el campo del acceso del admin de clínica (`admin.py`). Solo editable desde `superadmin.py`. Bajo riesgo, cambio quirúrgico. |

---

### Bloque D — Medio plazo (requieren diseño)

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 9 | **Rediseño visual admin (v2.1)** | ⏳ Pendiente | Aplicar estilo landing al admin. Subtarea: versión bot por tenant en superadmin. |
| 10 | **Login unificado (v2.2)** | ⏳ Pendiente | Botón en landing → redirect por rol. |
| 11 | **Buffer mensajes (debounce)** | ⏳ Pendiente | Agrupa msgs cortos (2-5s) en Redis. |
| 12 | **OAuth integrado en admin + recordatorios** | ⏳ Pendiente | OAuth Google dentro del panel + recordatorio WhatsApp 24h antes. |
| 13 | **Analytics costes LLM** | ⏳ Diferida | Necesita investigación de métricas. |
| 14 | **Multi-idioma** | ⏳ Pendiente | Detectar idioma paciente y responder en su idioma. |
| 34 | **Tests e2e Playwright** | ⏳ Pendiente | Crear `tests/e2e/test_admin_chat.py` y `test_admin_classes.py`. Añadir dependencias en `requirements-test.txt`. |
| 35 | **Ampliar admin_features.py** | ⏳ Pendiente | Actualmente solo tiene 1 endpoint GET /features. Añadir PUT para activar/desactivar features por tenant desde el panel. |

---

### Bloque E — Largo plazo / v2.0

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 15 | **Rediseño completo landing** | ⏳ Pendiente | Cambio grande. Referencia: atendu.es. Para después del primer cliente. |
| 19 | **Historial citas en BD** | ⏳ Pendiente | Consultar última cita sin depender solo de Calendar. |
| 20 | **Lista de espera** | ⏳ Pendiente | Si no hay huecos, apuntarse. Avisar si se cancela. |
| 21 | **Feedback post-cita** | ⏳ Pendiente | 2h después: "¿Qué tal? ¿Agendar la próxima?" |
| 22 | **Múltiples servicios con duraciones** | ⏳ Pendiente | 30/45/60/90 min según servicio. |
| 23 | **Pasarela de pago** | ⏳ Pendiente | Cobrar señal (Stripe/Redsys). |

---

## Detalle tareas pendientes del Plan 10_04_2026

### §B1 — Flujo inteligente de citas (#30)

**Problema actual:** `calendar_service.get_free_slots()` devuelve todos los huecos de la semana. El LLM los pega todos en el mensaje → muro de texto.

**Solución acordada:** Devolver los **3 huecos libres más cercanos** a la fecha/hora que pide el cliente.
- Si el cliente dice "esta tarde" → buscar desde esa tarde en adelante, devolver los 3 primeros.
- Si no da preferencia → desde ahora mismo, los 3 primeros.
- Fallback: si hay <3 huecos en los próximos 7 días → mostrar todos los disponibles + ofrecer semana siguiente.
- Cambios necesarios: `calendar_service.py` (filtrar+ordenar slots por proximidad) + `agent.py` (pasar parámetro de preferencia horaria) + `response_generation.md` (instrucción: mostrar solo los slots recibidos, no inventar).

### §B2 — Pipeline QA prompts (#31)

**Objetivo:** Batería de casos de test que ejecutan el pipeline completo (detect_intent → generate_response) contra respuestas esperadas, usando un LLM juez para validar.
- Framework: pytest + llamada directa a las funciones de `llm_service.py`.
- Casos mínimos: 10-15 escenarios (FAQ, agendar, cancelar, consultar historial, casos límite).
- Métricas: intent correcto (exacto), respuesta coherente (LLM-as-judge 1-5), sin alucinaciones, longitud aceptable.
- Requiere diseño del harness antes de implementar.

---

## Decisiones importantes

- **Deploy Hetzner:** completado 2026-04-06
- **Plan v1.3.0 + v1.5.0:** aprobado 2026-03-29, implementado en v1.3.0–v1.5.0
- **admin.js:** excepción a regla 300 líneas, se permite >400 líneas
- **negocio.md:** §3 horario eliminado del estático, se inyecta dinámico desde `tenant.work_blocks`
- **Top 3 huecos:** mostrar los más cercanos a la preferencia del cliente, no un dump de la semana
