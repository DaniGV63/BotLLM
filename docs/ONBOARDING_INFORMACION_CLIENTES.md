# Cuestionario de Onboarding — Atendoo

> **Propósito:** Extraer TODA la información que el bot de WhatsApp necesita para funcionar correctamente en tu negocio. Las respuestas alimentan directamente el perfil del bot.
>
> **Instrucciones para Typeform:** Cada pregunta lleva un marcador `[obligatorio]` u `[opcional]`. Respetar al copiar. Las cajas `> [PRE-RELLENO]` contienen datos que ya tenemos del cliente — solo debe validar o corregir.
>
> **Tiempo estimado:** 15-25 minutos.

---

## §1. Identidad y contacto del negocio

### 1.1 Nombre comercial del negocio [obligatorio]
*(ej: Clínica Physiofitness, Peluquería María, Centro Deportivo FitZone)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Clínica Physiofitness

---

### 1.2 Razón social / NIF [opcional]
*(ej: Physiofitness S.L., NIF: B12345678. Si eres autónomo, déjalo en blanco)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — completar si aplica)*

---

### 1.3 Dirección física exacta [obligatorio]
*(ej: Calle Venezuela, 8, 28220 Majadahonda, Madrid)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Calle Venezuela, 8, 28220 Majadahonda, Madrid

---

### 1.4 URL de Google Maps [opcional]
*(Pega aquí el enlace directo a tu ubicación en Google Maps)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — pegar enlace de Google Maps)*

---

### 1.5 Teléfono principal del negocio [obligatorio]
*(ej: 618 974 833)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 618 974 833

---

### 1.6 ¿Tienes un número de teléfono fijo en el negocio? [opcional]
*(ej: 91 123 45 67. Si no tienes fijo, escribe "No")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿tienes fijo?)*

---

### 1.7 Email principal del negocio [obligatorio]
*(ej: david.fisiofit@gmail.com — a este email llegarán las notificaciones del bot)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> david.fisiofit@gmail.com

---

### 1.8 Email de notificaciones del bot [opcional]
*(Si quieres que las alertas del bot lleguen a un email diferente al principal. Si es el mismo, déjalo en blanco)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Mismo que el principal — dejar en blanco si no cambia)*

---

### 1.9 Web del negocio [opcional]
*(ej: https://www.clinicaphysiofitness.com/)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> https://www.clinicaphysiofitness.com/

---

### 1.10 Redes sociales [opcional]
*Indica los perfiles activos (ej: Instagram: @physiofitness_madrid, Facebook: Clínica Physiofitness)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — completar las redes activas)*

---

## §2. Decisión de infraestructura WhatsApp

> ⚠️ **BLOQUE CRÍTICO — Lee con atención antes de responder**
>
> Para que el bot de Atendoo funcione por WhatsApp, necesita un **número de teléfono dedicado**, por requerimientos obligatorios de WhatsApp Business.
>
> **¿Qué significa esto?** Cuando un número de teléfono se registra en WhatsApp Business, **deja de funcionar en la app normal de WhatsApp** (tanto la personal como la de WhatsApp Business App). Es decir:
> - Ya no puedes abrir WhatsApp en el móvil con ese número.
> - Pierdes acceso al historial de chats que tenías.
> - Sales de todos los grupos de WhatsApp.
> - Ya no puedes enviar ni recibir mensajes desde la app.
> - **Las llamadas telefónicas normales (voz) SÍ siguen funcionando** — solo se ve afectado WhatsApp.
> - **Los datos de WhatsApp (chats, grupos, historial) se pierden de forma permanente.** Incluso si en el futuro se des-registra el número de la API y se vuelve a usar WhatsApp normal, se empezaría de cero — no se recupera nada de lo anterior.
>
> Por eso, elegir qué número usa el bot es una decisión importante. A continuación te explicamos **todas las opciones disponibles** con sus ventajas, inconvenientes y costes para que elijas la que mejor te encaje.

### 2.1 ¿El número principal del negocio (618 974 833) se usa actualmente para WhatsApp? [obligatorio]
*(Responde Sí o No)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Suponemos que sí — confirmar)*

---

### 2.2 ¿Usas ese WhatsApp para comunicarte con pacientes, proveedores o compañeros? [obligatorio]
*(Responde Sí o No. Si Sí, indica brevemente para qué: ej. "para confirmar citas", "para grupos con pacientes", "para hablar con proveedores", etc.)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — necesitamos saberlo para recomendarte la mejor opción)*

---

### 2.3 ¿Tienes algún número de teléfono (móvil o fijo) que NO estés usando actualmente con WhatsApp? [obligatorio]

*Piensa si tienes alguno de estos:*
- *Un número fijo de la clínica*
- *Una SIM antigua en un cajón que ya no usas*
- *Un segundo número móvil (ej. línea de empresa separada)*
- *Un número de un móvil viejo*

*Si tienes algún número así, es perfecto: lo podemos usar para el bot y te ahorras el coste de contratar uno nuevo. Escribe el número o "No tengo ninguno disponible".*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — comprobar)*

---

### 2.4 Elige la opción que prefieras para el número del bot [obligatorio]

Lee las **4 opciones** con calma. Cada una tiene sus ventajas e inconvenientes. Marca la que encaje mejor contigo.

---

#### Opción A — Migrar tu número actual (618 974 833) al bot

**Cómo funciona:** Tu número actual se registra en la API de WhatsApp Business. El bot responde a los pacientes desde ese mismo número. Tú sigues recibiendo llamadas normales en el 618 974 833 sin ningún problema.

