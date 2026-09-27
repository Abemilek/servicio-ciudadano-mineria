# ============================================
# test_conexion.py
# Prueba de conexión + conteo de registros en las tablas del DW
# ============================================

import sys
sys.path.insert(0, "src")

from database import test_connection, execute_query

if __name__ == "__main__":
    print("\n🔌 PRUEBA 1: Conexión al servidor")
    ok = test_connection()

    if not ok:
        sys.exit(1)

    print("\n\n📊 PRUEBA 2: Conteo de registros en tablas del DW")
    tablas = [
        "c15_callcenter_v0", "hecho_interaccion", "dim_canal",
        "dim_motivo", "dim_cola", "dim_turno", "dim_tiempo",
    ]
    for tabla in tablas:
        df = execute_query(f"SELECT COUNT(*) AS total FROM dbo.{tabla};")
        if df is not None:
            print(f"   📋 {tabla}: {df['total'][0]:,} registros")
        else:
            print(f"   ⚠️ {tabla}: no existe aún. Corre sql/01_datawarehouse.sql primero.")

    print("\n\n🤖 PRUEBA 3: Datasets de los 2 KPI")
    for vista in ["vw_kpi_recontacto_7d", "vw_kpi_duracion_promedio"]:
        df = execute_query(f"SELECT COUNT(*) AS total FROM dbo.{vista};")
        if df is not None:
            print(f"   🤖 {vista}: {df['total'][0]:,} registros")
        else:
            print(f"   ⚠️ {vista}: no existe. Corre sql/02_poblar_dw_y_datasets.sql primero.")
