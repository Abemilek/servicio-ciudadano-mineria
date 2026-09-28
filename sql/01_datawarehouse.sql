-- ============================================================
-- SERVICIO CIUDADANO 1800 - DATA WAREHOUSE (Caso C15_CallCenter)
-- Integrador VIII / Minería de Datos
-- ============================================================

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'ServicioCiudadanoDW')
BEGIN
    CREATE DATABASE ServicioCiudadanoDW;
END
GO

USE ServicioCiudadanoDW;
GO

-- ============================================================
-- 1. STAGING (dataset v0 crudo, tal como llega de las 4 fuentes)
--    NOTA: aquí cae la carga que hace src/generar_semilla.py
-- ============================================================
IF OBJECT_ID('dbo.c15_callcenter_v0', 'U') IS NOT NULL DROP TABLE dbo.c15_callcenter_v0;
GO

CREATE TABLE dbo.c15_callcenter_v0 (
    id_interaccion       NVARCHAR(20)  NOT NULL,
    fecha_contacto       DATE          NOT NULL,
    canal                NVARCHAR(20)  NULL,        -- puede venir vacío (RG-03)
    turno                NVARCHAR(20)  NOT NULL,
    motivo_contacto      NVARCHAR(20)  NOT NULL,     -- puede venir sin normalizar (RG-02)
    cola_servicio        NVARCHAR(20)  NOT NULL,
    espera_seg           INT           NOT NULL,
    tipo_usuario         NVARCHAR(20)  NOT NULL,
    duracion_seg         INT           NOT NULL,
    transferencias       INT           NOT NULL,
    casos_previos_30d    INT           NOT NULL,
    recontacto_7_dias    TINYINT       NULL,         -- 1 / 0 / NULL = no consolidado (RG-01)
    sistema_origen       NVARCHAR(20)  NOT NULL,
    fecha_carga          DATE          NOT NULL,
    grabacion_autorizada NVARCHAR(3)   NOT NULL
);
GO

-- ============================================================
-- 2. DIMENSIONES
-- ============================================================
IF OBJECT_ID('dbo.dim_canal', 'U') IS NOT NULL DROP TABLE dbo.dim_canal;
GO
CREATE TABLE dbo.dim_canal (
    id_canal    INT IDENTITY(1,1) PRIMARY KEY,
    canal       NVARCHAR(20) NOT NULL UNIQUE
);
GO

IF OBJECT_ID('dbo.dim_motivo', 'U') IS NOT NULL DROP TABLE dbo.dim_motivo;
GO
CREATE TABLE dbo.dim_motivo (
    id_motivo       INT IDENTITY(1,1) PRIMARY KEY,
    motivo_contacto NVARCHAR(20) NOT NULL UNIQUE
);
GO

IF OBJECT_ID('dbo.dim_cola', 'U') IS NOT NULL DROP TABLE dbo.dim_cola;
GO
CREATE TABLE dbo.dim_cola (
    id_cola       INT IDENTITY(1,1) PRIMARY KEY,
    cola_servicio NVARCHAR(20) NOT NULL UNIQUE
);
GO

IF OBJECT_ID('dbo.dim_turno', 'U') IS NOT NULL DROP TABLE dbo.dim_turno;
GO
CREATE TABLE dbo.dim_turno (
    id_turno INT IDENTITY(1,1) PRIMARY KEY,
    turno    NVARCHAR(20) NOT NULL UNIQUE
);
GO

IF OBJECT_ID('dbo.dim_tipo_usuario', 'U') IS NOT NULL DROP TABLE dbo.dim_tipo_usuario;
GO
CREATE TABLE dbo.dim_tipo_usuario (
    id_tipo_usuario INT IDENTITY(1,1) PRIMARY KEY,
    tipo_usuario    NVARCHAR(20) NOT NULL UNIQUE
);
GO

IF OBJECT_ID('dbo.dim_tiempo', 'U') IS NOT NULL DROP TABLE dbo.dim_tiempo;
GO
CREATE TABLE dbo.dim_tiempo (
    fecha             DATE PRIMARY KEY,
    anio              INT NOT NULL,
    mes               INT NOT NULL,
    nombre_mes        NVARCHAR(20) NOT NULL,
    dia               INT NOT NULL,
    dia_semana        INT NOT NULL,
    nombre_dia_semana NVARCHAR(20) NOT NULL,
    trimestre         INT NOT NULL,
    es_fin_semana     BIT NOT NULL
);
GO

-- ============================================================
-- 3. TABLA DE HECHOS
-- ============================================================
IF OBJECT_ID('dbo.hecho_interaccion', 'U') IS NOT NULL DROP TABLE dbo.hecho_interaccion;
GO
CREATE TABLE dbo.hecho_interaccion (
    id_interaccion       NVARCHAR(20) PRIMARY KEY,
    fecha_contacto       DATE NOT NULL,
    id_canal             INT NULL,
    id_motivo            INT NOT NULL,
    id_cola              INT NOT NULL,
    id_turno             INT NOT NULL,
    id_tipo_usuario      INT NOT NULL,
    espera_seg           INT NOT NULL,
    duracion_seg         INT NOT NULL,
    transferencias       INT NOT NULL,
    casos_previos_30d    INT NOT NULL,
    recontacto_7_dias    TINYINT NULL,
    sistema_origen       NVARCHAR(20) NOT NULL,
    grabacion_autorizada NVARCHAR(3) NOT NULL,

    CONSTRAINT FK_hi_canal  FOREIGN KEY (id_canal)  REFERENCES dbo.dim_canal(id_canal),
    CONSTRAINT FK_hi_motivo FOREIGN KEY (id_motivo) REFERENCES dbo.dim_motivo(id_motivo),
    CONSTRAINT FK_hi_cola   FOREIGN KEY (id_cola)   REFERENCES dbo.dim_cola(id_cola),
    CONSTRAINT FK_hi_turno  FOREIGN KEY (id_turno)  REFERENCES dbo.dim_turno(id_turno),
    CONSTRAINT FK_hi_tipo   FOREIGN KEY (id_tipo_usuario) REFERENCES dbo.dim_tipo_usuario(id_tipo_usuario),
    CONSTRAINT FK_hi_fecha  FOREIGN KEY (fecha_contacto)  REFERENCES dbo.dim_tiempo(fecha)
);
GO

CREATE INDEX IX_hi_canal  ON dbo.hecho_interaccion(id_canal);
CREATE INDEX IX_hi_motivo ON dbo.hecho_interaccion(id_motivo);
CREATE INDEX IX_hi_cola   ON dbo.hecho_interaccion(id_cola);
CREATE INDEX IX_hi_fecha  ON dbo.hecho_interaccion(fecha_contacto);
GO

PRINT 'Data Warehouse ServicioCiudadanoDW: estructura creada. Ejecuta ahora src/generar_semilla.py para poblar dbo.c15_callcenter_v0, y luego 02_poblar_dw.sql.';
GO
