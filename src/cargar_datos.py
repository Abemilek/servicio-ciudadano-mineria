# ============================================
# src/cargar_datos.py
# Carga los datasets de los 2 KPI aprobados desde SQL Server
# ============================================

from database import execute_query


def cargar_kpi_recontacto():
    """
    Carga el dataset del KPI 1 (Tasa de Recontacto en 7 Días).
    Ya viene filtrado a solo registros consolidados (R-CAL-01).
    """
    print("=" * 60)
    print("📊 CARGANDO DATASET — KPI 1: Tasa de Recontacto en 7 Días")
    print("=" * 60)

    df = execute_query("SELECT * FROM dbo.vw_kpi_recontacto_7d;")
    if df is None:
        return None

    print(f"\n📏 Dimensiones: {df.shape[0]:,} filas × {df.shape[1]} columnas")
    tr7d = df['recontacto_7_dias'].mean() * 100
    print(f"\n🎯 TR7D global: {tr7d:.2f}%")
    print("\n📈 TR7D por canal:")
    print((df.groupby('canal')['recontacto_7_dias'].mean() * 100).round(2))
    print("\n📈 TR7D por motivo:")
    print((df.groupby('motivo_contacto')['recontacto_7_dias'].mean() * 100).round(2))
    print("\n📈 TR7D por cola de servicio:")
    print((df.groupby('cola_servicio')['recontacto_7_dias'].mean() * 100).round(2))

    return df


def cargar_kpi_duracion():
    """Carga el dataset del KPI 2 (Duración Promedio de Interacción)."""
    print("\n" + "=" * 60)
    print("📊 CARGANDO DATASET — KPI 2: Duración Promedio de Interacción")
    print("=" * 60)

    df = execute_query("SELECT * FROM dbo.vw_kpi_duracion_promedio;")
    if df is None:
        return None

    print(f"\n📏 Dimensiones: {df.shape[0]:,} filas × {df.shape[1]} columnas")
    print(f"\n🎯 DPI global: {df['duracion_seg'].mean():.1f} seg "
          f"({df['duracion_seg'].mean() / 60:.1f} min)")
    print("\n📈 DPI por canal:")
    print(df.groupby('canal')['duracion_seg'].mean().round(1))

    return df


def cargar_dataset_modelo():
    """
    Carga el dataset completo para el modelo de minería (variable de
    resultado recontacto_7_dias + todas las variables explicativas).
    Requiere haber ejecutado sql/03_dataset_modelo.sql.
    """
    print("=" * 60)
    print("📊 CARGANDO DATASET — Modelo de Recontacto (todas las variables)")
    print("=" * 60)

    df = execute_query("SELECT * FROM dbo.vw_dataset_modelo_recontacto;")
    if df is None:
        return None

    print(f"\n📏 Dimensiones: {df.shape[0]:,} filas × {df.shape[1]} columnas")
    print(f"\n🎯 Distribución de la variable de resultado (recontacto_7_dias):")
    print(df['recontacto_7_dias'].value_counts())

    return df


if __name__ == "__main__":
    df_recontacto = cargar_kpi_recontacto()
    df_duracion = cargar_kpi_duracion()
    df_modelo = cargar_dataset_modelo()

    print("\n" + "=" * 60)
    print("✅ Datasets cargados en memoria, listos para el notebook")
    print("=" * 60)
