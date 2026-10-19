-- =====================================================================================
-- Esquema de base de datos: Veterinaria - Red de Clínicas y Derivación de Laboratorio
-- Motor: SQLite 3.37 o superior (se utilizan tablas STRICT).
-- =====================================================================================
--
-- Convenciones:
--   * Todas las tablas son STRICT: SQLite rechaza valores de un tipo distinto al declarado
--     (por ejemplo, el texto 'abc' en una columna INTEGER). Sin STRICT, SQLite lo aceptaría.
--   * Claves primarias: id INTEGER PRIMARY KEY AUTOINCREMENT (los id nunca se reutilizan,
--     algo deseable para la trazabilidad).
--   * Fechas y horas: TEXT en formato ISO 8601.
--       - Fecha y hora: 'AAAA-MM-DD HH:MM:SS'  (validado con strftime)
--       - Solo fecha:   'AAAA-MM-DD'           (validado con date)
--     El formato ISO permite comparar fechas como texto y ordenar cronológicamente.
--     IMPORTANTE: los CHECK de formato usan IS y no =. Ante un texto inválido,
--     date('19/10/2026') devuelve NULL; con "=" la comparación daría NULL y SQLite
--     considera que un CHECK con resultado NULL se cumple. "IS" sí devuelve falso.
--   * Las restricciones CHECK tienen nombre (ck_<tabla>_<regla>) para que el módulo
--     traductor_errores.py pueda convertir el error en un mensaje claro para el usuario.
--   * Booleanos: INTEGER con valores 0 / 1.
--   * Las claves foráneas se validan porque la conexión ejecuta PRAGMA foreign_keys = ON.
--   * Todas las sentencias usan IF NOT EXISTS: el script puede ejecutarse varias veces.
-- =====================================================================================


-- =====================================================================================
-- 1. CATÁLOGOS PARAMÉTRICOS
--    Evitan texto libre ("Sangre", "sangre", "SANGRE") y centralizan valores de referencia.
-- =====================================================================================

CREATE TABLE IF NOT EXISTS catalogo_especies (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT    NOT NULL UNIQUE
) STRICT;

CREATE TABLE IF NOT EXISTS catalogo_tipos_muestra (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo  TEXT    NOT NULL UNIQUE,               -- Ej.: 'SANGRE', 'ORINA'
    nombre  TEXT    NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS catalogo_tipos_estudio (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT    NOT NULL UNIQUE,           -- Ej.: 'HEMOGRAMA'
    nombre      TEXT    NOT NULL,
    costo_base  REAL    NOT NULL,
    CONSTRAINT ck_tipos_estudio_costo CHECK (costo_base >= 0)
) STRICT;

CREATE TABLE IF NOT EXISTS catalogo_vacunas (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre                     TEXT    NOT NULL,
    especie_id                 INTEGER NOT NULL REFERENCES catalogo_especies(id),
    es_obligatoria             INTEGER NOT NULL,
    -- Cada cuántos meses se debe reforzar. NULL = dosis única.
    -- Permite calcular las vacunas pendientes o vencidas de cada mascota.
    frecuencia_refuerzo_meses  INTEGER,
    CONSTRAINT uq_vacunas_nombre_especie UNIQUE (nombre, especie_id),
    CONSTRAINT ck_vacunas_obligatoria CHECK (es_obligatoria IN (0, 1)),
    CONSTRAINT ck_vacunas_frecuencia CHECK (frecuencia_refuerzo_meses IS NULL
                                            OR frecuencia_refuerzo_meses > 0)
) STRICT;


-- =====================================================================================
-- 2. ENTIDADES DE LA RED (clínicas, profesionales, laboratorios y transporte)
-- =====================================================================================

CREATE TABLE IF NOT EXISTS clinicas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre     TEXT    NOT NULL UNIQUE,
    direccion  TEXT,
    telefono   TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS veterinarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    matricula     TEXT    NOT NULL UNIQUE,
    nombre        TEXT    NOT NULL,
    apellido      TEXT    NOT NULL,
    especialidad  TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS laboratorios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre     TEXT    NOT NULL UNIQUE,
    direccion  TEXT,
    telefono   TEXT
) STRICT;