**✅ Ventajas:**
- Los pacientes ya conocen tu número — no hay que comunicar ningún cambio.
- Coste adicional: **0 €**.
- Máxima continuidad: el bot "hereda" la identidad de contacto de la clínica.

**❌ Inconvenientes:**
- **Pierdes el acceso a WhatsApp en ese número.** Ya no podrás abrir la app de WhatsApp con el 618 974 833. Nada de chats, nada de grupos, nada de mensajes — ni los antiguos ni nuevos.
- Si usas ese WhatsApp para hablar con pacientes, proveedores, amigos o familia, **todo eso se pierde**.
- El historial de conversaciones **no se transfiere** al bot — se pierde al eliminar la cuenta de WhatsApp.
- Si en algún momento quisieras volver a usar WhatsApp normal en ese número, podrías des-registrarlo de la API (el bot dejaría de funcionar), pero tu WhatsApp empezaría de cero — **los chats, grupos e historial anteriores NO se recuperan**.

**💾 Si eliges esta opción, haz una copia de seguridad ANTES:**
- En tu móvil, abre **WhatsApp → Ajustes → Chats → Copia de seguridad**. Esto guarda tus conversaciones en Google Drive (Android) o iCloud (iPhone).
- También puedes exportar chats individuales importantes: abre el chat → **⋮ (menú) → Más → Exportar chat**. Se genera un archivo .txt que puedes guardar en tu ordenador o email.
- Haz esto **antes** de que configuremos el bot, porque una vez registrado el número en la API, ya no tendrás acceso a la app para hacer la copia.

**⚠️ Recomendación:** Solo elige esta opción si **no usas WhatsApp** en el 618 974 833 para nada personal, o si no te importa perder ese acceso.

---

#### Opción B — Contratar un número nuevo para el bot (RECOMENDADA)

**Cómo funciona:** Se compra un número de teléfono nuevo (virtual o una SIM prepago) que será exclusivo del bot. Tú no tocas tu WhatsApp actual — sigue todo igual.

**✅ Ventajas:**
- **No pierdes absolutamente nada.** Tu WhatsApp del 618 974 833 sigue funcionando tal cual hoy.
- Separación limpia: el bot tiene su número, tú tienes el tuyo. Sin confusiones.
- Si el bot necesita derivar a una persona, te avisa a ti al 618 974 833 y tú respondes desde tu WhatsApp normal.
- Fácil de comunicar a los pacientes: se pone el número del bot en la web, en Instagram, en Google Business y listo.

**❌ Inconvenientes:**
- Hay un coste mensual por mantener el número nuevo: **~5-15 €/mes** (SIM prepago) o **~5-15 €/mes** (número virtual VoIP).
- Los pacientes ven un número nuevo que no conocen. Hay que comunicarlo (aunque esto se hace una vez y listo).

**💡 Sobre el coste:** Para un negocio que factura a 55 €/sesión, 5-15 €/mes es menos que el precio de una sesión al mes. Es el coste más bajo de toda esta decisión.

**📱 ¿Cómo se contrata?** Nosotros podemos encargarnos por ti (contratamos una SIM prepago o un número virtual, lo configuramos y te damos todo listo). Si prefieres hacerlo tú o tienes preferencia de operador, también puedes.

**⚠️ Recomendación:** Esta es la opción que recomendamos para la mayoría de negocios, especialmente si usas el WhatsApp actual de forma activa.

---

#### Opción C — Usar un número que ya tengas y que no esté en WhatsApp

**Cómo funciona:** Si tienes algún número de teléfono (móvil o fijo) que NO esté actualmente registrado en WhatsApp, lo podemos usar para el bot. No necesitas comprar nada nuevo.

**✅ Ventajas:**
- **Coste adicional: 0 €** — usamos un número que ya tienes.
- Tu WhatsApp del 618 974 833 sigue intacto.
- Separación limpia entre bot y uso personal.

**❌ Inconvenientes:**
- El número debe poder recibir un SMS o una llamada de verificación de Meta (una sola vez, durante la configuración inicial).
- Si es un número fijo, los pacientes verán un fijo en WhatsApp — puede parecer inusual (aunque cada vez es más común en negocios).
- Si es una SIM antigua, asegúrate de que esté activa y no caduque. Necesita estar operativa al menos para la verificación.

**📋 Ejemplos de números que podrían servir:**
- Un fijo de la clínica (ej. 91 XXX XX XX) → se verifica por llamada de voz.
- Una SIM de prepago antigua que tengas en un cajón → se verifica por SMS.
- Un móvil viejo con su propia línea → se verifica por SMS.
- Un número de empresa secundario que no uses para WhatsApp.

**⚠️ Requisito:** El número NO debe estar registrado actualmente en ninguna app de WhatsApp (ni personal ni Business). Si lo está, hay que eliminar esa cuenta primero.

---

#### Opción D — Usar el número fijo de la clínica

**Cómo funciona:** Si la clínica tiene un número de teléfono fijo (línea fija, tipo 91X XXX XXX), lo podemos registrar directamente en la API de WhatsApp Business. La verificación se hace por llamada de voz (recibes una llamada en el fijo con un código de 6 dígitos).

**✅ Ventajas:**
- **Coste adicional: 0 €** — ya estás pagando la línea fija.
- Tu WhatsApp del 618 974 833 sigue intacto.
- El fijo puede ser reconocible como "el teléfono de la clínica" por los pacientes.
- Profesional: muchos negocios con bot usan el fijo para WhatsApp y el móvil para llamadas personales.

