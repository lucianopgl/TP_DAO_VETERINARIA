"""
Capa de Persistencia: MascotaDAO
================================

Implementa las operaciones de persistencia para Mascotas, Historias Clínicas
y Registro de Vacunación.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from src.dominio.excepciones import ErrorDatosInvalidos
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
            fecha_apertura = fecha_apertura_historia or datetime.now().strftime("%Y-%m-%d")
            cursor.execute(sql_historia, (mascota_id, fecha_apertura))
            return mascota_id

    def actualizar(self, mascota: Mascota) -> None:
        """Actualiza los datos de la mascota."""
        if mascota.id is None:
            raise ErrorDatosInvalidos("id", "No se puede actualizar una mascota sin ID.")
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
        vacuna.validar()
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

    def listar_especies(self) -> list[dict]:
        """Devuelve el catálogo paramétrico de especies animales."""
        filas = self.conexion.consultar_todos(
            "SELECT id, nombre FROM catalogo_especies ORDER BY id"
        )
        return [dict(f) for f in filas]

    def listar_catalogo_vacunas(self, especie_id: int | None = None) -> list[dict]:
        """Devuelve el catálogo de vacunas (opcionalmente filtrado por especie)."""
        if especie_id is not None:
            filas = self.conexion.consultar_todos(
                "SELECT id, nombre, especie_id, es_obligatoria, frecuencia_refuerzo_meses "
                "FROM catalogo_vacunas WHERE especie_id = ? ORDER BY es_obligatoria DESC, nombre",
                (especie_id,),
            )
        else:
            filas = self.conexion.consultar_todos(
                "SELECT id, nombre, especie_id, es_obligatoria, frecuencia_refuerzo_meses "
                "FROM catalogo_vacunas ORDER BY especie_id, es_obligatoria DESC, nombre"
            )
        return [dict(f) for f in filas]

    def obtener_vacunas_pendientes(
        self, mascota_id: int, fecha_referencia: str | None = None
    ) -> list[dict]:
        """
        Recupera los datos de vacunación de la mascota y delega el cálculo de
        vencimientos/faltantes en la entidad de dominio `HistoriaClinica`
        (Principio Experto en Información y SRP).
        """
        mascota = self.obtener_por_id(mascota_id)
        if not mascota:
            return []

        obligatorias = self.obtener_catalogo_vacunas_obligatorias(mascota.especie_id)
        historia = self.obtener_historia_clinica(mascota_id) or HistoriaClinica(
            id=None,
            mascota_id=mascota_id,
            fecha_apertura=datetime.now().strftime("%Y-%m-%d"),
            vacunas=self.listar_vacunas_de_mascota(mascota_id),
        )
        return historia.calcular_vacunas_pendientes(
            catalogo_obligatorias=obligatorias,
            fecha_referencia=fecha_referencia,
        )

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
