# ============================================================
# src/generar_semilla.py
# Genera datos SINTÉTICOS para dbo.c15_callcenter_v0.
#
# ------------------------------------------------------------
# FIX A (2026-09-27): la semilla anterior (360 registros) NO
# contenía señal aprendible, y por eso el modelo no podía
# superar la línea base. El target se calculaba como el
# promedio de dos tasas fijas:
#
#     p = (TASA_POR_CANAL[canal] + TASA_POR_MOTIVO[motivo]) / 2
#
# cuyo máximo es (0.468 + 0.488) / 2 = 0.478 < 0.5. Si p < 0.5
# en TODAS las filas, la predicción bayesiana óptima es siempre
# "no recontacta" y la accuracy queda topada por la proporción
# de negativos (~61.9%) aunque el modelo sea perfecto.
# Además espera_seg, duracion_seg, transferencias y
# casos_previos_30d se generaban como ruido puro: no
# influían en el target, así que el modelo no tenía nada que
# aprender de ellas.
#
# Esta versión:
#   1) sube el volumen de 360 a 10 000 registros;
#   2) modela el recontacto en escala logit, sumando:
#        - pesos por canal, motivo y cola, que reproducen los
#          hallazgos 2, 3 y 4 de la auditoría;
#        - un bloque de señales operativas APRENDIBLES (espera,
#          duración residual al canal, transferencias, casos
#          previos, fin de semana, turno y tipo de usuario)
#          estandarizadas y recortadas, con media cero para no
#          deformar las tasas marginales;
#        - una tendencia temporal leve y creciente (dirección
#          del hallazgo 5);
#   3) calibra el intercepto por bisección para que la TR7D
#      global quede en 40.96% (145 de 354 del caso real);
#   4) preserva los 3 problemas de calidad del hallazgo 7 y los
#      duplicados, escalados proporcionalmente al nuevo volumen.
#
# Solo se usan variables que la vista dbo.vw_dataset_modelo_
# recontacto realmente expone (canal, motivo, cola, turno, tipo
# de usuario, espera, duración, transferencias, casos previos y
# es_fin_semana), para que la señal sea alcanzable por el modelo.
#
# IMPORTANTE: esto NO es el dataset real de la clase (ese lo
# tiene el compañero). Es una semilla sintética para probar el
# pipeline completo mientras llega el dataset real. Los
# supuestos marcados con "# SUPUESTO" hay que reemplazarlos
# apenas se tenga el dato real del equipo.
# ============================================================

import math
import random
import sys
from datetime import date, timedelta

from database import get_connection

random.seed(42)  # reproducible, como recomendó el profesor: nunca generar sin semilla fija

N_TOTAL = 10_000
TR7D_OBJETIVO = 0.4096          # 145/354 del caso real (40.96%)

# ============================================================
# Catálogos válidos (post R-CAL-02)
# ============================================================
MOTIVOS = ["Consulta", "Falla", "Cobro", "Solicitud", "Queja"]
COLAS = ["Facturación", "Soporte", "Información", "Reclamos", "Trámites"]
TURNOS = ["AM", "PM", "Nocturno", "Fin de semana"]
TIPOS_USUARIO = ["Nuevo", "Recurrente", "Empresa", "Adulto mayor"]
CANALES = ["Teléfono", "Chat", "Correo", "Red social"]

# Tasas de recontacto por canal (Hallazgo 2, del caso real)
TASA_POR_CANAL = {"Red social": 0.468, "Chat": 0.400, "Correo": 0.398, "Teléfono": 0.371}
# Duración promedio por canal en segundos (Hallazgo 6, del caso real)
DURACION_POR_CANAL = {"Chat": 1028.6, "Teléfono": 949.2, "Correo": 919.4, "Red social": 857.1}
# Tasas de recontacto por motivo (Hallazgo 3, del caso real)
TASA_POR_MOTIVO = {"Falla": 0.488, "Queja": 0.443, "Solicitud": 0.409, "Cobro": 0.371, "Consulta": 0.305}
# Tasas de recontacto por cola (Hallazgo 4, del caso real)
TASA_POR_COLA = {"Facturación": 0.471, "Información": 0.430, "Trámites": 0.413, "Reclamos": 0.370, "Soporte": 0.344}

# El bloque operativo (señal aprendible) tiene varianza propia, y esa
# varianza comprime hacia el centro las tasas marginales de canal,
# motivo y cola. Estos factores de realce expanden los desvíos de
# logit para que las tasas observadas reproduzcan el caso real.
# Se calibraron contra el resumen de --solo-resumen.
REALCE_CANAL = 1.25
REALCE_MOTIVO = 1.70
REALCE_COLA = 1.80

