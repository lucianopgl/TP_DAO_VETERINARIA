"""
Capa de Persistencia: LogisticaDAO
==================================

Gestiona la persistencia de Conservadoras Isotérmicas, Precintos Sanitarios,
Remitos Biológicos (con historial inmutable) y Envíos de Laboratorio.
"""

from __future__ import annotations

import sqlite3
from src.dominio.logistica import (
    ConservadoraIsotermica,
    EnvioLaboratorio,
    PrecintoSanitario,
    RemitoBiologico,
)
from src.persistencia.dao_base import DAOBase


class LogisticaDAO(DAOBase):
    """Objeto de Acceso a Datos para la logística de transporte y derivación."""

    # ----------------------------------------------------------------------------------
    # Conservadoras Isotérmicas
    # ----------------------------------------------------------------------------------

    def listar_conservadoras_disponibles(self) -> list[ConservadoraIsotermica]:
        """Obtiene las conservadoras habilitadas para ser asignadas a un remito."""
        sql = """
            SELECT id, codigo, capacidad_maxima, temperatura_min, temperatura_max, disponible
            FROM conservadoras
            WHERE disponible = 1
            ORDER BY codigo
        """
        filas = self.conexion.consultar_todos(sql)
        return [self._mapear_conservadora(f) for f in filas]

    def obtener_conservadora_por_id(self, conservadora_id: int) -> ConservadoraIsotermica | None:
        """Busca una conservadora por su ID."""
        sql = """
            SELECT id, codigo, capacidad_maxima, temperatura_min, temperatura_max, disponible
            FROM conservadoras
            WHERE id = ?
        """
        fila = self.conexion.consultar_uno(sql, (conservadora_id,))
        return self._mapear_conservadora(fila) if fila else None

    def actualizar_disponibilidad_conservadora(self, conservadora_id: int, disponible: bool) -> None:
        """Marca una conservadora como ocupada (en tránsito) o disponible (retornada)."""
        sql = "UPDATE conservadoras SET disponible = ? WHERE id = ?"
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (1 if disponible else 0, conservadora_id))

    # ----------------------------------------------------------------------------------
    # Precintos Sanitarios
    # ----------------------------------------------------------------------------------

    def crear_precinto(self, numero_serie: str, estado: str = "Intacto") -> int:
        """Registra un nuevo precinto de seguridad en el inventario."""
        precinto = PrecintoSanitario(id=None, numero_serie=numero_serie, estado=estado)
        sql = "INSERT INTO precintos_sanitarios (numero_serie, estado) VALUES (?, ?)"
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (precinto.numero_serie, precinto.estado))
            precinto_id = cursor.lastrowid
            precinto.id = precinto_id
            return precinto_id

    def obtener_precinto_por_id(self, precinto_id: int) -> PrecintoSanitario | None:
        """Busca un precinto sanitario por ID."""
        sql = "SELECT id, numero_serie, estado FROM precintos_sanitarios WHERE id = ?"
        fila = self.conexion.consultar_uno(sql, (precinto_id,))
        return self._mapear_precinto(fila) if fila else None

    def obtener_precinto_por_numero(self, numero_serie: str) -> PrecintoSanitario | None:
        """Busca un precinto por su número de serie único."""
        sql = "SELECT id, numero_serie, estado FROM precintos_sanitarios WHERE numero_serie = ?"
        fila = self.conexion.consultar_uno(sql, (numero_serie.strip().upper(),))
        return self._mapear_precinto(fila) if fila else None

    def actualizar_estado_precinto(self, precinto_id: int, nuevo_estado: str) -> None:
        """Actualiza el estado físico verificado del precinto (Intacto, Roto, Violado)."""
        estado_limpio = nuevo_estado.strip().capitalize()
        sql = "UPDATE precintos_sanitarios SET estado = ? WHERE id = ?"
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (estado_limpio, precinto_id))

    # ----------------------------------------------------------------------------------
    # Remitos Biológicos
    # ----------------------------------------------------------------------------------

    def crear_remito(self, remito: RemitoBiologico) -> int:
        """
        Inserta un remito biológico y registra su evento inicial en el historial inmutable.
        """
        remito.validar_estado()
        sql_remito = """
            INSERT INTO remitos_biologicos (
                numero_remito, clinica_origen_id, laboratorio_destino_id,
                conservadora_id, precinto_id, estado, fecha_hora_creacion
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        sql_historial = """
            INSERT INTO historial_estados_remito (
                remito_id, estado_anterior, estado_nuevo, fecha_hora, observacion
            ) VALUES (?, ?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql_remito, (
                remito.numero_remito,
                remito.clinica_origen_id,
                remito.laboratorio_destino_id,
                remito.conservadora_id,
                remito.precinto_id,
                remito.estado,
                remito.fecha_hora_creacion,
            ))
            remito_id = cursor.lastrowid
            remito.id = remito_id

            cursor.execute(sql_historial, (
                remito_id,
                None,
                remito.estado,
                remito.fecha_hora_creacion,
                "Creación y apertura de remito biológico.",
            ))
            return remito_id

    def actualizar_estado_remito(
        self,
        remito_id: int,
        estado_anterior: str,
        estado_nuevo: str,
        fecha_hora: str,
        observacion: str = "",
        precinto_id: int | None = None,
    ) -> None:
        """
        Actualiza el estado del remito e inserta el evento de auditoría de manera atómica.
        """
        sql_remito = """
            UPDATE remitos_biologicos
            SET estado = ?,
                precinto_id = COALESCE(?, precinto_id)
            WHERE id = ?
        """
        sql_historial = """
            INSERT INTO historial_estados_remito (
                remito_id, estado_anterior, estado_nuevo, fecha_hora, observacion
            ) VALUES (?, ?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql_remito, (estado_nuevo, precinto_id, remito_id))
            cursor.execute(sql_historial, (
                remito_id,
                estado_anterior,
                estado_nuevo,
                fecha_hora,
                observacion or None,
            ))

    def obtener_remito_por_id(self, remito_id: int) -> RemitoBiologico | None:
        """Recupera un remito biológico por su ID."""
        sql = """
            SELECT id, numero_remito, clinica_origen_id, laboratorio_destino_id,
                   conservadora_id, precinto_id, estado, fecha_hora_creacion
            FROM remitos_biologicos
            WHERE id = ?
        """
        fila = self.conexion.consultar_uno(sql, (remito_id,))
        return self._mapear_remito(fila) if fila else None

    def obtener_remito_por_numero(self, numero_remito: str) -> RemitoBiologico | None:
        """Recupera un remito biológico por su número."""
        sql = """
            SELECT id, numero_remito, clinica_origen_id, laboratorio_destino_id,
                   conservadora_id, precinto_id, estado, fecha_hora_creacion
            FROM remitos_biologicos
            WHERE numero_remito = ?
        """
        fila = self.conexion.consultar_uno(sql, (numero_remito.strip().upper(),))
        return self._mapear_remito(fila) if fila else None

    def listar_remitos_por_estado(self, estado: str) -> list[RemitoBiologico]:
        """Obtiene los remitos que se encuentren en un estado específico."""
        sql = """
            SELECT id, numero_remito, clinica_origen_id, laboratorio_destino_id,
                   conservadora_id, precinto_id, estado, fecha_hora_creacion
            FROM remitos_biologicos
            WHERE estado = ?
            ORDER BY id DESC
        """
        filas = self.conexion.consultar_todos(sql, (estado,))
        return [self._mapear_remito(f) for f in filas]

    # ----------------------------------------------------------------------------------
    # Envíos de Laboratorio
    # ----------------------------------------------------------------------------------

    def crear_envio(self, envio: EnvioLaboratorio) -> int:
        """Registra el despacho físico de un remito con su transportista asignado."""
        sql = """
            INSERT INTO envios_laboratorio (
                remito_id, transportista_id, fecha_hora_despacho,
                fecha_hora_recepcion, observaciones_recepcion
            ) VALUES (?, ?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (
                envio.remito_id,
                envio.transportista_id,
                envio.fecha_hora_despacho,
                envio.fecha_hora_recepcion,
                envio.observaciones_recepcion,
            ))
            envio_id = cursor.lastrowid
            envio.id = envio_id
            return envio_id

    def registrar_recepcion_envio(
        self,
        remito_id: int,
        fecha_hora_recepcion: str,
        observaciones: str = "",
    ) -> None:
        """Registra la llegada del envío a la sede del laboratorio central."""
        sql = """
            UPDATE envios_laboratorio
            SET fecha_hora_recepcion = ?,
                observaciones_recepcion = ?
            WHERE remito_id = ?
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (fecha_hora_recepcion, observaciones or None, remito_id))

    def obtener_envio_por_remito(self, remito_id: int) -> EnvioLaboratorio | None:
        """Obtiene los datos de traslado de un remito particular."""
        sql = """
            SELECT id, remito_id, transportista_id, fecha_hora_despacho,
                   fecha_hora_recepcion, observaciones_recepcion
            FROM envios_laboratorio
            WHERE remito_id = ?
        """
        fila = self.conexion.consultar_uno(sql, (remito_id,))
        if not fila:
            return None
        return EnvioLaboratorio(
            id=fila["id"],
            remito_id=fila["remito_id"],
            transportista_id=fila["transportista_id"],
            fecha_hora_despacho=fila["fecha_hora_despacho"],
            fecha_hora_recepcion=fila["fecha_hora_recepcion"],
            observaciones_recepcion=fila["observaciones_recepcion"],
        )

    # ----------------------------------------------------------------------------------
    # Mapeadores
    # ----------------------------------------------------------------------------------

    @staticmethod
    def _mapear_conservadora(fila: sqlite3.Row) -> ConservadoraIsotermica:
        return ConservadoraIsotermica(
            id=fila["id"],
            codigo=fila["codigo"],
            capacidad_maxima=fila["capacidad_maxima"],
            temperatura_min=fila["temperatura_min"],
            temperatura_max=fila["temperatura_max"],
            disponible=bool(fila["disponible"]),
        )

    @staticmethod
    def _mapear_precinto(fila: sqlite3.Row) -> PrecintoSanitario:
        return PrecintoSanitario(
            id=fila["id"],
            numero_serie=fila["numero_serie"],
            estado=fila["estado"],
        )

    @staticmethod
    def _mapear_remito(fila: sqlite3.Row) -> RemitoBiologico:
        return RemitoBiologico(
            id=fila["id"],
            numero_remito=fila["numero_remito"],
            clinica_origen_id=fila["clinica_origen_id"],
            laboratorio_destino_id=fila["laboratorio_destino_id"],
            conservadora_id=fila["conservadora_id"],
            precinto_id=fila["precinto_id"],
            estado=fila["estado"],
            fecha_hora_creacion=fila["fecha_hora_creacion"],
        )
