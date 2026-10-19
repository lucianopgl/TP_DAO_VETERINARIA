"""
Capa de Persistencia: FacturacionDAO
====================================

Gestiona la persistencia de Resultados de Análisis de Laboratorio y
Comprobantes de Atención con estructura flexible de Cabecera y Detalle.
"""

from __future__ import annotations

import sqlite3
from src.dominio.facturacion import (
    ComprobanteAtencion,
    DetalleComprobante,
    ResultadoAnalisis,
)
from src.persistencia.dao_base import DAOBase


class FacturacionDAO(DAOBase):
    """Objeto de Acceso a Datos para `resultados_analisis`, `comprobantes` y `detalles_comprobante`."""

    # ----------------------------------------------------------------------------------
    # Resultados de Análisis
    # ----------------------------------------------------------------------------------

    def crear_resultado(self, resultado: ResultadoAnalisis) -> int:
        """Inserta el resultado emitido por el bioquímico sobre una muestra viable."""
        sql = """
            INSERT INTO resultados_analisis (
                muestra_id, profesional_laboratorio_id, valores_medidos,
                conclusion, costo_analisis, fecha_hora_analisis
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (
                resultado.muestra_id,
                resultado.profesional_laboratorio_id,
                resultado.valores_medidos,
                resultado.conclusion,
                resultado.costo_analisis,
                resultado.fecha_hora_analisis,
            ))
            resultado_id = cursor.lastrowid
            resultado.id = resultado_id
            return resultado_id

    def obtener_resultado_por_muestra(self, muestra_id: int) -> ResultadoAnalisis | None:
        """Busca el resultado técnico asociado a una muestra biológica."""
        sql = """
            SELECT ra.id, ra.muestra_id, ra.profesional_laboratorio_id, ra.valores_medidos,
                   ra.conclusion, ra.costo_analisis, ra.fecha_hora_analisis,
                   (pl.nombre || ' ' || pl.apellido) AS bioquimico_nombre
            FROM resultados_analisis ra
            JOIN profesionales_laboratorio pl ON ra.profesional_laboratorio_id = pl.id
            WHERE ra.muestra_id = ?
        """
        fila = self.conexion.consultar_uno(sql, (muestra_id,))
        if not fila:
            return None
        return ResultadoAnalisis(
            id=fila["id"],
            muestra_id=fila["muestra_id"],
            profesional_laboratorio_id=fila["profesional_laboratorio_id"],
            valores_medidos=fila["valores_medidos"],
            conclusion=fila["conclusion"],
            costo_analisis=float(fila["costo_analisis"]),
            fecha_hora_analisis=fila["fecha_hora_analisis"],
            bioquimico_nombre=fila["bioquimico_nombre"],
        )

    # ----------------------------------------------------------------------------------
    # Comprobantes y Detalles (Facturación)
    # ----------------------------------------------------------------------------------

    def crear_comprobante(self, comprobante: ComprobanteAtencion) -> int:
        """
        Inserta la cabecera del comprobante y todos sus detalles desagregados
        en una transacción estrictamente atómica.
        """
        sql_cabecera = """
            INSERT INTO comprobantes (
                numero_comprobante, consulta_id, estrategia_tarifa,
                monto_total, fecha_hora_emision
            ) VALUES (?, ?, ?, ?, ?)
        """
        sql_detalle = """
            INSERT INTO detalles_comprobante (
                comprobante_id, tipo_concepto, concepto, monto
            ) VALUES (?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql_cabecera, (
                comprobante.numero_comprobante,
                comprobante.consulta_id,
                comprobante.estrategia_tarifa,
                comprobante.monto_total,
                comprobante.fecha_hora_emision,
            ))
            comprobante_id = cursor.lastrowid
            comprobante.id = comprobante_id

            for detalle in comprobante.detalles:
                cursor.execute(sql_detalle, (
                    comprobante_id,
                    detalle.tipo_concepto,
                    detalle.concepto,
                    detalle.monto,
                ))
                detalle.id = cursor.lastrowid
                detalle.comprobante_id = comprobante_id

            return comprobante_id

    def obtener_comprobante_por_consulta(self, consulta_id: int) -> ComprobanteAtencion | None:
        """Recupera la factura emitida para una consulta médica."""
        sql = """
            SELECT id, numero_comprobante, consulta_id, estrategia_tarifa,
                   monto_total, fecha_hora_emision
            FROM comprobantes
            WHERE consulta_id = ?
        """
        fila = self.conexion.consultar_uno(sql, (consulta_id,))
        if not fila:
            return None
        return self._cargar_comprobante_con_detalles(fila)

    def obtener_comprobante_por_id(self, comprobante_id: int) -> ComprobanteAtencion | None:
        """Recupera un comprobante por su ID."""
        sql = """
            SELECT id, numero_comprobante, consulta_id, estrategia_tarifa,
                   monto_total, fecha_hora_emision
            FROM comprobantes
            WHERE id = ?
        """
        fila = self.conexion.consultar_uno(sql, (comprobante_id,))
        if not fila:
            return None
        return self._cargar_comprobante_con_detalles(fila)

    def listar_comprobantes(self) -> list[ComprobanteAtencion]:
        """Lista todos los comprobantes emitidos ordenados por fecha descendente."""
        sql = """
            SELECT id, numero_comprobante, consulta_id, estrategia_tarifa,
                   monto_total, fecha_hora_emision
            FROM comprobantes
            ORDER BY fecha_hora_emision DESC
        """
        filas = self.conexion.consultar_todos(sql)
        return [self._cargar_comprobante_con_detalles(f) for f in filas]

    def _cargar_comprobante_con_detalles(self, fila_cabecera: sqlite3.Row) -> ComprobanteAtencion:
        """Carga los ítems de detalle para una cabecera recuperada."""
        comprobante_id = fila_cabecera["id"]
        sql_detalles = """
            SELECT id, comprobante_id, tipo_concepto, concepto, monto
            FROM detalles_comprobante
            WHERE comprobante_id = ?
            ORDER BY id ASC
        """
        filas_detalles = self.conexion.consultar_todos(sql_detalles, (comprobante_id,))
        detalles = [
            DetalleComprobante(
                id=f["id"],
                comprobante_id=f["comprobante_id"],
                tipo_concepto=f["tipo_concepto"],
                concepto=f["concepto"],
                monto=float(f["monto"]),
            )
            for f in filas_detalles
        ]
        return ComprobanteAtencion(
            id=comprobante_id,
            numero_comprobante=fila_cabecera["numero_comprobante"],
            consulta_id=fila_cabecera["consulta_id"],
            estrategia_tarifa=fila_cabecera["estrategia_tarifa"],
            monto_total=float(fila_cabecera["monto_total"]),
            fecha_hora_emision=fila_cabecera["fecha_hora_emision"],
            detalles=detalles,
        )