**❌ Inconvenientes:**
- Los pacientes ven un número fijo en WhatsApp. Algunos podrían extrañarse (aunque cada vez es más común).
- La línea fija **NO debe tener activada ninguna app de WhatsApp** previamente. Si la tienes porque alguna vez la registraste en WhatsApp Business, habría que eliminar esa cuenta primero.
- Si el fijo tiene centralita, contestador automático o filtros de llamadas internacionales, la llamada de verificación de Meta podría no entrar. Habría que desactivar esos filtros temporalmente durante la configuración.
- El fijo NO podrá usarse para WhatsApp personal después (quedaría reservado para el bot).

**⚠️ Requisito:** Necesitas poder contestar el teléfono fijo cuando Meta llame para verificar el número (es una sola llamada, durante la configuración).

---

### Resumen de opciones

| | Opción A | Opción B | Opción C | Opción D |
|---|---|---|---|---|
| **Número del bot** | Tu 618 974 833 | Número nuevo | Un número tuyo sin WA | Tu fijo |
| **Conservas tu WhatsApp** | ❌ No | ✅ Sí | ✅ Sí | ✅ Sí |
| **Pacientes reconocen el nº** | ✅ Sí | ❌ No (es nuevo) | 🟡 Depende | 🟡 Si conocen el fijo |
| **Coste extra mensual** | 0 € | 5-15 € | 0 € | 0 € |
| **Riesgo** | 🔴 Alto | 🟢 Bajo | 🟢 Bajo | 🟡 Medio |

**¿Cuál eliges? (A / B / C / D)**

> [PRE-RELLENO]
> Recomendamos **B** si usas activamente tu WhatsApp actual, o **C/D** si tienes un número disponible (fijo o móvil) que no estés usando con WhatsApp — así te ahorras el coste mensual.

---

### 2.5 Si elegiste B: ¿prefieres que contratemos nosotros el número o lo gestionas tú? [opcional]
*(Podemos encargarnos de todo: contratamos un número virtual o SIM prepago, lo configuramos y lo dejamos listo. Si prefieres hacerlo tú o tienes preferencia de operador, indícalo)*

---

### 2.6 Si elegiste C: ¿cuál es el número que quieres usar? [obligatorio si elegiste C]
*(Escribe el número e indica si es móvil o fijo)*

---

### 2.7 Si elegiste D: ¿cuál es el número fijo de la clínica? [obligatorio si elegiste D]
*(Escribe el número fijo. Confirma que puedes contestar llamadas en ese fijo y que NO tiene WhatsApp asociado)*

---

### 2.8 ¿Tu teléfono móvil personal tiene dual SIM o eSIM? [opcional]
*(Esto nos ayuda a saber si en el futuro podrías llevar un segundo número en tu mismo teléfono. Responde Sí / No / No sé)*

---

## §3. Horario de operaciones

### 3.1 Horario de atención por día [obligatorio]
*Indica el horario para cada día. Si tienes mañana y tarde separados, indícalo. Si un día estás cerrado, escribe "Cerrado".*

*(ej: Lunes: 07:00-14:00 y 16:00-21:00 | Sábado: 10:00-14:00 | Domingo: Cerrado)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
>
> | Día | Horario |
> |-----|---------|
> | Lunes | 07:00 - 21:00 |
> | Martes | 07:00 - 21:00 |
> | Miércoles | 07:00 - 21:00 |
> | Jueves | 07:00 - 21:00 |
> | Viernes | 07:00 - 21:00 |
> | Sábado | 10:00 - 14:00 |
> | Domingo | Cerrado |
>
> **Pregunta adicional:** ¿El horario L-V es continuo (7 a 21 sin pausa) o hay un descanso a mediodía? Esto es importante para que el bot ofrezca huecos correctamente.

---

### 3.2 Festivos y vacaciones [opcional]
*¿Cierras en algún periodo del año? ¿Respetas los festivos locales de Majadahonda?*

*(ej: "Cerramos del 1 al 15 de agosto", "Los festivos oficiales de la Comunidad de Madrid no abrimos")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — completar)*

---

### 3.3 ¿El bot puede ofrecer citas en cualquier franja del horario, o hay restricciones? [obligatorio]
*(ej: "Solo ofrezco fisioterapia por las mañanas", "El entrenamiento solo por las tardes a partir de las 16:00", "Todo igual durante todo el horario")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿hay restricciones horarias por tipo de servicio?)*

---

### 3.4 ¿Qué debe hacer el bot cuando alguien quiere cita fuera de horario? [obligatorio]
*Elige una o varias:*

- [ ] Rechazar la solicitud y ofrecer el próximo hueco disponible
- [ ] Añadir a una lista de espera
- [ ] Derivar al profesional para que decida
- [ ] El bot funciona 24/7 pero solo ofrece huecos dentro del horario

> [PRE-RELLENO]
> Recomendamos: **El bot funciona 24/7 pero solo ofrece huecos dentro del horario.**

---

## §4. Catálogo de servicios

> ⚠️ **BLOQUE CLAVE** — Esta sección es fundamental para que el bot ofrezca tus servicios correctamente. Rellena CADA servicio por separado.

### Servicio 1: Fisioterapia Avanzada

#### 4.1.1 Nombre comercial del servicio [obligatorio]
*(Tal como lo dices a los pacientes)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Fisioterapia

---

#### 4.1.2 Categoría [obligatorio]
*(Elige: fisioterapia / entrenamiento / estética / complementario / otro)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Fisioterapia

---