-- Bioquímicos / profesionales que firman los resultados de análisis.
CREATE TABLE IF NOT EXISTS profesionales_laboratorio (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    matricula       TEXT    NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    apellido        TEXT    NOT NULL,
    laboratorio_id  INTEGER NOT NULL REFERENCES laboratorios(id)
) STRICT;

CREATE TABLE IF NOT EXISTS transportistas (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT    NOT NULL,
    cuit_dni          TEXT    NOT NULL UNIQUE,
    vehiculo_patente  TEXT,
    telefono          TEXT
) STRICT;


-- =====================================================================================
-- 3. CLIENTES, MASCOTAS E HISTORIA CLÍNICA     (Procesos 1 y 2)
-- =====================================================================================

CREATE TABLE IF NOT EXISTS clientes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    dni        TEXT    NOT NULL UNIQUE,
    nombre     TEXT    NOT NULL,
    apellido   TEXT    NOT NULL,
    telefono   TEXT    NOT NULL,
    email      TEXT,
    direccion  TEXT,
    -- DNI: solo dígitos, entre 7 y 8 caracteres.
    CONSTRAINT ck_clientes_dni CHECK (dni NOT GLOB '*[^0-9]*'
                                      AND length(dni) BETWEEN 7 AND 8),
    CONSTRAINT ck_clientes_nombre CHECK (length(trim(nombre)) > 0),
    CONSTRAINT ck_clientes_apellido CHECK (length(trim(apellido)) > 0),
    CONSTRAINT ck_clientes_email CHECK (email IS NULL OR email LIKE '%_@_%._%')
) STRICT;

CREATE TABLE IF NOT EXISTS mascotas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT    NOT NULL,
    especie_id  INTEGER NOT NULL REFERENCES catalogo_especies(id),
    raza        TEXT,
    edad        INTEGER NOT NULL,                  -- En años cumplidos.
    sexo        TEXT    NOT NULL,
    -- Validación obligatoria: toda mascota debe tener un responsable asociado.
    cliente_id  INTEGER NOT NULL REFERENCES clientes(id),
    CONSTRAINT ck_mascotas_nombre CHECK (length(trim(nombre)) > 0),
    CONSTRAINT ck_mascotas_edad CHECK (edad >= 0),
    CONSTRAINT ck_mascotas_sexo CHECK (sexo IN ('Macho', 'Hembra'))
) STRICT;

-- Cabecera de la historia clínica (relación 1 a 1 con la mascota).
-- Las "entradas" de la historia son las consultas, tratamientos y vacunas registradas.
CREATE TABLE IF NOT EXISTS historias_clinicas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mascota_id      INTEGER NOT NULL UNIQUE REFERENCES mascotas(id),
    fecha_apertura  TEXT    NOT NULL,
    antecedentes    TEXT,
    alergias        TEXT,
    CONSTRAINT ck_historias_fecha_apertura_formato CHECK (fecha_apertura IS date(fecha_apertura))
) STRICT;


-- =====================================================================================
-- 4. ATENCIÓN MÉDICA Y ÓRDENES DE DERIVACIÓN    (Proceso 3)
-- =====================================================================================

CREATE TABLE IF NOT EXISTS consultas_medicas (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    mascota_id         INTEGER NOT NULL REFERENCES mascotas(id),
    clinica_id         INTEGER NOT NULL REFERENCES clinicas(id),
    veterinario_id     INTEGER NOT NULL REFERENCES veterinarios(id),
    fecha_hora_inicio  TEXT    NOT NULL,
    duracion_minutos   INTEGER NOT NULL DEFAULT 30,
    motivo             TEXT    NOT NULL,
    diagnostico        TEXT,
    costo_consulta     REAL    NOT NULL DEFAULT 0.0,
    -- Red de seguridad: impide dos consultas del mismo veterinario con igual inicio.
    -- La superposición por RANGO horario [inicio, inicio + duración) se valida en la
    -- capa de servicios, porque SQL no maneja rangos de tiempo de forma nativa.
    CONSTRAINT uq_consultas_veterinario_inicio UNIQUE (veterinario_id, fecha_hora_inicio),
    CONSTRAINT ck_consultas_fecha_hora_inicio_formato
        CHECK (fecha_hora_inicio IS strftime('%Y-%m-%d %H:%M:%S', fecha_hora_inicio)),
    CONSTRAINT ck_consultas_duracion CHECK (duracion_minutos > 0),
    CONSTRAINT ck_consultas_costo CHECK (costo_consulta >= 0)
) STRICT;

