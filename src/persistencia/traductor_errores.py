"""
Traducción de errores de sqlite3 a excepciones del sistema con mensajes amigables.

¿Por qué existe este módulo?
    El esquema protege fuertemente los datos (UNIQUE, CHECK, NOT NULL, FOREIGN KEY y
    triggers). Cuando el motor rechaza una operación, sqlite3 lanza un ``IntegrityError``
    con un texto técnico en inglés, por ejemplo:

        UNIQUE constraint failed: clientes.dni
        CHECK constraint failed: ck_mascotas_edad

    Este módulo interpreta ese texto y devuelve un ``ErrorIntegridadDatos`` con un mensaje
    en español apto para mostrar en la interfaz gráfica.

Para agregar un mensaje nuevo basta con sumar una entrada al diccionario
``MENSAJES_POR_RESTRICCION`` usando como clave lo que SQLite informa después de los dos
puntos (nombre de la restricción CHECK o "tabla.columna").
"""

from __future__ import annotations

import re
import sqlite3

from src.dominio.excepciones import ErrorIntegridadDatos, ErrorPersistencia, ErrorVeterinaria

# Mensajes específicos, indexados por la restricción que informa SQLite.
MENSAJES_POR_RESTRICCION: dict[str, str] = {
    # ----- UNIQUE (clave: "tabla.columna" o lista de columnas) -----
    "clientes.dni": "Ya existe un cliente registrado con el DNI ingresado.",
    "veterinarios.matricula": "Ya existe un veterinario con esa matrícula.",
    "profesionales_laboratorio.matricula": "Ya existe un profesional de laboratorio con esa matrícula.",
    "transportistas.cuit_dni": "Ya existe un transportista con ese CUIT/DNI.",
    "clinicas.nombre": "Ya existe una clínica con ese nombre.",
    "laboratorios.nombre": "Ya existe un laboratorio con ese nombre.",
    "historias_clinicas.mascota_id": "La mascota ya posee una historia clínica.",
    "consultas_medicas.veterinario_id, consultas_medicas.fecha_hora_inicio":
        "El veterinario ya tiene una consulta que comienza en ese mismo horario.",
    "conservadoras.codigo": "Ya existe una conservadora con ese código.",
    "precintos_sanitarios.numero_serie": "Ya existe un precinto con ese número de serie.",
    "remitos_biologicos.numero_remito": "Ya existe un remito con ese número.",
    "remitos_biologicos.precinto_id": "El precinto ya fue asignado a otro remito.",
    "muestras_biologicas.codigo_muestra": "Ya existe una muestra con ese código.",
    "envios_laboratorio.remito_id": "El remito ya tiene un envío registrado.",
    "resultados_analisis.muestra_id": "La muestra ya tiene un resultado de análisis cargado.",
    "comprobantes.numero_comprobante": "Ya existe un comprobante con ese número.",

    # ----- NOT NULL (clave: "tabla.columna") -----
    "mascotas.cliente_id": "Toda mascota debe tener un responsable (cliente) asociado.",

    # ----- CHECK (clave: nombre de la restricción definido en esquema.sql) -----
    "ck_clientes_dni": "El DNI debe contener solo números (7 u 8 dígitos).",
    "ck_clientes_nombre": "El nombre del cliente es obligatorio.",
    "ck_clientes_apellido": "El apellido del cliente es obligatorio.",
    "ck_clientes_email": "El correo electrónico no tiene un formato válido.",
    "ck_mascotas_nombre": "El nombre de la mascota es obligatorio.",
    "ck_mascotas_edad": "La edad de la mascota no puede ser negativa.",
    "ck_mascotas_sexo": "El sexo de la mascota debe ser 'Macho' o 'Hembra'.",
    "ck_consultas_duracion": "La duración de la consulta debe ser mayor a cero minutos.",
    "ck_consultas_costo": "El costo de la consulta no puede ser negativo.",
    "ck_tratamientos_duracion": "La duración del tratamiento debe ser mayor a cero días.",
    "ck_ordenes_prioridad": "La prioridad de la orden debe ser 'Normal' o 'Urgente'.",
    "ck_tipos_estudio_costo": "El costo base del estudio no puede ser negativo.",
    "ck_conservadoras_capacidad": "La capacidad de la conservadora debe ser mayor a cero.",
    "ck_conservadoras_temperaturas":
        "La temperatura mínima de la conservadora no puede superar a la máxima.",
    "ck_precintos_estado": "El estado del precinto debe ser 'Intacto', 'Roto' o 'Violado'.",
    "ck_remitos_estado": "El estado indicado para el remito no es válido.",
    "ck_remitos_precinto_requerido":
        "El remito debe tener un precinto sanitario asignado para avanzar de estado.",
    "ck_muestras_estado": "El estado indicado para la muestra no es válido.",
    "ck_muestras_remito_requerido":
        "La muestra debe estar asignada a un remito para avanzar de estado.",
    "ck_muestras_motivo_rechazo": "Debe indicarse el motivo de rechazo de la muestra.",
    "ck_envios_recepcion_posterior":
        "La fecha de recepción no puede ser anterior a la fecha de despacho.",
    "ck_resultados_costo": "El costo del análisis no puede ser negativo.",
    "ck_comprobantes_monto_total": "El monto total del comprobante no puede ser negativo.",
    "ck_detalles_tipo_concepto": "El tipo de concepto del comprobante no es válido.",
    "ck_detalles_signo_monto":
        "Las bonificaciones deben ser montos negativos y el resto de los conceptos, positivos.",
}