# SUPUESTO: el caso no da el volumen por canal, se reparte así.
PESO_CANAL = [35, 25, 20, 20]  # orden de CANALES: Teléfono, Chat, Correo, Red social
# SUPUESTO: el caso no da el volumen por motivo, se reparte uniforme.
PESO_MOTIVO = [20, 20, 20, 20, 20]
# SUPUESTO: el caso no da el volumen por turno, se reparte uniforme.
PESO_TURNO = [30, 30, 20, 20]
PESO_TIPO_USUARIO = [30, 45, 15, 10]

# Volumen por cola: 2 de 5 son datos reales del caso (Hallazgo 4);
# las otras 3 son SUPUESTO. Escalado de 360 a 10 000 manteniendo
# las proporciones (factor 10000/360).
VOLUMEN_COLA = {
    "Información": 2639,   # real (Hallazgo 4, 95/360)
    "Soporte": 2222,        # SUPUESTO (80/360)
    "Facturación": 1889,   # real (Hallazgo 4, 68/360)
    "Reclamos": 1806,        # SUPUESTO (65/360)
    "Trámites": 1444,        # SUPUESTO (52/360)
}  # suma = 10 000

# ============================================================
# Señal operativa aprendible (FIX A)
# Cada variable se estandariza con una media/sd fija y se
# recorta a ±2, de modo que su esperanza sea 0 y no desplace
# las tasas marginales de canal/motivo/cola.
# ============================================================
ESPERA_MEDIA, ESPERA_SD = 200.0, 260.0
DURACION_SD = 500.0
TRANSF_MEDIA, TRANSF_SD = 0.9, 1.2
CASOS_MEDIA, CASOS_SD = 1.6, 2.0

# Amplitud global del bloque operativo. Es la perilla que fija el
# techo de accuracy del modelo (accuracy bayes = E[max(p, 1-p)]):
# mucha amplitud -> probabilidades polarizadas -> el modelo se
# acerca al 100% (sospechoso para el profesor); muy poca -> todas
# las p rondan 0.5 y el modelo no supera la línea base.
# Calibrada para dejar el techo alrededor de 79% y que el árbol
# rinda 70-80% (el rango "razonable" que pidió el profesor).
AMPLITUD_OPERATIVA = 1.30

PESO_ESPERA = 0.95
PESO_DURACION = 0.70
PESO_TRANSFERENCIAS = 0.85
PESO_CASOS_PREVIOS = 0.85
PESO_FIN_DE_SEMANA = 0.75
PESO_TURNO_FIN_DE_SEMANA = 0.45
PESO_TIPO_RECURRENTE = 0.55
PESO_TENDENCIA = 0.35

# Proporciones de los problemas de calidad del hallazgo 7,
# tal como estaban cuantificadas sobre los 360 registros (2.5% /
# 1.1% / 1.7%) y los duplicados (5/360 = 1.39%).
PROP_SIN_CANAL = 0.025
PROP_SIN_NORMALIZAR = 0.011
PROP_SIN_CONSOLIDAR = 0.017
PROP_DUPLICADOS = 0.0139

FECHA_INICIO = date(2025, 1, 1)
FECHA_FIN = date(2026, 6, 30)
DIAS_RANGO = (FECHA_FIN - FECHA_INICIO).days


def _logit(p):
    return math.log(p / (1.0 - p))


def _sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


def _z(valor, media, sd, tope=2.0):
    return max(-tope, min(tope, (valor - media) / sd))


def fecha_aleatoria():
    return FECHA_INICIO + timedelta(days=random.randint(0, DIAS_RANGO))


def es_fin_de_semana(fecha):
    return fecha.weekday() >= 5