#### 4.1.3 Duración de la sesión en minutos [obligatorio]
*(ej: 50)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 50 minutos

---

#### 4.1.4 Precio sesión suelta [obligatorio]
*(ej: 55 €)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 55 €

---

#### 4.1.5 ¿Ofreces bonos para este servicio? [opcional]
*Indica los packs disponibles con precio total.*

*(ej: Bono 5 sesiones: 265 € | Bono 10 sesiones: 500 €)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> - Bono 5 sesiones: 265 € (53 €/sesión)
> - Bono 10 sesiones: 500 € (50 €/sesión)

---

#### 4.1.6 ¿Ofreces suscripción mensual para este servicio? [opcional]
*(ej: "1 sesión semanal: 200 €/mes". Si no aplica, escribe "No")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> No

---

#### 4.1.7 ¿Qué profesional realiza este servicio? [opcional]
*(ej: David, Ana, "cualquiera del equipo")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿quién lo realiza?)*

---

#### 4.1.8 ¿Requiere valoración previa para la primera cita? [obligatorio]
*(ej: "Sí, primera cita siempre es valoración" o "No, se puede reservar directamente")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿se necesita valoración previa?)*

---

#### 4.1.9 ¿Necesita alguna máquina o recurso compartido? [opcional]
*(ej: "Máquina isocinética", "Camilla INDIBA". Si no, escribe "No")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿algún recurso?)*

---

#### 4.1.10 ¿Es sesión individual o grupal? [obligatorio]
*(Si es grupal, indica capacidad mínima y máxima. ej: "Grupal, 2-4 personas")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Individual

---

---

### Servicio 2: Entrenamiento Personal

#### 4.2.1 Nombre comercial [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Entrenamiento Personal

---

#### 4.2.2 Categoría [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Entrenamiento

---

#### 4.2.3 Duración [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 60 minutos (1 hora)

---

#### 4.2.4 Precio sesión suelta [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 50 €

---

#### 4.2.5 Bonos [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> - Bono 5 sesiones: 240 € (48 €/sesión)
> - Bono 10 sesiones: 450 € (45 €/sesión)

---

#### 4.2.6 Suscripción mensual [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> No (la suscripción es para grupos reducidos, no para individual)

---

#### 4.2.7 Profesional asignado [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿quién lo realiza?)*

---

#### 4.2.8 ¿Requiere valoración previa? [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

#### 4.2.9 ¿Recurso/máquina compartida? [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> No

---

#### 4.2.10 ¿Individual o grupal? [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Individual

---

---

### Servicio 3: Entrenamiento en Grupos Reducidos

#### 4.3.1 Nombre comercial [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Entrenamiento en Grupos Reducidos

---

#### 4.3.2 Categoría [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Entrenamiento

---

#### 4.3.3 Duración [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 60 minutos (1 hora)

---

#### 4.3.4 Precio sesión suelta [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 55 € / persona

---

#### 4.3.5 Bonos [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> No (este servicio funciona con suscripciones)

---

#### 4.3.6 Suscripciones mensuales [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> - 1 clase semanal: 140 €/mes
> - 2 clases semanales: 260 €/mes
> - 3 clases semanales: 360 €/mes

---

#### 4.3.7 Profesional asignado [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿quién lo realiza?)*

---

#### 4.3.8 ¿Requiere valoración previa? [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

#### 4.3.9 ¿Recurso/máquina compartida? [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> No

---

#### 4.3.10 ¿Individual o grupal? Capacidad [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Grupal — 2 a 4 personas

---

---

### Servicio 4: Fisio-estética — 1 Zona (30 min)

#### 4.4.1 Nombre comercial [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Fisio-estética 1 zona (30 min)

---

#### 4.4.2 Categoría [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Estética

---

#### 4.4.3 Duración [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 30 minutos

---

#### 4.4.4 Precio sesión suelta [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 55 €

---

#### 4.4.5 Bonos [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> - Bono 5 sesiones: 250 €
> - Bono 10 sesiones: 500 €

---

#### 4.4.6 Suscripción [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> No

---

#### 4.4.7 Profesional asignado [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

#### 4.4.8 ¿Requiere valoración previa? [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

#### 4.4.9 ¿Recurso/máquina compartida? [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Posiblemente INDIBA u otro equipo — confirmar)*

---

#### 4.4.10 ¿Individual o grupal? [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Individual

---

#### 4.4.11 Zonas disponibles [obligatorio]
*(Indica qué zonas puede elegir el paciente)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Facial, Piernas, Abdomen, Glúteos

---

---

### Servicio 5: Fisio-estética — 1 Zona (45 min)

#### 4.5.1 Nombre comercial [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Fisio-estética 1 zona (45 min)

---

#### 4.5.2 Categoría [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Estética

---

#### 4.5.3 Duración [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 45 minutos

---

#### 4.5.4 Precio sesión suelta [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 70 €

---

#### 4.5.5 Bonos [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> - Bono 5 sesiones: 340 €
> - Bono 10 sesiones: 650 €

---

#### 4.5.6 - 4.5.10 (mismos campos que el servicio anterior)

> Misma estructura. Zonas: Facial, Piernas, Abdomen, Glúteos

---

---

### Servicio 6: Fisio-estética — 2 Zonas (60 min)

#### 4.6.1 Nombre comercial [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Fisio-estética combinada 2 zonas

---

#### 4.6.2 Categoría [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Estética

---

#### 4.6.3 Duración [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 60 minutos

---

#### 4.6.4 Precio sesión suelta [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 90 €

---

