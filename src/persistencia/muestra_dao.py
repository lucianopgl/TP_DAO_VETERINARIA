"""
Capa de Persistencia: MuestraDAO
================================

Núcleo de Trazabilidad e Inmutabilidad del Sistema.
Garantiza que toda actualización de estado en `muestras_biologicas` se guarde
de forma estrictamente ATÓMICA junto con el registro inmutable en `historial_estados_muestra`.
"""

from __future__ import annotations

import sqlite3
from src.dominio.muestra_biologica import (
    OBSERVACION_EXTRACCION_INICIAL,
    MuestraBiologica,
    RegistroTrazabilidad,
)
from src.persistencia.dao_base import DAOBase


class MuestraDAO(DAOBase):
    """Objeto de Acceso a Datos para `muestras_biologicas` y su historial inmutable."""

    def crear(self, muestra: MuestraBiologica) -> int:
        """
        Inserta la muestra biológica y su primer evento inmutable de extracción
        dentro de una única transacción atómica.
        """
        muestra.validar()
        observacion_inicial = (
            muestra.historial[0].observacion
            if muestra.historial
            else OBSERVACION_EXTRACCION_INICIAL
        )
        sql_muestra = """
            INSERT INTO muestras_biologicas (
                codigo_muestra, orden_id, tipo_muestra_id, fecha_hora_extraccion,
                remito_id, estado_actual, motivo_rechazo
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        sql_historial = """
            INSERT INTO historial_estados_muestra (
                muestra_id, estado_anterior, estado_nuevo, fecha_hora, observacion
            ) VALUES (?, ?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql_muestra, (
                muestra.codigo_muestra,
                muestra.orden_id,
                muestra.tipo_muestra_id,
                muestra.fecha_hora_extraccion,
                muestra.remito_id,
                muestra.estado_actual,
                muestra.motivo_rechazo,
            ))
            muestra_id = cursor.lastrowid
            muestra.id = muestra_id

            # Inserción atómica del evento inicial en el historial inmutable
            cursor.execute(sql_historial, (
                muestra_id,
                None,
                muestra.estado_actual,
                muestra.fecha_hora_extraccion,
                observacion_inicial,
            ))
            historial_id = cursor.lastrowid
            if muestra._historial:
                muestra._historial[0] = RegistroTrazabilidad(
                    id=historial_id,
                    muestra_id=muestra_id,
                    estado_anterior=None,
                    estado_nuevo=muestra.estado_actual,
                    fecha_hora=muestra.fecha_hora_extraccion,
                    observacion=observacion_inicial,
                )
            return muestra_id

    def actualizar_estado(
        self,
        muestra_id: int,
        estado_anterior: str,
        estado_nuevo: str,
        fecha_hora: str,
        observacion: str = "",
        motivo_rechazo: str | None = None,
        remito_id: int | None = None,
    ) -> None:
        """
        Transición Atómica de Estado:
            1. Actualiza `estado_actual` (y optativamente `remito_id` / `motivo_rechazo`)
               en la tabla `muestras_biologicas`.
            2. Inserta la entrada de trazabilidad en `historial_estados_muestra`.
            Ambos pasos se confirman o se deshacen juntos con commit() / rollback().
        """
        sql_muestra = """
            UPDATE muestras_biologicas
            SET estado_actual = ?,
                motivo_rechazo = COALESCE(?, motivo_rechazo),
                remito_id = COALESCE(?, remito_id)
            WHERE id = ?
        """
        sql_historial = """
            INSERT INTO historial_estados_muestra (
                muestra_id, estado_anterior, estado_nuevo, fecha_hora, observacion
            ) VALUES (?, ?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql_muestra, (estado_nuevo, motivo_rechazo, remito_id, muestra_id))
            cursor.execute(sql_historial, (
                muestra_id,
                estado_anterior,
                estado_nuevo,
                fecha_hora,
                observacion or None,
            ))

    def obtener_por_id(self, muestra_id: int) -> MuestraBiologica | None:
        """Busca una muestra por ID reconstruyendo su objeto de dominio y su historial."""
        sql = """
            SELECT mb.id, mb.codigo_muestra, mb.orden_id, mb.tipo_muestra_id,
                   mb.fecha_hora_extraccion, mb.remito_id, mb.estado_actual,
                   mb.motivo_rechazo, ctm.nombre AS nombre_tipo_muestra
            FROM muestras_biologicas mb
            JOIN catalogo_tipos_muestra ctm ON mb.tipo_muestra_id = ctm.id
            WHERE mb.id = ?
        """
        fila = self.conexion.consultar_uno(sql, (muestra_id,))
        if not fila:
            return None

        historial = self.obtener_historial(muestra_id)
        return self._mapear_fila(fila, historial)

    def obtener_por_codigo(self, codigo_muestra: str) -> MuestraBiologica | None:
        """Busca una muestra por su código único de identificación."""
        sql = """
            SELECT mb.id, mb.codigo_muestra, mb.orden_id, mb.tipo_muestra_id,
                   mb.fecha_hora_extraccion, mb.remito_id, mb.estado_actual,
                   mb.motivo_rechazo, ctm.nombre AS nombre_tipo_muestra
            FROM muestras_biologicas mb
            JOIN catalogo_tipos_muestra ctm ON mb.tipo_muestra_id = ctm.id
            WHERE mb.codigo_muestra = ?
        """
        fila = self.conexion.consultar_uno(sql, (codigo_muestra.strip().upper(),))
        if not fila:
            return None

        historial = self.obtener_historial(fila["id"])
        return self._mapear_fila(fila, historial)

    def listar_por_orden(self, orden_id: int) -> list[MuestraBiologica]:
        """Obtiene todas las muestras asociadas a una orden de derivación."""
        sql = """
            SELECT mb.id, mb.codigo_muestra, mb.orden_id, mb.tipo_muestra_id,
                   mb.fecha_hora_extraccion, mb.remito_id, mb.estado_actual,
                   mb.motivo_rechazo, ctm.nombre AS nombre_tipo_muestra
            FROM muestras_biologicas mb
            JOIN catalogo_tipos_muestra ctm ON mb.tipo_muestra_id = ctm.id
            WHERE mb.orden_id = ?
            ORDER BY mb.id
        """
        filas = self.conexion.consultar_todos(sql, (orden_id,))
        return self._mapear_filas_con_historiales(filas)

    def listar_por_remito(self, remito_id: int) -> list[MuestraBiologica]:
        """Obtiene todas las muestras empaquetadas en un remito biológico."""
        sql = """
            SELECT mb.id, mb.codigo_muestra, mb.orden_id, mb.tipo_muestra_id,
                   mb.fecha_hora_extraccion, mb.remito_id, mb.estado_actual,
                   mb.motivo_rechazo, ctm.nombre AS nombre_tipo_muestra
            FROM muestras_biologicas mb
            JOIN catalogo_tipos_muestra ctm ON mb.tipo_muestra_id = ctm.id
            WHERE mb.remito_id = ?
            ORDER BY mb.id
        """
        filas = self.conexion.consultar_todos(sql, (remito_id,))
        return self._mapear_filas_con_historiales(filas)

    def listar_por_estado(self, estado: str) -> list[MuestraBiologica]:
        """Obtiene muestras que se encuentren actualmente en un estado determinado."""
        sql = """
            SELECT mb.id, mb.codigo_muestra, mb.orden_id, mb.tipo_muestra_id,
                   mb.fecha_hora_extraccion, mb.remito_id, mb.estado_actual,
                   mb.motivo_rechazo, ctm.nombre AS nombre_tipo_muestra
            FROM muestras_biologicas mb
            JOIN catalogo_tipos_muestra ctm ON mb.tipo_muestra_id = ctm.id
            WHERE mb.estado_actual = ?
            ORDER BY mb.id DESC
        """
        filas = self.conexion.consultar_todos(sql, (estado,))
        return self._mapear_filas_con_historiales(filas)

    def listar_extraidas_por_clinica(self, clinica_id: int | None = None) -> list[MuestraBiologica]:
        """
        Lista las muestras en estado 'Extraida' pendientes de empaquetar.
        Si se especifica `clinica_id`, filtra directamente en SQL mediante JOIN
        (evita consultas N+1 desde la capa de servicios).
        """
        if clinica_id is None:
            return self.listar_por_estado("Extraida")

        sql = """
            SELECT mb.id, mb.codigo_muestra, mb.orden_id, mb.tipo_muestra_id,
                   mb.fecha_hora_extraccion, mb.remito_id, mb.estado_actual,
                   mb.motivo_rechazo, ctm.nombre AS nombre_tipo_muestra
            FROM muestras_biologicas mb
            JOIN catalogo_tipos_muestra ctm ON mb.tipo_muestra_id = ctm.id
            JOIN ordenes_derivacion od ON mb.orden_id = od.id
            JOIN consultas_medicas cm ON od.consulta_id = cm.id
            WHERE mb.estado_actual = 'Extraida' AND cm.clinica_id = ?
            ORDER BY mb.id DESC
        """
        filas = self.conexion.consultar_todos(sql, (clinica_id,))
        return self._mapear_filas_con_historiales(filas)

    def obtener_clinica_origen(self, muestra_id: int) -> int | None:
        """
        Obtiene el ID de la clínica en la que se extrajo la muestra siguiendo la
        relación relacional: Muestra -> OrdenDerivacion -> ConsultaMedica -> Clinica.
        """
        sql = """
            SELECT cm.clinica_id
            FROM muestras_biologicas mb
            JOIN ordenes_derivacion od ON mb.orden_id = od.id
            JOIN consultas_medicas cm ON od.consulta_id = cm.id
            WHERE mb.id = ?
        """
        fila = self.conexion.consultar_uno(sql, (muestra_id,))
        return int(fila["clinica_id"]) if fila else None

    def listar_tipos_muestra(self) -> list[dict]:
        """Devuelve el catálogo paramétrico de tipos de muestra biológica."""
        filas = self.conexion.consultar_todos(
            "SELECT id, codigo, nombre FROM catalogo_tipos_muestra ORDER BY nombre"
        )
        return [dict(f) for f in filas]

    def obtener_historial(self, muestra_id: int) -> list[RegistroTrazabilidad]:
        """Recupera la cadena completa e inmutable de eventos de la muestra."""
        sql = """
            SELECT id, muestra_id, estado_anterior, estado_nuevo, fecha_hora, observacion
            FROM historial_estados_muestra
            WHERE muestra_id = ?
            ORDER BY id ASC
        """
        filas = self.conexion.consultar_todos(sql, (muestra_id,))
        return [
            RegistroTrazabilidad(
                id=f["id"],
                muestra_id=f["muestra_id"],
                estado_anterior=f["estado_anterior"],
                estado_nuevo=f["estado_nuevo"],
                fecha_hora=f["fecha_hora"],
                observacion=f["observacion"],
            )
            for f in filas
        ]

    def _mapear_filas_con_historiales(self, filas: list[sqlite3.Row]) -> list[MuestraBiologica]:
        """
        Hidrata un lote de muestras cargando todos sus historiales en una única
        consulta SQL con `IN (...)`, eliminando el problema de consultas N+1.
        """
        if not filas:
            return []

        ids = [int(f["id"]) for f in filas]
        marcadores = ", ".join("?" for _ in ids)
        sql_hist = f"""
            SELECT id, muestra_id, estado_anterior, estado_nuevo, fecha_hora, observacion
            FROM historial_estados_muestra
            WHERE muestra_id IN ({marcadores})
            ORDER BY id ASC
        """
        filas_hist = self.conexion.consultar_todos(sql_hist, tuple(ids))
        historiales_por_muestra: dict[int, list[RegistroTrazabilidad]] = {mid: [] for mid in ids}
        for fh in filas_hist:
            historiales_por_muestra[int(fh["muestra_id"])].append(
                RegistroTrazabilidad(
                    id=fh["id"],
                    muestra_id=fh["muestra_id"],
                    estado_anterior=fh["estado_anterior"],
                    estado_nuevo=fh["estado_nuevo"],
                    fecha_hora=fh["fecha_hora"],
                    observacion=fh["observacion"],
                )
            )
        return [self._mapear_fila(f, historiales_por_muestra.get(int(f["id"]), [])) for f in filas]

    def listar_muestras_rechazadas_con_transporte(
        self, clinica_id: int | None = None
    ) -> list[dict]:
        """
        Recupera información completa de trazabilidad de todas las muestras rechazadas
        para el reporte de auditoría y transporte sanitario (Reporte 2 del TP).
        """
        condicion_clinica = "AND rb.clinica_origen_id = ?" if clinica_id is not None else ""
        parametros = (clinica_id,) if clinica_id is not None else ()
        sql = f"""
            SELECT mb.id AS muestra_id,
                   mb.codigo_muestra,
                   ctm.nombre AS tipo_muestra,
                   mb.fecha_hora_extraccion,
                   mb.motivo_rechazo,
                   rb.numero_remito,
                   cl.nombre AS clinica_origen,
                   lb.nombre AS laboratorio_destino,
                   cs.codigo AS conservadora_codigo,
                   ps.numero_serie AS precinto_serie,
                   ps.estado AS precinto_estado,
                   tr.nombre AS transportista_nombre,
                   tr.vehiculo_patente AS transportista_patente,
                   el.fecha_hora_despacho,
                   el.fecha_hora_recepcion
            FROM muestras_biologicas mb
            JOIN catalogo_tipos_muestra ctm ON mb.tipo_muestra_id = ctm.id
            LEFT JOIN remitos_biologicos rb ON mb.remito_id = rb.id
            LEFT JOIN clinicas cl ON rb.clinica_origen_id = cl.id
            LEFT JOIN laboratorios lb ON rb.laboratorio_destino_id = lb.id
            LEFT JOIN conservadoras cs ON rb.conservadora_id = cs.id
            LEFT JOIN precintos_sanitarios ps ON rb.precinto_id = ps.id
            LEFT JOIN envios_laboratorio el ON rb.id = el.remito_id
            LEFT JOIN transportistas tr ON el.transportista_id = tr.id
            WHERE mb.estado_actual = 'Rechazada' {condicion_clinica}
            ORDER BY mb.id DESC
        """
        filas = self.conexion.consultar_todos(sql, parametros)
        return [dict(f) for f in filas]

    @staticmethod
    def _mapear_fila(fila: sqlite3.Row, historial: list[RegistroTrazabilidad]) -> MuestraBiologica:
        """Construye la entidad MuestraBiologica con su historial y su estado State activo."""
        return MuestraBiologica(
            id=fila["id"],
            codigo_muestra=fila["codigo_muestra"],
            orden_id=fila["orden_id"],
            tipo_muestra_id=fila["tipo_muestra_id"],
            fecha_hora_extraccion=fila["fecha_hora_extraccion"],
            remito_id=fila["remito_id"],
            estado_inicial=fila["estado_actual"],
            motivo_rechazo=fila["motivo_rechazo"],
            nombre_tipo_muestra=fila["nombre_tipo_muestra"] if "nombre_tipo_muestra" in fila.keys() else "",
            historial_inicial=historial,
        )
