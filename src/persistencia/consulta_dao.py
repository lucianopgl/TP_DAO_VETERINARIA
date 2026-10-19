"""
Capa de Persistencia: ConsultaDAO
=================================

Gestiona la persistencia de Consultas Médicas, Tratamientos indicados
y Órdenes de Derivación a laboratorios centrales.
"""

from __future__ import annotations

import sqlite3
from src.dominio.consulta_medica import ConsultaMedica, OrdenDerivacion
from src.dominio.historia_clinica import Tratamiento
from src.persistencia.dao_base import DAOBase


class ConsultaDAO(DAOBase):
    """Objeto de Acceso a Datos para `consultas_medicas`, `tratamientos` y `ordenes_derivacion`."""

    def crear(self, consulta: ConsultaMedica) -> int:
        """
        Inserta una consulta médica y sus tratamientos asociados dentro de una
        misma unidad de trabajo atómica.
        """
        consulta.validar()
        sql_consulta = """
            INSERT INTO consultas_medicas (
                mascota_id, clinica_id, veterinario_id, fecha_hora_inicio,
                duracion_minutos, motivo, diagnostico, costo_consulta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        sql_tratamiento = """
            INSERT INTO tratamientos (consulta_id, descripcion, medicamento, dosis, duracion_dias)
            VALUES (?, ?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql_consulta, (
                consulta.mascota_id,
                consulta.clinica_id,
                consulta.veterinario_id,
                consulta.fecha_hora_inicio,
                consulta.duracion_minutos,
                consulta.motivo,
                consulta.diagnostico,
                consulta.costo_consulta,
            ))
            consulta_id = cursor.lastrowid
            consulta.id = consulta_id

            for t in consulta.tratamientos:
                cursor.execute(sql_tratamiento, (
                    consulta_id,
                    t.descripcion,
                    t.medicamento,
                    t.dosis,
                    t.duracion_dias,
                ))
                t.id = cursor.lastrowid
                t.consulta_id = consulta_id

            return consulta_id

    def actualizar_diagnostico(self, consulta_id: int, diagnostico: str) -> None:
        """Actualiza las conclusiones diagnósticas de la atención."""
        sql = "UPDATE consultas_medicas SET diagnostico = ? WHERE id = ?"
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (diagnostico, consulta_id))

    def obtener_por_id(self, consulta_id: int) -> ConsultaMedica | None:
        """Recupera una consulta médica completa incluyendo tratamientos y órdenes."""
        sql = """
            SELECT id, mascota_id, clinica_id, veterinario_id, fecha_hora_inicio,
                   duracion_minutos, motivo, diagnostico, costo_consulta
            FROM consultas_medicas
            WHERE id = ?
        """
        fila = self.conexion.consultar_uno(sql, (consulta_id,))
        if not fila:
            return None

        consulta = self._mapear_fila(fila)
        consulta.tratamientos = self.obtener_tratamientos_por_consulta(consulta_id)
        consulta.ordenes = self.listar_ordenes_por_consulta(consulta_id)
        return consulta

    def listar_por_veterinario_y_fecha(self, veterinario_id: int, fecha_str: str) -> list[ConsultaMedica]:
        """
        Recupera todas las consultas asignadas a un veterinario en un día determinado (YYYY-MM-DD).
        Utilizado por la capa de servicio para validar matemáticamente la no superposición de turnos.
        """
        patron_fecha = f"{fecha_str.strip()}%"
        sql = """
            SELECT id, mascota_id, clinica_id, veterinario_id, fecha_hora_inicio,
                   duracion_minutos, motivo, diagnostico, costo_consulta
            FROM consultas_medicas
            WHERE veterinario_id = ? AND fecha_hora_inicio LIKE ?
            ORDER BY fecha_hora_inicio
        """
        filas = self.conexion.consultar_todos(sql, (veterinario_id, patron_fecha))
        return [self._mapear_fila(f) for f in filas]

    def listar_por_mascota(self, mascota_id: int) -> list[ConsultaMedica]:
        """Recupera el historial de consultas de una mascota ordenadas cronológicamente."""
        sql = """
            SELECT id, mascota_id, clinica_id, veterinario_id, fecha_hora_inicio,
                   duracion_minutos, motivo, diagnostico, costo_consulta
            FROM consultas_medicas
            WHERE mascota_id = ?
            ORDER BY fecha_hora_inicio DESC
        """
        filas = self.conexion.consultar_todos(sql, (mascota_id,))
        return [self._mapear_fila(f) for f in filas]

    # ----------------------------------------------------------------------------------
    # Tratamientos
    # ----------------------------------------------------------------------------------

    def obtener_tratamientos_por_consulta(self, consulta_id: int) -> list[Tratamiento]:
        """Recupera los tratamientos indicados en una consulta."""
        sql = """
            SELECT id, consulta_id, descripcion, medicamento, dosis, duracion_dias
            FROM tratamientos
            WHERE consulta_id = ?
        """
        filas = self.conexion.consultar_todos(sql, (consulta_id,))
        return [
            Tratamiento(
                id=f["id"],
                consulta_id=f["consulta_id"],
                descripcion=f["descripcion"],
                medicamento=f["medicamento"],
                dosis=f["dosis"],
                duracion_dias=f["duracion_dias"],
            )
            for f in filas
        ]

    # ----------------------------------------------------------------------------------
    # Órdenes de Derivación
    # ----------------------------------------------------------------------------------

    def crear_orden_derivacion(self, orden: OrdenDerivacion) -> int:
        """Inserta una nueva orden de derivación a laboratorio."""
        sql = """
            INSERT INTO ordenes_derivacion (
                consulta_id, tipo_estudio_id, indicaciones, prioridad, fecha_hora_emision
            ) VALUES (?, ?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (
                orden.consulta_id,
                orden.tipo_estudio_id,
                orden.indicaciones,
                orden.prioridad,
                orden.fecha_hora_emision,
            ))
            orden_id = cursor.lastrowid
            orden.id = orden_id
            return orden_id

    def obtener_orden_por_id(self, orden_id: int) -> OrdenDerivacion | None:
        """Busca una orden de derivación con información ampliada del catálogo."""
        sql = """
            SELECT od.id, od.consulta_id, od.tipo_estudio_id, od.indicaciones,
                   od.prioridad, od.fecha_hora_emision,
                   cte.nombre AS nombre_estudio, cte.costo_base
            FROM ordenes_derivacion od
            JOIN catalogo_tipos_estudio cte ON od.tipo_estudio_id = cte.id
            WHERE od.id = ?
        """
        fila = self.conexion.consultar_uno(sql, (orden_id,))
        if not fila:
            return None
        return OrdenDerivacion(
            id=fila["id"],
            consulta_id=fila["consulta_id"],
            tipo_estudio_id=fila["tipo_estudio_id"],
            indicaciones=fila["indicaciones"],
            prioridad=fila["prioridad"],
            fecha_hora_emision=fila["fecha_hora_emision"],
            nombre_estudio=fila["nombre_estudio"],
            costo_base=float(fila["costo_base"]),
        )

    def listar_ordenes_por_consulta(self, consulta_id: int) -> list[OrdenDerivacion]:
        """Obtiene todas las órdenes de derivación emitidas en una consulta."""
        sql = """
            SELECT od.id, od.consulta_id, od.tipo_estudio_id, od.indicaciones,
                   od.prioridad, od.fecha_hora_emision,
                   cte.nombre AS nombre_estudio, cte.costo_base
            FROM ordenes_derivacion od
            JOIN catalogo_tipos_estudio cte ON od.tipo_estudio_id = cte.id
            WHERE od.consulta_id = ?
            ORDER BY od.fecha_hora_emision
        """
        filas = self.conexion.consultar_todos(sql, (consulta_id,))
        return [
            OrdenDerivacion(
                id=f["id"],
                consulta_id=f["consulta_id"],
                tipo_estudio_id=f["tipo_estudio_id"],
                indicaciones=f["indicaciones"],
                prioridad=f["prioridad"],
                fecha_hora_emision=f["fecha_hora_emision"],
                nombre_estudio=f["nombre_estudio"],
                costo_base=float(f["costo_base"]),
            )
            for f in filas
        ]

    @staticmethod
    def _mapear_fila(fila: sqlite3.Row) -> ConsultaMedica:
        """Mapea una fila de SQLite a un objeto de dominio ConsultaMedica."""
        return ConsultaMedica(
            id=fila["id"],
            mascota_id=fila["mascota_id"],
            clinica_id=fila["clinica_id"],
            veterinario_id=fila["veterinario_id"],
            fecha_hora_inicio=fila["fecha_hora_inicio"],
            duracion_minutos=fila["duracion_minutos"],
            motivo=fila["motivo"],
            diagnostico=fila["diagnostico"],
            costo_consulta=float(fila["costo_consulta"]),
        )
