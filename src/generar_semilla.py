# ============================================================
# src/generar_semilla.py
# Genera datos SINTÉTICOS para dbo.c15_callcenter_v0, ajustados
# para reproducir (aproximadamente) los hallazgos ya calculados
# en kpi-audicion.md: TR7D global ~41%, tasas por canal/motivo/
# cola, y los 3 problemas de calidad cuantificados (canal sin
# dato, etiquetas sin normalizar, target sin consolidar).
#
# IMPORTANTE: esto NO es el dataset real de la clase (ese lo
# tiene el compañero). Es una semilla sintética para poder
# probar el pipeline completo mientras llega el dataset real.
# Los supuestos marcados con "# SUPUESTO" son proporciones que
# el caso de estudio no especificó (volumen exacto por canal,
# cantidad real de duplicados) y que aquí se fijaron de forma
# razonable para que el pipeline sea reproducible — hay que
# reemplazarlos apenas tengan el dataset real del equipo.
# ============================================================

import random
from datetime import date, timedelta

from database import get_connection

random.seed(42)  # reproducible, como recomendó el profesor: nunca generar sin semilla fija

N_TOTAL = 360

# --- Catálogos válidos (post R-CAL-02) ---
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

# Volumen por cola: 2 de 5 son datos reales del caso (Hallazgo 4);
# las otras 3 son SUPUESTO (se reparte el resto proporcional a la tasa)
VOLUMEN_COLA = {
    "Información": 95,   # real (Hallazgo 4)
    "Facturación": 68,   # real (Hallazgo 4)
    "Soporte": 80,        # SUPUESTO
    "Reclamos": 65,        # SUPUESTO
    "Trámites": 52,        # SUPUESTO
}  # suma = 360

FECHA_INICIO = date(2025, 1, 1)
FECHA_FIN = date(2026, 6, 30)


def fecha_aleatoria():
    dias = (FECHA_FIN - FECHA_INICIO).days
    return FECHA_INICIO + timedelta(days=random.randint(0, dias))


def generar_registros():
    registros = []
    # arma la lista de colas según el volumen definido arriba
    colas_expandidas = []
    for cola, n in VOLUMEN_COLA.items():
        colas_expandidas += [cola] * n
    random.shuffle(colas_expandidas)

    for i in range(1, N_TOTAL + 1):
        id_interaccion = f"C15-{i:04d}"
        canal = random.choices(CANALES, weights=[35, 25, 20, 20])[0]  # SUPUESTO: no viene el volumen real por canal
        motivo = random.choice(MOTIVOS)
        cola = colas_expandidas[i - 1]
        turno = random.choice(TURNOS)
        tipo_usuario = random.choices(TIPOS_USUARIO, weights=[30, 45, 15, 10])[0]

        espera_seg = random.randint(0, 900)
        duracion_media = DURACION_POR_CANAL[canal]
        duracion_seg = max(30, min(1800, int(random.gauss(duracion_media, 180))))
        transferencias = random.choices([0, 1, 2, 3, 4], weights=[55, 25, 12, 6, 2])[0]
        casos_previos_30d = random.choices(range(9), weights=[40, 25, 15, 8, 5, 3, 2, 1, 1])[0]

        # combina la tasa por canal y por motivo (promedio simple) para decidir el target
        prob_recontacto = (TASA_POR_CANAL[canal] + TASA_POR_MOTIVO[motivo]) / 2
        recontacto = 1 if random.random() < prob_recontacto else 0

        sistema_origen = random.choice(["ACD", "CRM", "Ticketing", "Calidad"])
        fecha_contacto = fecha_aleatoria()
        fecha_carga = fecha_contacto + timedelta(days=random.randint(0, 3))
        grabacion_autorizada = random.choices(["Sí", "No"], weights=[70, 30])[0]

        registros.append([
            id_interaccion, fecha_contacto, canal, turno, motivo, cola, espera_seg,
            tipo_usuario, duracion_seg, transferencias, casos_previos_30d, recontacto,
            sistema_origen, fecha_carga, grabacion_autorizada,
        ])

    # --- inyectar los 3 problemas de calidad ya cuantificados (Hallazgo 7) ---
    idx = list(range(N_TOTAL))
    random.shuffle(idx)

    for i in idx[:9]:  # 9/360 sin canal (2.5%)
        registros[i][2] = None

    for i in idx[9:13]:  # 4/360 con etiqueta sin normalizar (1.1%)
        registros[i][4] = registros[i][4].upper()

    for i in idx[13:19]:  # 6/360 sin consolidar (1.7%)
        registros[i][11] = None

    # --- duplicados (RG-04: confirmados pero sin cuantificar en el caso real) ---
    # SUPUESTO: se inyectan 5 duplicados para poder probar la deduplicación del ETL
    for i in idx[19:24]:
        dup = registros[i].copy()
        dup[13] = dup[13] + timedelta(days=1)  # llega en una carga posterior
        registros.append(dup)

    return registros


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
    datos = generar_registros()
    insertar(datos)