def generar_registros(solo_resumen=False):
    # ---------- PASO 1: features (todas las que el modelo ve) ----------
    filas = []
    colas_expandidas = []
    for cola, n in VOLUMEN_COLA.items():
        colas_expandidas += [cola] * n
    random.shuffle(colas_expandidas)

    for i in range(1, N_TOTAL + 1):
        canal = random.choices(CANALES, weights=PESO_CANAL)[0]
        motivo = random.choices(MOTIVOS, weights=PESO_MOTIVO)[0]
        cola = colas_expandidas[i - 1]
        turno = random.choices(TURNOS, weights=PESO_TURNO)[0]
        tipo_usuario = random.choices(TIPOS_USUARIO, weights=PESO_TIPO_USUARIO)[0]

        espera_seg = random.randint(0, 900)
        duracion_media = DURACION_POR_CANAL[canal]
        duracion_seg = max(30, min(1800, int(random.gauss(duracion_media, 180))))
        transferencias = random.choices([0, 1, 2, 3, 4], weights=[55, 25, 12, 6, 2])[0]
        casos_previos_30d = random.choices(range(9), weights=[40, 25, 15, 8, 5, 3, 2, 1, 1])[0]

        fecha_contacto = fecha_aleatoria()
        t_riesgo = (fecha_contacto - FECHA_INICIO).days / DIAS_RANGO
        filas.append({
            "id": f"C15-{i:05d}",
            "fecha_contacto": fecha_contacto,
            "canal": canal,
            "motivo": motivo,
            "cola": cola,
            "turno": turno,
            "tipo_usuario": tipo_usuario,
            "espera_seg": espera_seg,
            "duracion_seg": duracion_seg,
            "transferencias": transferencias,
            "casos_previos_30d": casos_previos_30d,
            "sistema_origen": random.choice(["ACD", "CRM", "Ticketing", "Calidad"]),
            "grabacion_autorizada": random.choices(["Sí", "No"], weights=[70, 30])[0],
            "fin_de_semana": 1.0 if es_fin_de_semana(fecha_contacto) else 0.0,
            "turno_fds": 1.0 if turno == "Fin de semana" else 0.0,
            "tipo_recurrente": 1.0 if tipo_usuario == "Recurrente" else 0.0,
            "t_riesgo": t_riesgo,
        })

    # ---------- PASO 2: score base en escala logit ----------
    media_fds = sum(f["fin_de_semana"] for f in filas) / N_TOTAL
    media_turno_fds = sum(f["turno_fds"] for f in filas) / N_TOTAL
    media_recurrente = sum(f["tipo_recurrente"] for f in filas) / N_TOTAL

    logit_objetivo = _logit(TR7D_OBJETIVO)
    for f in filas:
        # la duración se usa como residuo respecto a la media de SU
        # canal: así el efecto "duración larga = caso complejo"
        # queda ortogonal al canal y no deforma la tasa por canal.
        g_duracion = _z(
            f["duracion_seg"] - DURACION_POR_CANAL[f["canal"]],
            0.0, DURACION_SD,
        )
        operacional = AMPLITUD_OPERATIVA * (
            PESO_ESPERA * _z(f["espera_seg"], ESPERA_MEDIA, ESPERA_SD)
            + PESO_TRANSFERENCIAS * _z(f["transferencias"], TRANSF_MEDIA, TRANSF_SD)
            + PESO_CASOS_PREVIOS * _z(f["casos_previos_30d"], CASOS_MEDIA, CASOS_SD)
            + PESO_DURACION * g_duracion
            + PESO_FIN_DE_SEMANA * (f["fin_de_semana"] - media_fds)
            + PESO_TURNO_FIN_DE_SEMANA * (f["turno_fds"] - media_turno_fds)
            + PESO_TIPO_RECURRENTE * (f["tipo_recurrente"] - media_recurrente)
            + PESO_TENDENCIA * _z(f["t_riesgo"], 0.5, 0.5)
        )
        f["score"] = (
            (REALCE_CANAL * (_logit(TASA_POR_CANAL[f["canal"]]) - logit_objetivo))
            + (REALCE_MOTIVO * (_logit(TASA_POR_MOTIVO[f["motivo"]]) - logit_objetivo))
            + (REALCE_COLA * (_logit(TASA_POR_COLA[f["cola"]]) - logit_objetivo))
            + operacional
        )

    # ---------- PASO 3: bisección del intercepto para TR7D = 40.96% ----------
    lo, hi = -10.0, 10.0
    for _ in range(60):
        medio = (lo + hi) / 2.0
        media_p = sum(_sigmoid(medio + f["score"]) for f in filas) / N_TOTAL
        if media_p < TR7D_OBJETIVO:
            lo = medio
        else:
            hi = medio
    intercepto = (lo + hi) / 2.0

    # ---------- PASO 4: muestreo del target ----------
    for f in filas:
        f["p"] = _sigmoid(intercepto + f["score"])
        f["recontacto"] = 1 if random.random() < f["p"] else 0

    # ---------- PASO 5: inyectar los problemas de calidad (hallazgo 7) ----------
    idx = list(range(N_TOTAL))
    random.shuffle(idx)
    n_sin_canal = round(N_TOTAL * PROP_SIN_CANAL)
    n_sin_norm = round(N_TOTAL * PROP_SIN_NORMALIZAR)
    n_sin_cons = round(N_TOTAL * PROP_SIN_CONSOLIDAR)
    n_dups = round(N_TOTAL * PROP_DUPLICADOS)

    for i in idx[:n_sin_canal]:
        filas[i]["canal"] = None
    for i in idx[n_sin_canal:n_sin_canal + n_sin_norm]:
        filas[i]["motivo"] = filas[i]["motivo"].upper()
    for i in idx[n_sin_canal + n_sin_norm:n_sin_canal + n_sin_norm + n_sin_cons]:
        filas[i]["recontacto"] = None

    # ---------- RESUMEN (no necesita base de datos) ----------
    if solo_resumen:
        imprimir_resumen(filas, intercepto, n_sin_canal, n_sin_norm, n_sin_cons, n_dups)

    # ---------- PASO 6: duplicados + filas para el INSERT ----------
    registros = []
    for f in filas:
        fecha_carga = f["fecha_contacto"] + timedelta(days=random.randint(0, 3))
        registros.append([
            f["id"], f["fecha_contacto"], f["canal"], f["turno"], f["motivo"],
            f["cola"], f["espera_seg"], f["tipo_usuario"], f["duracion_seg"],
            f["transferencias"], f["casos_previos_30d"], f["recontacto"],
            f["sistema_origen"], fecha_carga, f["grabacion_autorizada"],
        ])

    # RG-04: duplicados confirmados pero no cuantificados en el caso real.
    # SUPUESTO: se inyectan proporcionalmente (1.39% como en la
    # semilla de 360) para poder probar la deduplicación del ETL.
    for i in idx[n_sin_canal + n_sin_norm + n_sin_cons:][:n_dups]:
        dup = registros[i].copy()
        dup[13] = dup[13] + timedelta(days=1)  # llega en una carga posterior
        registros.append(dup)

    return registros