#### 4.6.5 Bonos [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> - Bono 5 sesiones: 425 €
> - Bono 10 sesiones: 800 €

---

#### 4.6.6 - 4.6.11 (mismos campos: suscripción, profesional, valoración, recurso, individual, zonas)

---

---

### Servicio 7: Fisio-estética — 3 Zonas (60 min)

#### 4.7.1 Nombre comercial [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Fisio-estética combinada 3 zonas

---

#### 4.7.2 Categoría [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Estética

---

#### 4.7.3 Duración [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 60 minutos

---

#### 4.7.4 Precio sesión suelta [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 99 €

---

#### 4.7.5 Bonos [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> - Bono 5 sesiones: 475 €
> - Bono 10 sesiones: 900 €

---

#### 4.7.6 - 4.7.11 (mismos campos)

---

---

### Servicio 8: Presoterapia

#### 4.8.1 Nombre comercial [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Presoterapia

---

#### 4.8.2 Categoría [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Complementario

---

#### 4.8.3 Duración [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 30 minutos

---

#### 4.8.4 Precio sesión suelta [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 20 €

---

#### 4.8.5 Bonos [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿ofreces bonos de presoterapia?)*

---

#### 4.8.6 Suscripción [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> No

---

#### 4.8.7 Profesional asignado [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

#### 4.8.8 ¿Requiere valoración previa? [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

#### 4.8.9 ¿Recurso/máquina compartida? [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Sí — máquina de presoterapia

---

#### 4.8.10 ¿Individual o grupal? [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Individual

---

---

### Servicio 9: Readaptación Neuromuscular

#### 4.9.1 Nombre comercial [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Readaptación Neuromuscular

---

#### 4.9.2 Categoría [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Complementario

---

#### 4.9.3 Duración [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿cuántos minutos dura la sesión?)*

---

#### 4.9.4 Precio sesión suelta [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 60 €

---

#### 4.9.5 Bonos [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿ofreces bonos?)*

---

#### 4.9.6 Suscripción [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> No

---

#### 4.9.7 Profesional asignado [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

#### 4.9.8 ¿Requiere valoración previa? [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿requiere valoración?)*

---

#### 4.9.9 ¿Recurso/máquina compartida? [opcional]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Sí — máquina isocinética

---

#### 4.9.10 ¿Individual o grupal? [obligatorio]

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Individual

---

---

### ¿Tienes más servicios? [opcional]
*Si tienes servicios que no hemos listado, descríbelos con el mismo formato: nombre, categoría, duración, precio, bonos, profesional, y si es individual o grupal.*

---

## §5. Restricciones médicas y límites del bot

> ⚠️ **BLOQUE CRÍTICO** — Esta sección define qué puede y qué NO puede decir tu bot. Tómate tu tiempo.

### 5.1 ¿Qué patologías o problemas tratas habitualmente? [obligatorio]
*Lista las dolencias/patologías que tus pacientes traen con frecuencia y que tú tratas con confianza.*

*(ej: cervicalgias, lumbalgias, ciáticas, contracturas, tendinitis, post-operatorio de rodilla/hombro, dolores musculares por deporte, fascitis plantar...)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — necesitamos que David liste sus patologías habituales)*

---

### 5.2 ¿Qué patologías NO tratas o requieren derivación inmediata? [obligatorio]
*Lista las situaciones en las que el bot DEBE derivar al paciente a urgencias o a otro profesional.*

*(ej: sospecha de fractura, traumatismos de menos de 24h, dolor nocturno irradiado que despierta del sueño, fiebre con dolor articular, pérdida de fuerza súbita, déficit neurológico, dolor torácico...)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — FUNDAMENTAL que David defina sus líneas rojas)*

---

### 5.3 Contraindicaciones para tratamientos estéticos [obligatorio — si ofreces estética]
*¿En qué casos NO se debe aplicar fisio-estética (INDIBA, presoterapia, etc.)?*

*(ej: embarazo, portadores de marcapasos, prótesis metálicas en la zona, problemas circulatorios graves, cáncer activo, heridas abiertas...)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — David debe listar las contraindicaciones de INDIBA/presoterapia)*

---

### 5.4 ¿El bot atiende menores de edad? [obligatorio]
*(Responde: "Sí, cualquier edad" / "Solo mayores de 16" / "Solo mayores de 18" / "Menores con autorización de los padres" / Otra)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

### 5.5 ¿Tratas pacientes de edad avanzada? ¿Hay alguna limitación? [opcional]
*(ej: "Sí, sin limitación" / "Sí, pero sin entrenamiento de alta intensidad")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

### 5.6 ¿El bot puede dar consejos clínicos o solo gestionar la agenda? [obligatorio]
*Esta es una decisión IMPORTANTE. Elige una:*

- **(A) Solo agenda:** El bot NO opina sobre dolencias. Ante cualquier pregunta clínica → "Esto lo valorará el profesional en tu cita" y ofrece reservar.
- **(B) Mini-triaje empático (RECOMENDADA):** El bot puede preguntar 1-2 preguntas sobre los síntomas (¿desde cuándo? ¿con qué empeora?) y dar una respuesta empática tipo "Eso suele responder bien a fisioterapia, pero lo confirma [tu nombre] en la valoración. ¿Quieres que te busque un hueco?". **Nunca da diagnóstico ni nombre de patología.**
- **(C) Información detallada:** El bot da explicaciones más amplias sobre qué tipo de tratamiento podría ayudar. ⚠️ Mayor riesgo legal.

**¿Cuál eliges? (A / B / C)**

