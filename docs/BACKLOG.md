# Backlog — Attendoo

Última actualización: 2026-04-05. Fuente de verdad para priorización de tareas.

## Resumen

**Deploy Hetzner fijado: 2026-04-04 al 2026-04-06** (paralelo, no bloquea desarrollo).
**Plan v1.3.0 + v1.5.0 aprobado.** Detalle completo en `docs/PLAN_V1.3.0.md`.
**Implementadas v1.2.2–v1.6.1:** #25, #16, #17, #26, #18. **Próximo:** Bloque B (bugs) o deploy Hetzner.

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
| Rename BotLLM → Attendoo | v1.2.0 |
| Ajustes landing page | v1.2.1 |
| Horarios configurables (work_blocks), calendario FullCalendar admin, superadmin mejoras | v1.6.0 |
| Gestión clases grupales migrada al calendario (modal chooser, detalle sesión) | v1.6.1 |

---

## Backlog completo (27 tareas)

### Bloque A — Prioridad 1: Infraestructura

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 25 | **Crear FEATURES.md** | ⏳ Pendiente | Inventario de TODAS las features existentes + nuevas. Regla: registrar cada feature nueva al desarrollarla. Base para futuro sistema de pricing por tiers. |

### Bloque A2 — Prioridad 2: Plan v1.3.0 + v1.5.0

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 16 | **Chat web + respuesta fisio (v1.3.0)** | ✅ Implementada | WebSocket admin, estado DERIVADA, fisio responde desde panel. |
| 17 | **WhatsApp bridge derivaciones (v1.3.0)** | ✅ Implementada | Bridge WA personal fisio con prefijos `1.`, `2.`. |
| 26 | **Alerta cancelación <24h (v1.3.0)** | ✅ Implementada | Email al fisio si cita/clase se cancela a <24h. |
| 18 | **Sesiones grupales (v1.5.0)** | ✅ Implementada | Clases recurrentes + excepciones, aforo configurable, inscripciones BD + Calendar. |

### Bloque B — Bugs y comportamiento del bot

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 2 | **Reforzar regla emojis** | ⏳ Pendiente | Prompt existe pero LLM lo incumple. Reforzar o post-procesar en código. |
| 3 | **Investigar mensaje duplicado** | ⏳ Pendiente | No hay mecanismo en código. Probable: Meta webhook retry o ngrok. Añadir logs. |
| 4 | **Bot afirmativo sobre servicios** | ⏳ Pendiente | Mejorar negocio.md con detalle de servicios + ajustar prompt para sugerir en vez de rechazar. |
| 5 | **Refresco admin 5s** | ⏳ Pendiente | Existe polling 10s. Cambiar a 5s y verificar. |
| 24 | **Seguridad sesión admin: logout + caché** | ⏳ Pendiente | Blacklist JWT Redis + `Cache-Control: no-store` + verificar token en cada carga. |
| 27 | **Skill /update-status no sincroniza bien** | ⏳ Pendiente | No actualiza los .md del proyecto correctamente. Revisar manualmente. |

### Bloque C — Corto plazo (bajo acoplamiento)

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 6 | **Referidos en contrato-bot** | ⏳ Pendiente | Cero código: +5 EUR descuento si referido. |
| 7 | **Confirmación cita por WhatsApp** | ⏳ Pendiente | Msg resumen post-ejecución (fecha, hora, servicio). Hoy solo confirma antes de crear. |
| 8 | **Mensajes de ausencia** | ⏳ Pendiente | bot_activo=false retorna silencioso. Enviar msg automático. |

### Bloque D — Medio plazo (requieren diseño)

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 9 | **Rediseño visual admin (2.1)** | ⏳ Pendiente | Estilo landing → admin. Subtarea: versión del bot por tenant en superadmin. |
| 10 | **Login unificado (2.2)** | ⏳ Pendiente | Botón en landing → redirect por rol. |
| 11 | **Buffer mensajes (debounce)** | ⏳ Pendiente | Agrupa msgs cortos (2s/5s) en Redis. |
| 12 | **OAuth integrado en admin + recordatorios** | ⏳ Pendiente | OAuth Google en admin + recordatorio WhatsApp 24h. |
| 13 | **Analytics costes LLM** | ⏳ Diferida | Necesita investigación de métricas. |
| 14 | **Multi-idioma** | ⏳ Pendiente | Detectar idioma paciente y responder en su idioma. |

### Bloque E — Largo plazo / v2.0

| # | Tarea | Estado | Notas |
|---|---|---|---|
| 15 | **Rediseño completo landing (estilo atendu.es)** | ⏳ Pendiente | Cambio grande. Referencia: atendu.es. Para después de deploy. |
| 19 | **Historial citas en BD** | ⏳ Pendiente | Consultar última cita sin depender solo de Calendar. |
| 20 | **Lista de espera** | ⏳ Pendiente | Si no hay huecos, apuntarse. Avisar si se cancela. |
| 21 | **Feedback post-cita** | ⏳ Pendiente | 2h después: "¿Qué tal? ¿Agendar la próxima?" |
| 22 | **Múltiples servicios con duraciones** | ⏳ Pendiente | 30/45/60/90 min según servicio. |
| 23 | **Pasarela de pago** | ⏳ Pendiente | Cobrar señal (Stripe/Redsys). |

---

## Detalle tarea #4: Bot afirmativo sobre servicios

- Enriquecer negocio.md con descripción detallada de servicios (junto con el tenant)
- Ajustar response_generation.md: sugerir servicios ante síntomas en vez de rechazar
- Ejemplo: "dolor de espalda" → "Ofrecemos fisioterapia general que puede ayudarte. ¿Quieres agendar?"

---

## Decisiones importantes

- **Deploy Hetzner:** 2026-04-04 al 2026-04-06
- **Plan v1.3.0 + v1.5.0:** aprobado 2026-03-29. Ver `docs/PLAN_V1.3.0.md`
- **admin.js:** excepción a regla 300 líneas, se permite >400 líneas
- **v1.4.0** reservada para bugfixes/polish post-v1.3.0
