# Servicio Ciudadano 1800 — Minería de Datos (KPI v2)

Proyecto de minería de datos sobre el caso Servicio Ciudadano 1800, con los 2 indicadores
de rendimiento reformulados tras la auditoría de KPI. Ver justificación completa en
[`docs/KPIs_v2.md`](docs/KPIs_v2.md).

## Contenido

```
├── docker-compose.yml              # SQL Server en contenedor
├── .env.example                    # variables de conexión (copiar a .env)
├── requirements.txt
├── INSTALACION.md                  # paso a paso para Zorin OS + Docker + VSCodium
├── docs/
│   └── KPIs_v2.md                  # ficha GQM+SMART de los 2 KPI aprobados
├── sql/
│   ├── 01_datawarehouse.sql        # crea BD, staging y esquema dimensional
│   ├── 02_poblar_dw_y_datasets.sql # ETL (normaliza, deduplica, puebla) + vistas de KPI
│   └── 03_dataset_modelo.sql       # vista con todas las variables explicativas (para el modelo)
├── src/
│   ├── database.py                 # conexión (Linux + Docker + ODBC 18)
│   ├── generar_semilla.py          # genera el dataset sintético (10 000 registros)
│   └── cargar_datos.py             # carga los datasets de KPI y del modelo a pandas
├── notebooks/
│   ├── 01_kpis_recontacto_duracion.ipynb
│   └── 02_modelo_recontacto.ipynb  # árbol de decisión sobre recontacto_7_dias
├── verificar_instalacion.py
└── test_conexion.py
```

## Orden de ejecución (resumen — detalle completo en INSTALACION.md)

1. `docker compose up -d` → levanta SQL Server
2. Driver ODBC 18 instalado a nivel de sistema (una sola vez)
3. `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
4. `cp .env.example .env`
5. Ejecutar `sql/01_datawarehouse.sql` contra el contenedor
6. `python verificar_instalacion.py` y `python test_conexion.py`
7. `cd src && python generar_semilla.py`
8. Ejecutar `sql/02_poblar_dw_y_datasets.sql` contra el contenedor
9. Ejecutar `sql/03_dataset_modelo.sql` contra el contenedor
10. Abrir `notebooks/01_kpis_recontacto_duracion.ipynb`
11. Abrir `notebooks/02_modelo_recontacto.ipynb` (árbol de decisión sobre recontacto_7_dias)

## Qué esperar en cada paso

| Paso | Resultado esperado |
|---|---|
| `docker ps` | contenedor `servicio-ciudadano-sqlserver` en estado `Up`/`healthy` |
| `verificar_instalacion.py` | todas las librerías con ✅, incluyendo `ODBC Driver 18 for SQL Server` en la lista de drivers |
| `test_conexion.py` (antes del paso 7-8) | conecta, pero las tablas del DW existen con 0 filas |
| `generar_semilla.py` | mensaje `✅ 10 139 registros insertados...` (10 000 + 139 duplicados intencionales). Con `--solo-resumen` imprime el TR7D, las tasas por canal/motivo/cola y el techo de accuracy esperado, sin tocar la base de datos |
| `test_conexion.py` (después del paso 8) | `c15_callcenter_v0` =10 139, `hecho_interaccion` =10 000 (los duplicados se filtran en el ETL), `vw_kpi_recontacto_7d` =9 830 (excluye los 170 no consolidados) |
| Notebook — TR7D global | cercano a 40.4% (la semilla se calibra a 40.96%), con Red social y "Falla" como las tasas más altas |
| Notebook — DPI por canal | Chat con la duración más alta, Red social con la más baja |
| Notebook 02 — accuracy | la línea base queda en ~59.6% y el árbol `max_depth=5` en ~72.7%: el modelo supera claramente a no hacer nada |

## ⚠️ Sobre los datos

El dataset es **sintético**, generado en `src/generar_semilla.py` (10 000 registros
con la estructura del caso C15_CallCenter). El pipeline completo (Data Warehouse →
ETL → dataset → notebook) se probó sobre esta semilla.