# Mensajes genéricos cuando la restricción no figura en el diccionario anterior.
MENSAJES_GENERICOS: dict[str, str] = {
    "UNIQUE": "Ya existe un registro con esos datos.",
    "NOT NULL": "Falta completar un dato obligatorio.",
    "CHECK": "Uno de los valores ingresados no cumple las reglas de validación.",
    "FOREIGN KEY": (
        "La operación hace referencia a un registro inexistente, o intenta eliminar "
        "un registro que está siendo utilizado por otros datos."
    ),
}

# Sufijo usado en esquema.sql para las restricciones de formato de fecha.
SUFIJO_RESTRICCION_FORMATO = "_formato"
MENSAJE_FORMATO_FECHA = (
    "La fecha u hora ingresada no tiene un formato válido "
    "(se espera AAAA-MM-DD o AAAA-MM-DD HH:MM:SS)."
)

# Tablas STRICT: SQLite informa "cannot store <TIPO> value in <TIPO> column <tabla.columna>".
_PREFIJO_ERROR_TIPO_DATO = "cannot store"
MENSAJE_TIPO_DATO = "Uno de los valores ingresados no tiene el tipo de dato esperado."

# Ejemplos que reconoce: "UNIQUE constraint failed: clientes.dni"
#                        "FOREIGN KEY constraint failed"
_PATRON_RESTRICCION = re.compile(
    r"^(?P<tipo>UNIQUE|CHECK|NOT NULL|FOREIGN KEY) constraint failed(?::\s*(?P<detalle>.+))?$"
)


def traducir_error_integridad(error: sqlite3.IntegrityError) -> ErrorIntegridadDatos:
    """
    Convierte un ``sqlite3.IntegrityError`` en un ``ErrorIntegridadDatos`` amigable.

    Args:
        error: Excepción original lanzada por sqlite3.

    Returns:
        Excepción del sistema con un mensaje en español y los datos técnicos conservados.
    """
    texto_original = str(error)

    # Tablas STRICT: "cannot store TEXT value in INTEGER column mascotas.edad".
    if texto_original.startswith(_PREFIJO_ERROR_TIPO_DATO):
        return ErrorIntegridadDatos(
            mensaje=MENSAJE_TIPO_DATO,
            tipo_restriccion="TIPO_DATO",
            restriccion=texto_original.rsplit(" ", 1)[-1],
            detalle_tecnico=texto_original,
        )

    coincidencia = _PATRON_RESTRICCION.match(texto_original)

    # Si no responde a ningún patrón conocido, proviene de un trigger con RAISE(ABORT, ...).
    # Esos mensajes se escriben en español en esquema.sql, así que se muestran tal cual.
    if coincidencia is None:
        return ErrorIntegridadDatos(
            mensaje=texto_original,
            tipo_restriccion="TRIGGER",
            detalle_tecnico=texto_original,
        )

    tipo = coincidencia.group("tipo")
    restriccion = coincidencia.group("detalle")

    if restriccion in MENSAJES_POR_RESTRICCION:
        mensaje = MENSAJES_POR_RESTRICCION[restriccion]
    elif tipo == "CHECK" and restriccion and restriccion.endswith(SUFIJO_RESTRICCION_FORMATO):
        mensaje = MENSAJE_FORMATO_FECHA
    else:
        mensaje = MENSAJES_GENERICOS[tipo]

    return ErrorIntegridadDatos(
        mensaje=mensaje,
        tipo_restriccion=tipo,
        restriccion=restriccion,
        detalle_tecnico=texto_original,
    )


def traducir_error_sqlite(error: sqlite3.Error) -> ErrorVeterinaria:
    """
    Convierte cualquier error de sqlite3 en una excepción del sistema.

    - ``IntegrityError`` (incluye los errores de tipo de las tablas STRICT):
      se delega en ``traducir_error_integridad``.
    - Cualquier otro error (archivo inaccesible, SQL mal formado, etc.):
      ``ErrorPersistencia`` genérico, conservando el detalle técnico.

    Args:
        error: Excepción original lanzada por sqlite3.

    Returns:
        Excepción del sistema lista para ser lanzada con ``raise ... from error``.
    """
    if isinstance(error, sqlite3.IntegrityError):
        return traducir_error_integridad(error)

    return ErrorPersistencia(
        "Ocurrió un error al acceder a la base de datos.",
        detalle_tecnico=str(error),
    )
