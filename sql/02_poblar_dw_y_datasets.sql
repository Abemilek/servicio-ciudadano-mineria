-- ============================================================
-- SERVICIO CIUDADANO 1800 - ETL (staging -> dimensional)
-- y datasets (vistas) para los 2 KPI aprobados
-- Ejecutar DESPUÉS de que src/generar_semilla.py haya poblado
-- dbo.c15_callcenter_v0
-- ============================================================

USE ServicioCiudadanoDW;
GO

-- ============================================================
-- 1. NORMALIZACIÓN previa (regla R-CAL-02: catálogo único)
--    Se corrige en una vista, sin tocar el dato crudo del v0,
--    para conservar trazabilidad hacia el dataset original.
-- ============================================================
IF OBJECT_ID('dbo.vw_c15_normalizado', 'V') IS NOT NULL DROP VIEW dbo.vw_c15_normalizado;
GO
CREATE VIEW dbo.vw_c15_normalizado AS
SELECT
    id_interaccion,
    fecha_contacto,
    NULLIF(LTRIM(RTRIM(canal)), '')                          AS canal,
    turno,
    UPPER(LEFT(LTRIM(RTRIM(motivo_contacto)), 1))
        + LOWER(SUBSTRING(LTRIM(RTRIM(motivo_contacto)), 2, 50)) AS motivo_contacto,  -- R-CAL-02
    cola_servicio,
    espera_seg,
    tipo_usuario,
    duracion_seg,
    transferencias,
    casos_previos_30d,
    recontacto_7_dias,
    sistema_origen,
    fecha_carga,
    grabacion_autorizada
FROM dbo.c15_callcenter_v0;
GO

-- ============================================================
-- 1.b RESET — el ETL debe poder RE-EJECUTARSE sin duplicar
--     El staging se regenera completo con generar_semilla.py, así
--     que aqui se vacian las dimensiones y el hecho para que una
--     segunda corrida no mezcle el dataset viejo con el nuevo.
--     Orden obligatorio: primero la tabla de hechos, porque es la
--     que tiene las claves foraneas hacia las dimensiones.
-- ============================================================
DELETE FROM dbo.hecho_interaccion;
GO
DELETE FROM dbo.dim_canal;
DELETE FROM dbo.dim_motivo;
DELETE FROM dbo.dim_cola;
DELETE FROM dbo.dim_turno;
DELETE FROM dbo.dim_tipo_usuario;
DELETE FROM dbo.dim_tiempo;
GO
-- Las claves IDENTITY siguen la posicion de las filas borradas; se
-- reinician para que el DW quede siempre en el mismo estado.
DBCC CHECKIDENT('dbo.dim_canal', RESEED, 0) WITH NO_INFOMSGS;
DBCC CHECKIDENT('dbo.dim_motivo', RESEED, 0) WITH NO_INFOMSGS;
DBCC CHECKIDENT('dbo.dim_cola', RESEED, 0) WITH NO_INFOMSGS;
DBCC CHECKIDENT('dbo.dim_turno', RESEED, 0) WITH NO_INFOMSGS;
DBCC CHECKIDENT('dbo.dim_tipo_usuario', RESEED, 0) WITH NO_INFOMSGS;
GO

-- ============================================================
-- 2. POBLAR DIMENSIONES (a partir del v0 ya normalizado)
-- ============================================================
INSERT INTO dbo.dim_canal (canal)
SELECT DISTINCT canal FROM dbo.vw_c15_normalizado
WHERE canal IS NOT NULL
  AND canal NOT IN (SELECT canal FROM dbo.dim_canal);

INSERT INTO dbo.dim_motivo (motivo_contacto)
SELECT DISTINCT motivo_contacto FROM dbo.vw_c15_normalizado
WHERE motivo_contacto NOT IN (SELECT motivo_contacto FROM dbo.dim_motivo);

INSERT INTO dbo.dim_cola (cola_servicio)
SELECT DISTINCT cola_servicio FROM dbo.vw_c15_normalizado
WHERE cola_servicio NOT IN (SELECT cola_servicio FROM dbo.dim_cola);

INSERT INTO dbo.dim_turno (turno)
SELECT DISTINCT turno FROM dbo.vw_c15_normalizado
WHERE turno NOT IN (SELECT turno FROM dbo.dim_turno);

INSERT INTO dbo.dim_tipo_usuario (tipo_usuario)
SELECT DISTINCT tipo_usuario FROM dbo.vw_c15_normalizado
WHERE tipo_usuario NOT IN (SELECT tipo_usuario FROM dbo.dim_tipo_usuario);

INSERT INTO dbo.dim_tiempo (fecha, anio, mes, nombre_mes, dia, dia_semana, nombre_dia_semana, trimestre, es_fin_semana)
SELECT DISTINCT
    fecha_contacto,
    YEAR(fecha_contacto),
    MONTH(fecha_contacto),
    DATENAME(MONTH, fecha_contacto),
    DAY(fecha_contacto),
    DATEPART(WEEKDAY, fecha_contacto),
    DATENAME(WEEKDAY, fecha_contacto),
    DATEPART(QUARTER, fecha_contacto),
    CASE WHEN DATEPART(WEEKDAY, fecha_contacto) IN (1,7) THEN 1 ELSE 0 END