> [PRE-RELLENO]
> Recomendamos **B** — minimiza derivaciones innecesarias y mejora la conversión a cita, sin riesgo legal.

---

### 5.7 ¿El bot puede mencionar precios concretos? [obligatorio]
*(Responde: "Sí, puede dar precios cuando se los pregunten" / "No, que diga que contacte con la clínica para precios" / "Solo puede dar el precio de la sesión suelta, no bonos ni suscripciones")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿puede el bot decir los precios?)*

---

## §6. Tono y personalidad del bot

### 6.1 ¿El bot tutea o trata de usted? [obligatorio]
*(ej: "Tutea" / "De usted" / "Empieza de usted y si el paciente tutea, cambia")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — recomendamos "Tutea" para un centro cercano como Physiofitness)*

---

### 6.2 Nivel de cercanía [obligatorio]
*Elige uno:*

- **Clínico-formal:** "Buenos días, ¿en qué puedo ayudarle?" Sin emojis, tono serio.
- **Cercano-empático (RECOMENDADA):** "¡Hola! 😊 Cuéntame qué necesitas y te echo un cable." Emojis con moderación, tono cálido.
- **Desenfadado:** "¡Hey! 🤙 ¿Qué tal? Dime qué te pasa y miramos." Muchos emojis, tono muy informal.

**¿Cuál eliges?**

> [PRE-RELLENO]
> Recomendamos **Cercano-empático** para fisioterapia — genera confianza sin perder profesionalidad.

---

### 6.3 ¿El bot puede usar emojis? [obligatorio]
*(Responde: "Sí, con moderación" / "Sí, muchos" / "No, sin emojis")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Recomendamos sí, con moderación — ej. ✅ para confirmaciones, 😊 para cercanía, 📅 para citas)*

---

### 6.4 Idioma principal del bot [obligatorio]
*(ej: "Solo español" / "Español e inglés" / "Español, si el paciente escribe en inglés responder en inglés")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> Solo español

---

### 6.5 ¿Hay alguna palabra o frase que el bot NO debe usar nunca? [opcional]
*(ej: "No usar 'dolor crónico'", "No decir 'problema'", "No mencionar competidores")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

### 6.6 ¿Quieres que el bot firme sus mensajes? [opcional]
*(ej: "— Equipo Physiofitness" / "— Tu asistente de Physiofitness" / Sin firma)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Recomendamos sin firma — los mensajes de WhatsApp ya salen del número de la clínica)*

---

## §7. Política de citas

### 7.1 ¿Se puede reservar cita directamente la primera vez o se requiere una valoración previa? [obligatorio]
*(ej: "La primera vez siempre es valoración + tratamiento" / "Se puede reservar cualquier servicio desde la primera vez" / "Solo fisioterapia requiere valoración inicial")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — importante para el flujo del bot)*

---

### 7.2 ¿Con cuánta antelación mínima se puede cancelar sin coste? [obligatorio]
*(ej: "24 horas" / "48 horas" / "Sin política de cancelación")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 24 horas

---

### 7.3 ¿Qué pasa si un paciente no se presenta (no-show)? [obligatorio]
*(ej: "Se cobra el 50% de la sesión" / "Se avisa pero no se cobra" / "Se pierde una sesión del bono" / "No hacemos nada")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — en negocio.md aparecía "50% del importe" pero eran datos ficticios. ¿Cuál es la política real?)*

---

### 7.4 ¿Tienes un enlace de reservas online externo? [opcional]
*(ej: "Sí, usamos Booksy: https://booksy.com/..." / "Sí, tenemos formulario en la web" / "No, solo por WhatsApp y teléfono")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿usas alguna plataforma externa de reservas?)*

---

### 7.5 ¿El bot puede ofrecer el enlace de reservas como alternativa? [opcional]
*(Si tienes enlace externo: "Sí, que lo ofrezca si el paciente prefiere reservar online" / "No, prefiero que solo use el bot")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

## §8. Datos del profesional para derivaciones (handoff)

### 8.1 Nombre completo del profesional principal [obligatorio]
*(Este nombre es el que el bot usará cuando diga "lo confirma [nombre] en tu cita")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> David *(falta apellido — completar)*

---

### 8.2 WhatsApp personal del profesional [obligatorio]
*(Número al que el bot derivará cuando necesite intervención humana. NO tiene que ser el mismo que el del bot)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> 618 974 833

---

### 8.3 Email para notificaciones de derivación [obligatorio]
*(Email al que llega el aviso cuando el bot deriva una conversación)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> david.fisiofit@gmail.com

---

### 8.4 Horario de disponibilidad para responder derivaciones [opcional]
*(ej: "Respondo en horario de clínica, L-V 7-21, S 10-14" / "Puedo responder hasta las 23h" / "24/7")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

### 8.5 ¿Hay más profesionales en el equipo? [opcional]
*Si tienes más fisioterapeutas o entrenadores, indica nombre y servicios que cubren. Si eres solo tú, escribe "Solo yo".*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿trabaja alguien más en la clínica?)*

---

## §9. RGPD y consentimiento

### 9.1 Texto del aviso de privacidad para el primer mensaje [obligatorio]
*El bot mostrará este texto en la primera interacción con cada paciente.*

*(ej: "Al continuar, aceptas que procesemos tus datos para gestionar tu cita. Más info: [URL política privacidad]")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> "Al continuar, aceptas que procesemos tus datos para gestionar tu cita."
>
> *(¿Quieres personalizar el texto? ¿Tienes URL de política de privacidad?)*

---