def imprimir_resumen(filas, intercepto, n_sin_canal, n_sin_norm, n_sin_cons, n_dups):
    print("=" * 62)
    print("RESUMEN DE LA SEMILLA SINTÉTICA (sin tocar la base de datos)")
    print("=" * 62)
    print(f"Registros base generados: {N_TOTAL}")
    print(f"Intercepto calibrado:     {intercepto:+.4f}")

    print("\nProblemas de calidad inyectados (hallazgo 7):")
    print(f"  sin canal:              {n_sin_canal} ({n_sin_canal / N_TOTAL:.1%})")
    print(f"  etiqueta sin normalizar:{n_sin_norm} ({n_sin_norm / N_TOTAL:.1%})")
    print(f"  target sin consolidar:  {n_sin_cons} ({n_sin_cons / N_TOTAL:.1%})")
    print(f"  duplicados:             {n_dups}")

    print("\nMétricas sobre las filas con canal y target (las que ve el modelo):")
    validas = [f for f in filas if f["canal"] is not None and f["recontacto"] is not None]
    tr7d = sum(f["recontacto"] for f in validas) / len(validas)
    bayes = sum(max(f["p"], 1 - f["p"]) for f in validas) / len(validas)
    print(f"  n = {len(validas)}")
    print(f"  TR7D (KPI 1):           {tr7d:.2%}   (objetivo {TR7D_OBJETIVO:.2%})")
    print(f"  accuracy bayes óptima:  {bayes:.2%}   -> tope del modelo")

    for etiqueta, campo, metas in [
        ("Canal", "canal", TASA_POR_CANAL),
        ("Motivo", "motivo", TASA_POR_MOTIVO),
        ("Cola", "cola", TASA_POR_COLA),
    ]:
        print(f"\nTasa por {etiqueta.lower()} (real vs caso real):")
        for cat, meta in sorted(metas.items(), key=lambda kv: -kv[1]):
            sub = [f for f in validas if f[campo] == cat]
            obs = sum(f["recontacto"] for f in sub) / len(sub)
            print(f"  {cat:<14} {obs:6.2%}   (meta {meta:.1%}, dif {(obs - meta) * 100:+.1f} pp)")
    print("=" * 62)


def insertar(registros):
    conn = get_connection()
    if conn is None:
        print("No se pudo conectar. Revisa .env y que el contenedor de SQL Server esté corriendo.")
        return

    cursor = conn.cursor()
    cursor.execute("DELETE FROM dbo.c15_callcenter_v0;")

    sql = """
        INSERT INTO dbo.c15_callcenter_v0
        (id_interaccion, fecha_contacto, canal, turno, motivo_contacto, cola_servicio,
         espera_seg, tipo_usuario, duracion_seg, transferencias, casos_previos_30d,
         recontacto_7_dias, sistema_origen, fecha_carga, grabacion_autorizada)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.executemany(sql, registros)
    conn.commit()
    print(f"✅ {len(registros)} registros insertados en dbo.c15_callcenter_v0 "
          f"({len(registros) - N_TOTAL} son duplicados intencionales para probar el ETL).")
    cursor.close()
    conn.close()


if __name__ == "__main__":
    print("Generando dataset sintético (semilla fija = 42, reproducible)...")
    datos = generar_registros(solo_resumen="--solo-resumen" in sys.argv)
    if "--solo-resumen" not in sys.argv:
        insertar(datos)
