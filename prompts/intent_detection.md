Clasifica la intención del último mensaje del paciente en una clínica de fisioterapia.

Devuelve SOLO una de estas categorías, sin explicación:
- faq (preguntas sobre el negocio: precios, horarios, servicios, ubicación, mutuas)
- agendar_cita (quiere reservar una cita nueva, o está en proceso de hacerlo)
- modificar_cita (quiere cambiar fecha/hora de una cita que ya tiene)
- cancelar_cita (quiere cancelar una cita existente)
- derivar_humano (quiere hablar con una persona, o pide algo que el bot no puede hacer)
- otro (saludo suelto, mensaje irrelevante, o no se puede clasificar)

IMPORTANTE sobre continuación de conversación:
- Si el historial muestra que el paciente está en medio de agendar una cita
  (el bot le preguntó hora, servicio, o confirmación), clasifica como "agendar_cita"
  aunque el mensaje actual sea solo "sí", "a las 10", o un nombre.
- Lo mismo aplica para cancelar y modificar: si el contexto previo es de esa acción,
  mantén la intención aunque el mensaje actual sea ambiguo.