FROM dbo.vw_c15_normalizado
WHERE fecha_contacto NOT IN (SELECT fecha FROM dbo.dim_tiempo);
GO

-- ============================================================
-- 3. POBLAR TABLA DE HECHOS
--    R-CAL-04 (unicidad): los duplicados de id_interaccion
--    inyectados por generar_semilla.py se filtran aquí,
--    quedándonos con el primero (por fecha_carga).
-- ============================================================
;WITH dedup AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY id_interaccion ORDER BY fecha_carga) AS rn
    FROM dbo.vw_c15_normalizado
)
INSERT INTO dbo.hecho_interaccion
    (id_interaccion, fecha_contacto, id_canal, id_motivo, id_cola, id_turno,
     id_tipo_usuario, espera_seg, duracion_seg, transferencias, casos_previos_30d,
     recontacto_7_dias, sistema_origen, grabacion_autorizada)
SELECT
    d.id_interaccion,
    d.fecha_contacto,
    c.id_canal,
    m.id_motivo,
    q.id_cola,
    t.id_turno,
    u.id_tipo_usuario,
    d.espera_seg,
    d.duracion_seg,
    d.transferencias,
    d.casos_previos_30d,
    d.recontacto_7_dias,
    d.sistema_origen,
    d.grabacion_autorizada
FROM dedup d
LEFT JOIN dbo.dim_canal c ON c.canal = d.canal
JOIN dbo.dim_motivo m ON m.motivo_contacto = d.motivo_contacto
JOIN dbo.dim_cola q ON q.cola_servicio = d.cola_servicio
JOIN dbo.dim_turno t ON t.turno = d.turno
JOIN dbo.dim_tipo_usuario u ON u.tipo_usuario = d.tipo_usuario
WHERE d.rn = 1
  AND NOT EXISTS (SELECT 1 FROM dbo.hecho_interaccion h WHERE h.id_interaccion = d.id_interaccion);
GO

PRINT 'ETL completado: dimensiones y hecho_interaccion poblados desde dbo.c15_callcenter_v0.';
GO

-- ============================================================
-- 4. DATASET — KPI 1: Tasa de Recontacto en 7 Días (TR7D)
--    Solo registros consolidados (regla R-CAL-01)
-- ============================================================
IF OBJECT_ID('dbo.vw_kpi_recontacto_7d', 'V') IS NOT NULL DROP VIEW dbo.vw_kpi_recontacto_7d;
GO
CREATE VIEW dbo.vw_kpi_recontacto_7d AS
SELECT
    h.id_interaccion,
    h.fecha_contacto,
    dt.anio,
    dt.mes,
    dt.nombre_mes,
    ISNULL(c.canal, '(sin dato)')  AS canal,
    m.motivo_contacto,
    q.cola_servicio,
    t.turno,
    h.recontacto_7_dias
FROM dbo.hecho_interaccion h
JOIN dbo.dim_tiempo dt   ON dt.fecha = h.fecha_contacto
LEFT JOIN dbo.dim_canal c ON c.id_canal = h.id_canal
JOIN dbo.dim_motivo m    ON m.id_motivo = h.id_motivo
JOIN dbo.dim_cola q      ON q.id_cola = h.id_cola
JOIN dbo.dim_turno t     ON t.id_turno = h.id_turno
WHERE h.recontacto_7_dias IS NOT NULL;   -- R-CAL-01: excluye no consolidados
GO

-- ============================================================
-- 5. DATASET — KPI 2: Duración Promedio de Interacción (DPI)
-- ============================================================
IF OBJECT_ID('dbo.vw_kpi_duracion_promedio', 'V') IS NOT NULL DROP VIEW dbo.vw_kpi_duracion_promedio;
GO
CREATE VIEW dbo.vw_kpi_duracion_promedio AS
SELECT
    h.id_interaccion,
    h.fecha_contacto,
    dt.anio,
    dt.mes,
    dt.nombre_mes,
    ISNULL(c.canal, '(sin dato)')  AS canal,
    m.motivo_contacto,
    t.turno,
    h.duracion_seg
FROM dbo.hecho_interaccion h
JOIN dbo.dim_tiempo dt   ON dt.fecha = h.fecha_contacto
LEFT JOIN dbo.dim_canal c ON c.id_canal = h.id_canal
JOIN dbo.dim_motivo m    ON m.id_motivo = h.id_motivo
JOIN dbo.dim_turno t     ON t.id_turno = h.id_turno;
GO

PRINT 'Vistas de dataset creadas: dbo.vw_kpi_recontacto_7d, dbo.vw_kpi_duracion_promedio';
GO