-- Tratamientos indicados en una consulta (necesario para el reporte
-- "Tratamientos aplicados y vacunas pendientes").
CREATE TABLE IF NOT EXISTS tratamientos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    consulta_id   INTEGER NOT NULL REFERENCES consultas_medicas(id),
    descripcion   TEXT    NOT NULL,
    medicamento   TEXT,
    dosis         TEXT,
    duracion_dias INTEGER,
    CONSTRAINT ck_tratamientos_duracion CHECK (duracion_dias IS NULL OR duracion_dias > 0)
) STRICT;

CREATE TABLE IF NOT EXISTS vacunas_aplicadas (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    mascota_id        INTEGER NOT NULL REFERENCES mascotas(id),
    vacuna_id         INTEGER NOT NULL REFERENCES catalogo_vacunas(id),
    -- Consulta en la que se aplicó. NULL si se registra un antecedente externo
    -- (por ejemplo, una vacuna aplicada en otra veterinaria).
    consulta_id       INTEGER REFERENCES consultas_medicas(id),
    fecha_aplicacion  TEXT    NOT NULL,
    CONSTRAINT ck_vacunas_aplicadas_fecha_aplicacion_formato
        CHECK (fecha_aplicacion IS date(fecha_aplicacion))
) STRICT;

-- Una consulta puede emitir varias órdenes (una por tipo de estudio solicitado).
CREATE TABLE IF NOT EXISTS ordenes_derivacion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    consulta_id         INTEGER NOT NULL REFERENCES consultas_medicas(id),
    tipo_estudio_id     INTEGER NOT NULL REFERENCES catalogo_tipos_estudio(id),
    indicaciones        TEXT,
    prioridad           TEXT    NOT NULL DEFAULT 'Normal',
    fecha_hora_emision  TEXT    NOT NULL,
    CONSTRAINT ck_ordenes_prioridad CHECK (prioridad IN ('Normal', 'Urgente')),
    CONSTRAINT ck_ordenes_fecha_hora_emision_formato
        CHECK (fecha_hora_emision IS strftime('%Y-%m-%d %H:%M:%S', fecha_hora_emision))
) STRICT;


-- =====================================================================================
-- 5. LOGÍSTICA: CONSERVADORAS, PRECINTOS Y REMITOS     (Proceso 4)
-- =====================================================================================

CREATE TABLE IF NOT EXISTS conservadoras (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo            TEXT    NOT NULL UNIQUE,
    capacidad_maxima  INTEGER NOT NULL,
    temperatura_min   REAL,                        -- Grados Celsius.
    temperatura_max   REAL,
    disponible        INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_conservadoras_capacidad CHECK (capacidad_maxima > 0),
    CONSTRAINT ck_conservadoras_temperaturas CHECK (temperatura_min IS NULL
                                                    OR temperatura_max IS NULL
                                                    OR temperatura_min <= temperatura_max),
    CONSTRAINT ck_conservadoras_disponible CHECK (disponible IN (0, 1))
) STRICT;

CREATE TABLE IF NOT EXISTS precintos_sanitarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_serie  TEXT    NOT NULL UNIQUE,
    -- Fuente única de verdad del estado del precinto: se actualiza en la recepción.
    estado        TEXT    NOT NULL DEFAULT 'Intacto',
    CONSTRAINT ck_precintos_estado CHECK (estado IN ('Intacto', 'Roto', 'Violado'))
) STRICT;

