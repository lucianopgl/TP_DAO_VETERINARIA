"""
Capa de Persistencia: MascotaDAO
================================

Implementa las operaciones de persistencia para Mascotas, Historias Clínicas
y Registro de Vacunación.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from src.dominio.mascota import Mascota
from src.dominio.historia_clinica import HistoriaClinica, VacunaAplicada
from src.persistencia.dao_base import DAOBase


class MascotaDAO(DAOBase):
    """Objeto de Acceso a Datos para las tablas `mascotas`, `historias_clinicas` y `vacunas_aplicadas`."""

    def crear(self, mascota: Mascota, fecha_apertura_historia: str | None = None) -> int:
        """
        Inserta una mascota y abre automáticamente su historia clínica en una
        única unidad de trabajo atómica.
        """
        mascota.validar()
        sql_mascota = """
            INSERT INTO mascotas (nombre, especie_id, raza, edad, sexo, cliente_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        sql_historia = """
            INSERT INTO historias_clinicas (mascota_id, fecha_apertura)
            VALUES (?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql_mascota, (
                mascota.nombre,
                mascota.especie_id,
                mascota.raza,
                mascota.edad,
                mascota.sexo,
                mascota.cliente_id,
            ))
            mascota_id = cursor.lastrowid
            mascota.id = mascota_id

            # Creación atómica de la historia clínica asociada
            fecha_apertura = fecha_apertura_historia or "2026-10-19"
            cursor.execute(sql_historia, (mascota_id, fecha_apertura))
            return mascota_id

    def actualizar(self, mascota: Mascota) -> None:
        """Actualiza los datos de la mascota."""
        if mascota.id is None:
            raise ValueError("No se puede actualizar una mascota sin ID.")
        mascota.validar()
        sql = """
            UPDATE mascotas
            SET nombre = ?, especie_id = ?, raza = ?, edad = ?, sexo = ?, cliente_id = ?
            WHERE id = ?
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (
                mascota.nombre,
                mascota.especie_id,
                mascota.raza,
                mascota.edad,
                mascota.sexo,
                mascota.cliente_id,
                mascota.id,
            ))

    def eliminar(self, mascota_id: int) -> None:
        """Elimina una mascota (SQLite validará integridad referencial)."""
        with self.conexion.transaccion() as cursor:
            cursor.execute("DELETE FROM historias_clinicas WHERE mascota_id = ?", (mascota_id,))
            cursor.execute("DELETE FROM mascotas WHERE id = ?", (mascota_id,))

    def obtener_por_id(self, mascota_id: int) -> Mascota | None:
        """Busca una mascota por ID incluyendo el nombre de su especie."""
        sql = """
            SELECT m.id, m.nombre, m.especie_id, m.raza, m.edad, m.sexo, m.cliente_id,
                   e.nombre AS nombre_especie
            FROM mascotas m
            JOIN catalogo_especies e ON m.especie_id = e.id
            WHERE m.id = ?
        """
        fila = self.conexion.consultar_uno(sql, (mascota_id,))
        return self._mapear_fila(fila) if fila else None

    def listar_por_cliente(self, cliente_id: int) -> list[Mascota]:
        """Obtiene todas las mascotas a cargo de un cliente determinado."""
        sql = """
            SELECT m.id, m.nombre, m.especie_id, m.raza, m.edad, m.sexo, m.cliente_id,
                   e.nombre AS nombre_especie
            FROM mascotas m
            JOIN catalogo_especies e ON m.especie_id = e.id
            WHERE m.cliente_id = ?
            ORDER BY m.nombre
        """
        filas = self.conexion.consultar_todos(sql, (cliente_id,))
        return [self._mapear_fila(f) for f in filas]

    def listar_todas(self) -> list[Mascota]:
        """Lista todas las mascotas registradas en la red."""
        sql = """
            SELECT m.id, m.nombre, m.especie_id, m.raza, m.edad, m.sexo, m.cliente_id,
                   e.nombre AS nombre_especie
            FROM mascotas m
            JOIN catalogo_especies e ON m.especie_id = e.id
            ORDER BY m.nombre
        """
        filas = self.conexion.consultar_todos(sql)
        return [self._mapear_fila(f) for f in filas]

    # ----------------------------------------------------------------------------------
    # Vacunas
    # ----------------------------------------------------------------------------------

    def registrar_vacuna_aplicada(self, vacuna: VacunaAplicada) -> int:
        """Registra la aplicación de una dosis de vacuna."""
        sql = """
            INSERT INTO vacunas_aplicadas (mascota_id, vacuna_id, fecha_aplicacion, consulta_id)
            VALUES (?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (
                vacuna.mascota_id,
                vacuna.vacuna_id,
                vacuna.fecha_aplicacion,
                vacuna.consulta_id,
            ))
            vacuna_id = cursor.lastrowid
            vacuna.id = vacuna_id
            return vacuna_id

    def listar_vacunas_de_mascota(self, mascota_id: int) -> list[VacunaAplicada]:
        """Obtiene el historial de vacunas aplicadas a una mascota."""
        sql = """
            SELECT va.id, va.mascota_id, va.vacuna_id, va.fecha_aplicacion, va.consulta_id,
                   cv.nombre AS nombre_vacuna, cv.es_obligatoria
            FROM vacunas_aplicadas va
            JOIN catalogo_vacunas cv ON va.vacuna_id = cv.id
            WHERE va.mascota_id = ?
            ORDER BY va.fecha_aplicacion DESC
        """
        filas = self.conexion.consultar_todos(sql, (mascota_id,))
        return [
            VacunaAplicada(
                id=f["id"],
                mascota_id=f["mascota_id"],
                vacuna_id=f["vacuna_id"],
                fecha_aplicacion=f["fecha_aplicacion"],
                nombre_vacuna=f["nombre_vacuna"],
                es_obligatoria=bool(f["es_obligatoria"]),
                consulta_id=f["consulta_id"],
            )
            for f in filas
        ]

    def obtener_catalogo_vacunas_obligatorias(self, especie_id: int) -> list[dict]:
        """Obtiene las vacunas que son obligatorias por ley sanitaria para una especie dada."""
        sql = """
            SELECT id, nombre, es_obligatoria, frecuencia_refuerzo_meses
            FROM catalogo_vacunas
            WHERE especie_id = ? AND es_obligatoria = 1
        """
        filas = self.conexion.consultar_todos(sql, (especie_id,))
        return [dict(f) for f in filas]

    def obtener_vacunas_pendientes(
        self, mascota_id: int, fecha_referencia: str | None = None
    ) -> list[dict]:
        """
        Calcula las vacunas obligatorias pendientes o vencidas para una mascota.
        Compara las vacunas obligatorias de su especie contra las dosis aplicadas.

        Returns:
            Lista de diccionarios con {vacuna_id, nombre_vacuna, obligatoria, motivo_pendiente, ultima_fecha_aplicacion}.
        """
        mascota = self.obtener_por_id(mascota_id)
        if not mascota:
            return []

        obligatorias = self.obtener_catalogo_vacunas_obligatorias(mascota.especie_id)
        aplicadas = self.listar_vacunas_de_mascota(mascota_id)

        # Mapa de vacunas aplicadas indexadas por vacuna_id -> fecha más reciente
        fechas_ultimas: dict[int, str] = {}
        for va in aplicadas:
            if va.vacuna_id not in fechas_ultimas or va.fecha_aplicacion > fechas_ultimas[va.vacuna_id]:
                fechas_ultimas[va.vacuna_id] = va.fecha_aplicacion

        fecha_ref_str = fecha_referencia or datetime.now().strftime("%Y-%m-%d")
        fecha_ref_dt = datetime.strptime(fecha_ref_str, "%Y-%m-%d")

        pendientes: list[dict] = []
        for vac in obligatorias:
            vid = vac["id"]
            nombre = vac["nombre"]
            frecuencia_meses = vac["frecuencia_refuerzo_meses"] or 12

            if vid not in fechas_ultimas:
                pendientes.append({
                    "vacuna_id": vid,
                    "nombre_vacuna": nombre,
                    "es_obligatoria": True,
                    "motivo_pendiente": "Nunca aplicada",
                    "ultima_fecha_aplicacion": None,
                })
            else:
                ultima_fecha_str = fechas_ultimas[vid]
                ultima_fecha_dt = datetime.strptime(ultima_fecha_str, "%Y-%m-%d")
                dias_transcurridos = (fecha_ref_dt - ultima_fecha_dt).days
                dias_limite = int(frecuencia_meses * 30.4)

                if dias_transcurridos > dias_limite:
                    pendientes.append({
                        "vacuna_id": vid,
                        "nombre_vacuna": nombre,
                        "es_obligatoria": True,
                        "motivo_pendiente": f"Refuerzo vencido (última: {ultima_fecha_str})",
                        "ultima_fecha_aplicacion": ultima_fecha_str,
                    })

        return pendientes

    # ----------------------------------------------------------------------------------
    # Historia Clínica
    # ----------------------------------------------------------------------------------

    def obtener_historia_clinica(self, mascota_id: int) -> HistoriaClinica | None:
        """Recupera la historia clínica de una mascota incluyendo vacunas registradas."""
        sql = """
            SELECT id, mascota_id, fecha_apertura, antecedentes, alergias
            FROM historias_clinicas
            WHERE mascota_id = ?
        """
        fila = self.conexion.consultar_uno(sql, (mascota_id,))
        if not fila:
            return None

        historia = HistoriaClinica(
            id=fila["id"],
            mascota_id=fila["mascota_id"],
            fecha_apertura=fila["fecha_apertura"],
            antecedentes=fila["antecedentes"],
            alergias=fila["alergias"],
            vacunas=self.listar_vacunas_de_mascota(mascota_id),
        )
        return historia

    def actualizar_historia_clinica(
        self, mascota_id: int, antecedentes: str | None, alergias: str | None
    ) -> None:
        """Actualiza los antecedentes y alergias registrados en la historia clínica."""
        sql = """
            UPDATE historias_clinicas
            SET antecedentes = ?, alergias = ?
            WHERE mascota_id = ?
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (
                antecedentes.strip() if antecedentes else None,
                alergias.strip() if alergias else None,
                mascota_id,
            ))

    @staticmethod
    def _mapear_fila(fila: sqlite3.Row) -> Mascota:
        """Mapea una fila de SQLite a un objeto de dominio Mascota."""
        return Mascota(
            id=fila["id"],
            nombre=fila["nombre"],
            especie_id=fila["especie_id"],
            raza=fila["raza"],
            edad=fila["edad"],
            sexo=fila["sexo"],
            cliente_id=fila["cliente_id"],
            nombre_especie=fila["nombre_especie"] if "nombre_especie" in fila.keys() else None,
        )