### 9.2 URL de la política de privacidad completa [obligatorio]
*(Si la tienes en tu web, pega el enlace. Si no la tienes, podemos ayudarte a crearla)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos — ¿tienes política de privacidad publicada?)*

---

### 9.3 ¿Cómo se pide el consentimiento? [obligatorio]
*Elige una:*

- **(A) Consentimiento explícito:** El bot pide que el paciente responda "Acepto" antes de continuar.
- **(B) Consentimiento implícito (RECOMENDADA):** El bot informa y, al continuar la conversación, se entiende como aceptación.

**¿Cuál eliges? (A / B)**

> [PRE-RELLENO]
> Recomendamos **B** — menos fricción, estándar en la industria.

---

## §10. Casos límite (edge-cases)

> Estas preguntas definen cómo reacciona el bot ante situaciones especiales. Si no tienes claro alguna, escribe "No sé — decidir juntos".

### 10.1 ¿Qué hace el bot si un paciente describe síntomas graves? [obligatorio]
*(ej: dolor irradiado nocturno que despierta, fiebre con dolor articular, pérdida de fuerza, traumatismo reciente)*

> [PRE-RELLENO]
> Recomendamos: El bot responde con una frase de derivación: *"Por lo que me cuentas, prefiero que [nombre del profesional] te valore cuanto antes. Te paso con él/ella ahora mismo."* y deriva al fisio.

¿Estás de acuerdo con esta frase? ¿Quieres personalizarla?

---

### 10.2 ¿Y si un paciente quiere reservar para un menor de edad? [obligatorio]
*(ej: "Atiendo menores sin problema" / "Solo mayores de 16" / "Menores con consentimiento del padre/madre — el bot pide que un adulto confirme")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

### 10.3 ¿Y si un paciente pregunta por servicios que no ofrecéis? [obligatorio]
*(ej: "Que diga que no lo ofrecemos y sugiera los servicios que sí tenemos" / "Que derive al fisio" / "Que diga que consulte con la clínica")*

> [PRE-RELLENO]
> Recomendamos: *"Ese servicio no lo ofrecemos actualmente, pero tenemos [servicios relacionados]. ¿Te interesa alguno?"*

---

### 10.4 ¿Trabajáis con mutuas o seguros médicos? [obligatorio]
*(ej: "No, solo privado" / "Sí, aceptamos: Adeslas, Sanitas..." / "Solo algunas — lista: ...")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(En los datos ficticios decía "solo privado" — ¿es correcto?)*

---

### 10.5 ¿Y si un paciente quiere hablar con una persona concreta? [obligatorio]
*(ej: "Derivar directamente" / "Preguntar para qué y si el bot puede ayudar primero" / "Derivar siempre que lo pidan")*

> [PRE-RELLENO]
> Recomendamos: Derivar directamente cuando el paciente lo pida explícitamente.

---

### 10.6 ¿Y si un paciente pide cambiar de profesional? [opcional]
*(ej: "Derivar al fisio para que gestione el cambio" / "El bot puede reasignar" / "No aplica, solo hay un profesional")*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(Sin datos)*

---

### 10.7 Mensaje cuando el bot no entiende [obligatorio]
*¿Qué quieres que diga el bot cuando no comprende lo que le piden?*

*(ej: "Disculpa, no he entendido bien. ¿Puedes reformularlo?" / "No estoy seguro de entenderte. ¿Quieres que te ponga con [profesional]?")*

> [PRE-RELLENO]
> Recomendamos: *"Disculpa, no he entendido bien 😅 ¿Puedes decírmelo de otra forma? Si prefieres, te pongo directamente con [nombre del profesional]."*

---

### 10.8 Preguntas frecuentes que debería manejar el bot [opcional]
*Lista las preguntas que tus pacientes hacen repetidamente y que el bot debería saber responder.*

*(ej: "¿Necesito cita previa?" → Sí. "¿Cuánto dura una sesión?" → Depende del servicio. "¿Dónde puedo aparcar?" → ...)*

> [PRE-RELLENO — VERIFICA SI ES CORRECTO]
> *(El negocio.md ficticio tenía estas FAQ — ¿cuáles son las reales?):*
> 1. ¿Necesito cita previa? →
> 2. ¿Cuánto dura una sesión? →
> 3. ¿Hacéis primera consulta gratuita? →
> 4. ¿Dónde puedo aparcar? →
> 5. ¿Qué debo traer a la primera cita? →
> *(Añade las que falten)*

---

---

## Schema YAML resultante

> Una vez completado el cuestionario, las respuestas se transforman en el siguiente formato YAML que se carga como `business_profile` del tenant en la base de datos.

