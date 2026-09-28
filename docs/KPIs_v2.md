# Indicadores de Rendimiento v2 — Caso Servicio Ciudadano 1800

> Reformulados tras la auditoría de indicadores. De los 10 indicadores
> originales en `kpi-audicion.md`, solo dos correspondían a **operaciones de negocio
> distintas**. El resto eran el mismo indicador (Tasa de Recontacto) cortado por una
> dimensión distinta cada vez (canal, motivo, cola, tiempo), o eran indicadores de
> **gobierno de datos / ETL** (normalización de etiquetas, completitud de canal,
> consolidación del target) que no tienen cabida como KPI de negocio — esos ya están
> cubiertos como reglas de calidad (R-CAL-01 a R-CAL-06) en el Marco de Gobierno.
>
> Criterio: *"no existen dos KPI con la misma operación solo porque cambia
> la dimensión"*. Canal, motivo, cola de servicio y tiempo son **dimensiones** del mismo
> hecho (la interacción) — se usan para desagregar el KPI en un dashboard, no para
> crear un KPI nuevo por cada una.

---

## KPI 1 — Tasa de Recontacto en 7 Días (TR7D)

**Responde a:** ¿Qué tan seguido un usuario vuelve a contactar por el mismo motivo
dentro de los 7 días posteriores a su interacción? Es un indicador de **calidad de
resolución en el primer contacto**: si el caso se resolvió bien, no hay razón para
que el usuario regrese por lo mismo.

**Definición operativa** (según diccionario del caso, Punto 13 del Marco de Gobierno):
un registro cuenta como recontacto cuando el usuario vuelve a contactar por el **mismo
motivo** dentro de los 7 días siguientes a la interacción original. No se está midiendo
que el agente vuelva a llamar al usuario, sino que el usuario regresa por no haber
quedado resuelto.

- **Fórmula:** `TR7D = (Σ recontacto_7_dias = 1) / (Σ registros con recontacto_7_dias consolidado) × 100`
- **Unidad:** Porcentaje
- **Frecuencia de cálculo:** Mensual
- **Fuente de datos:** CRM / Calidad → tabla de hechos `hecho_interaccion`, campo `recontacto_7_dias`
- **Dimensiones para desagregar (NO son KPI aparte):** canal, motivo_contacto, cola_servicio, turno, mes
- **Regla de exclusión:** los registros con `recontacto_7_dias` vacío (no consolidado) se excluyen del cálculo, no se cuentan como 0
- **Línea base:** 40.96%
- **Semilla sintética:** `src/generar_semilla.py` genera 10 000 registros y calibra por
  bisección el intercepto del modelo logit para que la TR7D consolidada quede en ~40.4% sobre
  9 830 registros (10 000 menos 139 duplicados y 170 no consolidados).

**Validación SMART**
| Criterio | Cumple | Justificación |
|---|---|---|
| Specific | ✔ | Numerador y denominador definidos sin ambigüedad; dos analistas obtienen el mismo resultado |
| Measurable | ✔ | El campo existe en CRM/Calidad y ya está en el diccionario de datos |
| Achievable | ✔ | No requiere infraestructura nueva, solo aplicar la regla de exclusión R-CAL-01 |
| Relevant | ✔ | Ataca directamente el problema institucional: decisiones de asignación, conocimiento y resolución |
| Time-bound | ✔ | Cálculo mensual, permite comparar contra la línea base y detectar tendencia |

**Prueba "¿Y qué?":** *"Nuestra tasa de recontacto es 41%."* — "¿Y eso es bueno o malo?" —
"Es alto: casi 2 de cada 5 interacciones resueltas terminan generando un nuevo contacto
por lo mismo en menos de una semana. Eso apunta a un problema de resolución en el primer
contacto, no de volumen de llamadas." → **Pasa la prueba.**

---

## KPI 2 — Duración Promedio de Interacción (DPI)

**Responde a:** ¿Cuánto tiempo toma en promedio atender una interacción? Es un
indicador de **eficiencia operativa**, independiente del de recontacto (mide otra
operación: promedio de una variable numérica, no una tasa de eventos).

- **Fórmula:** `DPI = Σ duracion_seg / Σ registros`
- **Unidad:** Segundos (se puede mostrar también en minutos)
- **Frecuencia de cálculo:** Mensual
- **Fuente de datos:** CRM → tabla de hechos `hecho_interaccion`, campo `duracion_seg`
- **Dimensiones para desagregar (NO son KPI aparte):** canal, motivo_contacto, turno, mes
- **Línea base por canal:** Chat 1,028.6 seg · Teléfono 949.2 seg · Correo 919.4 seg · Red social 857.1 seg
  *(el promedio global ponderado queda pendiente de conocer el volumen por canal)*

**Validación SMART**
| Criterio | Cumple | Justificación |
|---|---|---|
| Specific | ✔ | Promedio simple de un campo numérico validado en rango (R-CAL-05: 30–1800 seg) |
| Measurable | ✔ | Campo numérico disponible directamente en CRM |
| Achievable | ✔ | Cálculo directo, sin transformación adicional |
| Relevant | ✔ | Relacionado con eficiencia operativa y asignación de personal por cola/canal |
| Time-bound | ✔ | Cálculo mensual |

**Cruce interesante (hipótesis, no confirmada):** Red social tiene la duración promedio
más corta (857.1 seg) pero la tasa de recontacto más alta (46.8%) — sugiere que
interacciones más rápidas en ese canal podrían estar asociadas a resoluciones
superficiales. Esto se puede llevar como pregunta al modelo de minería (árbol de
decisión), no se declara como hallazgo confirmado.

---

## Lo que quedó descartado como KPI de negocio (y por qué)

| Indicador original | Por qué no es un KPI de negocio aparte |
|---|---|
| TR7D por canal / motivo / cola / tiempo | Son el mismo KPI 1, solo cortado por dimensión — se muestran como filtros del dashboard, no como indicadores nuevos |
| Índice de normalización de etiquetas | Es responsabilidad de ETL/gobierno de datos (regla R-CAL-02), no algo que le sirva al gerente para decidir |
| Tasa de completitud del canal | Operativamente el canal no debería faltar nunca (regla R-CAL-03); no es un indicador de negocio, es un control de calidad |
| Consolidación de la variable resultado | Es un prerrequisito técnico para poder calcular el KPI 1 (regla R-CAL-01), no un KPI en sí |
| Índice de concentración por motivo/cola (Pareto) | Es un análisis de apoyo (para priorizar dónde intervenir), no una operación de negocio distinta — se puede mostrar como parte del dashboard del KPI 1 |
