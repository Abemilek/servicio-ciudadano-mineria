-- ============================================================
-- SERVICIO CIUDADANO 1800 - DATASET PARA MINERÍA (MODELO)
-- Integrador VIII / Minería de Datos
-- A diferencia de vw_kpi_recontacto_7d (pensada solo para medir
-- el KPI 1), esta vista agrega TODAS las variables explicativas
-- disponibles en hecho_interaccion, para entrenar un modelo de
-- clasificación sobre recontacto_7_dias.
-- Ejecutar DESPUÉS de sql/02_poblar_dw_y_datasets.sql
-- ============================================================

USE ServicioCiudadanoDW;
GO

IF OBJECT_ID('dbo.vw_dataset_modelo_recontacto', 'V') IS NOT NULL
    DROP VIEW dbo.vw_dataset_modelo_recontacto;
GO

CREATE VIEW dbo.vw_dataset_modelo_recontacto AS
SELECT
    h.id_interaccion,
    ISNULL(c.canal, '(sin dato)')  AS canal,
    m.motivo_contacto,
    q.cola_servicio,
    t.turno,
    u.tipo_usuario,
    h.espera_seg,
    h.duracion_seg,
    h.transferencias,
    h.casos_previos_30d,
    dt.es_fin_semana,
    h.recontacto_7_dias                -- variable de resultado (target)
FROM dbo.hecho_interaccion h
JOIN dbo.dim_tiempo        dt ON dt.fecha = h.fecha_contacto
LEFT JOIN dbo.dim_canal     c ON c.id_canal = h.id_canal
JOIN dbo.dim_motivo         m ON m.id_motivo = h.id_motivo
JOIN dbo.dim_cola           q ON q.id_cola = h.id_cola
JOIN dbo.dim_turno          t ON t.id_turno = h.id_turno
JOIN dbo.dim_tipo_usuario   u ON u.id_tipo_usuario = h.id_tipo_usuario
WHERE h.recontacto_7_dias IS NOT NULL;   -- R-CAL-01: un modelo supervisado necesita el target consolidado
GO

PRINT 'Vista creada: dbo.vw_dataset_modelo_recontacto (dataset listo para el modelo de minería)';
GO