-- Ciclo de vida del remito biológico:
--   EnPreparacion -> Precintado -> EnTransito -> Recibido
--                                            \-> Rechazado   (precinto Roto o Violado)
CREATE TABLE IF NOT EXISTS remitos_biologicos (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_remito           TEXT    NOT NULL UNIQUE,
    -- Un remito agrupa muestras de UNA sola clínica (regla validada en servicios).
    clinica_origen_id       INTEGER NOT NULL REFERENCES clinicas(id),
    laboratorio_destino_id  INTEGER NOT NULL REFERENCES laboratorios(id),
    conservadora_id         INTEGER NOT NULL REFERENCES conservadoras(id),
    -- NULL mientras el remito está en preparación; se asigna al precintar.
    precinto_id             INTEGER UNIQUE REFERENCES precintos_sanitarios(id),
    estado                  TEXT    NOT NULL DEFAULT 'EnPreparacion',
    fecha_hora_creacion     TEXT    NOT NULL,
    CONSTRAINT ck_remitos_estado CHECK (estado IN ('EnPreparacion', 'Precintado',
                                                   'EnTransito', 'Recibido', 'Rechazado')),
    -- Fuera del estado 'EnPreparacion' el remito debe tener precinto.
    CONSTRAINT ck_remitos_precinto_requerido CHECK (estado = 'EnPreparacion'
                                                    OR precinto_id IS NOT NULL),
    CONSTRAINT ck_remitos_fecha_hora_creacion_formato
        CHECK (fecha_hora_creacion IS strftime('%Y-%m-%d %H:%M:%S', fecha_hora_creacion))
) STRICT;

-- Trazabilidad inmutable del remito (solo INSERT; ver triggers al final).
CREATE TABLE IF NOT EXISTS historial_estados_remito (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    remito_id        INTEGER NOT NULL REFERENCES remitos_biologicos(id),
    estado_anterior  TEXT,                         -- NULL en el registro de creación.
    estado_nuevo     TEXT    NOT NULL,
    fecha_hora       TEXT    NOT NULL,
    observacion      TEXT,
    CONSTRAINT ck_historial_remito_fecha_hora_formato
        CHECK (fecha_hora IS strftime('%Y-%m-%d %H:%M:%S', fecha_hora))
) STRICT;


-- =====================================================================================
-- 6. MUESTRAS BIOLÓGICAS Y SU TRAZABILIDAD     (Núcleo del sistema)
-- =====================================================================================

-- Ciclo de vida de la muestra (implementado con el patrón State):
--   Extraida -> Empaquetada -> EnTransito -> Recibida -> Analizada
--                                       \-> Rechazada   (precinto Roto o Violado)
CREATE TABLE IF NOT EXISTS muestras_biologicas (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_muestra         TEXT    NOT NULL UNIQUE,
    orden_id               INTEGER NOT NULL REFERENCES ordenes_derivacion(id),
    tipo_muestra_id        INTEGER NOT NULL REFERENCES catalogo_tipos_muestra(id),
    fecha_hora_extraccion  TEXT    NOT NULL,
    remito_id              INTEGER REFERENCES remitos_biologicos(id),
    -- Dato desnormalizado a propósito (evita JOIN + MAX(fecha) en cada consulta).
    -- Se modifica SIEMPRE en la misma transacción que inserta en historial_estados_muestra.
    estado_actual          TEXT    NOT NULL DEFAULT 'Extraida',
    motivo_rechazo         TEXT,
    CONSTRAINT ck_muestras_estado CHECK (estado_actual IN ('Extraida', 'Empaquetada',
                                                           'EnTransito', 'Recibida',
                                                           'Analizada', 'Rechazada')),
    -- Desde 'Empaquetada' en adelante la muestra debe pertenecer a un remito.
    CONSTRAINT ck_muestras_remito_requerido CHECK (estado_actual = 'Extraida'
                                                   OR remito_id IS NOT NULL),
    -- Una muestra rechazada siempre documenta el motivo.
    CONSTRAINT ck_muestras_motivo_rechazo CHECK (estado_actual <> 'Rechazada'
                                                 OR motivo_rechazo IS NOT NULL),
    CONSTRAINT ck_muestras_fecha_hora_extraccion_formato
        CHECK (fecha_hora_extraccion IS strftime('%Y-%m-%d %H:%M:%S', fecha_hora_extraccion))
) STRICT;