```yaml
# tenant_id: <uuid>
# slug: clinica-physiofitness
# last_synced_from_db: <timestamp>
# ─────────────────────────────────────────
# Si editas este archivo a mano, ejecuta:
#   python -m app.scripts.profile_sync load --slug clinica-physiofitness
# para que el bot vea tus cambios.

nombre_comercial: "Clínica Physiofitness"
direccion: "Calle Venezuela, 8, 28220 Majadahonda, Madrid"
web_url: "https://www.clinicaphysiofitness.com/"
booking_url: null  # ← completar si tiene enlace externo de reservas
profesional_principal: "David"  # ← completar apellido

servicios:
  - nombre: "Fisioterapia"
    categoria: "fisioterapia"
    duracion_min: 50
    precio_sesion: 55.0
    bonos:
      - sesiones: 5
        precio: 265.0
      - sesiones: 10
        precio: 500.0
    suscripciones: []
    requiere_valoracion_previa: false  # ← CONFIRMAR
    profesional: null  # ← COMPLETAR
    recurso_compartido: null
    grupo_capacidad: null

  - nombre: "Entrenamiento Personal"
    categoria: "entrenamiento"
    duracion_min: 60
    precio_sesion: 50.0
    bonos:
      - sesiones: 5
        precio: 240.0
      - sesiones: 10
        precio: 450.0
    suscripciones: []
    requiere_valoracion_previa: false  # ← CONFIRMAR
    profesional: null  # ← COMPLETAR
    recurso_compartido: null
    grupo_capacidad: null

  - nombre: "Entrenamiento Grupos Reducidos"
    categoria: "entrenamiento"
    duracion_min: 60
    precio_sesion: 55.0
    bonos: []
    suscripciones:
      - modalidad: "1 clase/semana"
        precio_mes: 140.0
      - modalidad: "2 clases/semana"
        precio_mes: 260.0
      - modalidad: "3 clases/semana"
        precio_mes: 360.0
    requiere_valoracion_previa: false  # ← CONFIRMAR
    profesional: null  # ← COMPLETAR
    recurso_compartido: null
    grupo_capacidad: [2, 4]

  - nombre: "Fisio-estética 1 zona (30 min)"
    categoria: "estetica"
    duracion_min: 30
    precio_sesion: 55.0
    bonos:
      - sesiones: 5
        precio: 250.0
      - sesiones: 10
        precio: 500.0
    suscripciones: []
    requiere_valoracion_previa: false  # ← CONFIRMAR
    profesional: null  # ← COMPLETAR
    recurso_compartido: null  # ← ¿INDIBA?
    grupo_capacidad: null

  - nombre: "Fisio-estética 1 zona (45 min)"
    categoria: "estetica"
    duracion_min: 45
    precio_sesion: 70.0
    bonos:
      - sesiones: 5
        precio: 340.0
      - sesiones: 10
        precio: 650.0
    suscripciones: []
    requiere_valoracion_previa: false
    profesional: null
    recurso_compartido: null
    grupo_capacidad: null

  - nombre: "Fisio-estética 2 zonas"
    categoria: "estetica"
    duracion_min: 60
    precio_sesion: 90.0
    bonos:
      - sesiones: 5
        precio: 425.0
      - sesiones: 10
        precio: 800.0
    suscripciones: []
    requiere_valoracion_previa: false
    profesional: null
    recurso_compartido: null
    grupo_capacidad: null

  - nombre: "Fisio-estética 3 zonas"
    categoria: "estetica"
    duracion_min: 60
    precio_sesion: 99.0
    bonos:
      - sesiones: 5
        precio: 475.0
      - sesiones: 10
        precio: 900.0
    suscripciones: []
    requiere_valoracion_previa: false
    profesional: null
    recurso_compartido: null
    grupo_capacidad: null

  - nombre: "Presoterapia"
    categoria: "complementario"
    duracion_min: 30
    precio_sesion: 20.0
    bonos: []  # ← CONFIRMAR si hay bonos
    suscripciones: []
    requiere_valoracion_previa: false
    profesional: null
    recurso_compartido: "Máquina de presoterapia"
    grupo_capacidad: null

  - nombre: "Readaptación Neuromuscular"
    categoria: "complementario"
    duracion_min: null  # ← COMPLETAR duración
    precio_sesion: 60.0
    bonos: []  # ← CONFIRMAR si hay bonos
    suscripciones: []
    requiere_valoracion_previa: false  # ← CONFIRMAR
    profesional: null
    recurso_compartido: "Máquina isocinética"
    grupo_capacidad: null

limites_medicos:
  patologias_tratadas: []  # ← COMPLETAR (§5.1)
  patologias_excluidas: []  # ← COMPLETAR (§5.2)
  contraindicaciones_estetica: []  # ← COMPLETAR (§5.3)
  edad_minima: null  # ← COMPLETAR (§5.4)
  edad_maxima: null
  bot_puede_dar_consejo_clinico: false  # ← Cambiar a true si elige opción B o C en §5.6
  bot_puede_mencionar_precios: true  # ← CONFIRMAR (§5.7)

personalidad:
  tuteo: true  # ← CONFIRMAR (§6.1)
  tono: "cercano"  # ← CONFIRMAR (§6.2)
  usar_emojis: true  # ← CONFIRMAR (§6.3)
  idiomas: ["es"]  # ← CONFIRMAR (§6.4)
  frases_prohibidas: []  # ← COMPLETAR (§6.5)
  firma: null  # ← COMPLETAR si quiere firma (§6.6)

politica_cancelacion_horas: 24  # ← CONFIRMAR (§7.2)
politica_no_show: null  # ← COMPLETAR (§7.3)
rgpd_disclaimer: "Al continuar, aceptas que procesemos tus datos para gestionar tu cita."  # ← CONFIRMAR (§9.1)
```

---

## Notas para el equipo

1. Los campos marcados con `← COMPLETAR` o `← CONFIRMAR` están pendientes de la respuesta del cliente.
2. Una vez validado el cuestionario, el YAML se puede cargar directamente con: `python -m app.scripts.profile_sync load --slug clinica-physiofitness`
3. Los bonos y suscripciones quedan dentro del perfil del negocio y se inyectan en el prompt del bot vía `prompt_builder.py`.
4. Las zonas de fisio-estética (facial, piernas, abdomen, glúteos) se manejan como servicios separados por duración, no como sub-opciones de un servicio único — esto simplifica la lógica de scheduling ya que cada combinación tiene duración y precio distintos.