-- Trazabilidad inmutable de la muestra (solo INSERT; ver triggers al final).
CREATE TABLE IF NOT EXISTS historial_estados_muestra (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    muestra_id       INTEGER NOT NULL REFERENCES muestras_biologicas(id),
    estado_anterior  TEXT,                         -- NULL en el registro de extracción.
    estado_nuevo     TEXT    NOT NULL,
    fecha_hora       TEXT    NOT NULL,
    observacion      TEXT,
    CONSTRAINT ck_historial_muestra_fecha_hora_formato
        CHECK (fecha_hora IS strftime('%Y-%m-%d %H:%M:%S', fecha_hora))
) STRICT;


-- =====================================================================================
-- 7. CADENA DE ENVÍO Y RECEPCIÓN     (Procesos 5 y 6)
-- =====================================================================================

CREATE TABLE IF NOT EXISTS envios_laboratorio (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    remito_id                INTEGER NOT NULL UNIQUE REFERENCES remitos_biologicos(id),
    transportista_id         INTEGER NOT NULL REFERENCES transportistas(id),
    fecha_hora_despacho      TEXT    NOT NULL,
    fecha_hora_recepcion     TEXT,                 -- NULL mientras está en tránsito.
    observaciones_recepcion  TEXT,
    -- El estado del precinto al llegar se registra en precintos_sanitarios.estado.
    CONSTRAINT ck_envios_fecha_hora_despacho_formato
        CHECK (fecha_hora_despacho IS strftime('%Y-%m-%d %H:%M:%S', fecha_hora_despacho)),
    CONSTRAINT ck_envios_fecha_hora_recepcion_formato
        CHECK (fecha_hora_recepcion IS strftime('%Y-%m-%d %H:%M:%S', fecha_hora_recepcion)),
    CONSTRAINT ck_envios_recepcion_posterior CHECK (fecha_hora_recepcion IS NULL
                                                    OR fecha_hora_recepcion >= fecha_hora_despacho)
) STRICT;


-- =====================================================================================
-- 8. RESULTADOS Y FACTURACIÓN     (Proceso 7)
-- =====================================================================================

CREATE TABLE IF NOT EXISTS resultados_analisis (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    muestra_id                  INTEGER NOT NULL UNIQUE REFERENCES muestras_biologicas(id),
    profesional_laboratorio_id  INTEGER NOT NULL REFERENCES profesionales_laboratorio(id),
    valores_medidos             TEXT    NOT NULL,
    conclusion                  TEXT    NOT NULL,
    costo_analisis              REAL    NOT NULL,
    fecha_hora_analisis         TEXT    NOT NULL,
    CONSTRAINT ck_resultados_costo CHECK (costo_analisis >= 0),
    CONSTRAINT ck_resultados_fecha_hora_analisis_formato
        CHECK (fecha_hora_analisis IS strftime('%Y-%m-%d %H:%M:%S', fecha_hora_analisis))
) STRICT;

-- Cabecera del comprobante. La clínica se deduce por consulta -> clínica.
CREATE TABLE IF NOT EXISTS comprobantes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_comprobante  TEXT    NOT NULL UNIQUE,
    consulta_id         INTEGER NOT NULL REFERENCES consultas_medicas(id),
    estrategia_tarifa   TEXT    NOT NULL,          -- Nombre de la estrategia (patrón Strategy).
    -- Suma de los detalles; se calcula y guarda en la misma transacción que los detalles.
    monto_total         REAL    NOT NULL,
    fecha_hora_emision  TEXT    NOT NULL,
    CONSTRAINT ck_comprobantes_monto_total CHECK (monto_total >= 0),
    CONSTRAINT ck_comprobantes_fecha_hora_emision_formato
        CHECK (fecha_hora_emision IS strftime('%Y-%m-%d %H:%M:%S', fecha_hora_emision))
) STRICT;

-- Detalle extensible: agregar un nuevo concepto no requiere modificar la estructura.
CREATE TABLE IF NOT EXISTS detalles_comprobante (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    comprobante_id  INTEGER NOT NULL REFERENCES comprobantes(id),
    tipo_concepto   TEXT    NOT NULL,              -- Permite desglosar la facturación.
    concepto        TEXT    NOT NULL,              -- Descripción legible del ítem.
    monto           REAL    NOT NULL,
    CONSTRAINT ck_detalles_tipo_concepto CHECK (tipo_concepto IN ('Consulta', 'Laboratorio',
                                                                  'Vacuna', 'Tratamiento',
                                                                  'Recargo', 'Bonificacion')),
    -- Las bonificaciones se registran en negativo; el resto de los conceptos, en positivo.
    CONSTRAINT ck_detalles_signo_monto CHECK ((tipo_concepto = 'Bonificacion' AND monto <= 0)
                                              OR (tipo_concepto <> 'Bonificacion' AND monto >= 0))
) STRICT;


-- =====================================================================================
-- 9. ÍNDICES (aceleran búsquedas por claves foráneas y los reportes)
--    Las columnas UNIQUE ya tienen índice implícito.
-- =====================================================================================

CREATE INDEX IF NOT EXISTS ix_mascotas_cliente           ON mascotas (cliente_id);
CREATE INDEX IF NOT EXISTS ix_consultas_mascota          ON consultas_medicas (mascota_id);
CREATE INDEX IF NOT EXISTS ix_consultas_clinica          ON consultas_medicas (clinica_id);
CREATE INDEX IF NOT EXISTS ix_tratamientos_consulta      ON tratamientos (consulta_id);
CREATE INDEX IF NOT EXISTS ix_vacunas_aplicadas_mascota  ON vacunas_aplicadas (mascota_id);
CREATE INDEX IF NOT EXISTS ix_ordenes_consulta           ON ordenes_derivacion (consulta_id);
CREATE INDEX IF NOT EXISTS ix_muestras_orden             ON muestras_biologicas (orden_id);
CREATE INDEX IF NOT EXISTS ix_muestras_remito            ON muestras_biologicas (remito_id);
CREATE INDEX IF NOT EXISTS ix_muestras_estado            ON muestras_biologicas (estado_actual);
CREATE INDEX IF NOT EXISTS ix_historial_muestra          ON historial_estados_muestra (muestra_id);
CREATE INDEX IF NOT EXISTS ix_historial_remito           ON historial_estados_remito (remito_id);
CREATE INDEX IF NOT EXISTS ix_remitos_estado             ON remitos_biologicos (estado);
CREATE INDEX IF NOT EXISTS ix_comprobantes_consulta      ON comprobantes (consulta_id);
CREATE INDEX IF NOT EXISTS ix_detalles_comprobante       ON detalles_comprobante (comprobante_id);


-- =====================================================================================
-- 10. TRIGGERS DE INMUTABILIDAD
--     Validación obligatoria: "mantener la trazabilidad inmutable de estados".
--     El motor rechaza cualquier UPDATE o DELETE sobre los historiales, aun si un error
--     de programación lo intentara. RAISE(ABORT) llega a Python como IntegrityError.
-- =====================================================================================

CREATE TRIGGER IF NOT EXISTS trg_historial_muestra_sin_modificar
BEFORE UPDATE ON historial_estados_muestra
BEGIN
    SELECT RAISE(ABORT, 'El historial de estados de la muestra es inmutable: no puede modificarse.');
END;

CREATE TRIGGER IF NOT EXISTS trg_historial_muestra_sin_eliminar
BEFORE DELETE ON historial_estados_muestra
BEGIN
    SELECT RAISE(ABORT, 'El historial de estados de la muestra es inmutable: no puede eliminarse.');
END;

CREATE TRIGGER IF NOT EXISTS trg_historial_remito_sin_modificar
BEFORE UPDATE ON historial_estados_remito
BEGIN
    SELECT RAISE(ABORT, 'El historial de estados del remito es inmutable: no puede modificarse.');
END;

CREATE TRIGGER IF NOT EXISTS trg_historial_remito_sin_eliminar
BEFORE DELETE ON historial_estados_remito
BEGIN
    SELECT RAISE(ABORT, 'El historial de estados del remito es inmutable: no puede eliminarse.');
END;
