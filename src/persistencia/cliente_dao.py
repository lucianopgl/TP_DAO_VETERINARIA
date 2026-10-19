"""
Capa de Persistencia: ClienteDAO
================================

Implementa las operaciones de persistencia (ABMC) para la entidad Cliente:
    - Crear (Alta)
    - Obtener por ID o DNI (Consulta)
    - Listar y Buscar (Consulta)
    - Actualizar (Modificación)
    - Eliminar (Baja)
"""

from __future__ import annotations

import sqlite3
from typing import Any
from src.dominio.cliente import Cliente
from src.persistencia.dao_base import DAOBase


class ClienteDAO(DAOBase):
    """Objeto de Acceso a Datos para la tabla `clientes`."""

    def crear(self, cliente: Cliente) -> int:
        """
        Inserta un nuevo cliente en la base de datos.
        
        Returns:
            El id autoincremental asignado al cliente.
        """
        cliente.validar()
        sql = """
            INSERT INTO clientes (dni, nombre, apellido, telefono, email, direccion)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (
                cliente.dni,
                cliente.nombre,
                cliente.apellido,
                cliente.telefono,
                cliente.email,
                cliente.direccion,
            ))
            cliente_id = cursor.lastrowid
            cliente.id = cliente_id
            return cliente_id

    def actualizar(self, cliente: Cliente) -> None:
        """Actualiza los datos personales y de contacto de un cliente existente."""
        if cliente.id is None:
            raise ValueError("No se puede actualizar un cliente sin ID.")
        cliente.validar()
        sql = """
            UPDATE clientes
            SET dni = ?, nombre = ?, apellido = ?, telefono = ?, email = ?, direccion = ?
            WHERE id = ?
        """
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (
                cliente.dni,
                cliente.nombre,
                cliente.apellido,
                cliente.telefono,
                cliente.email,
                cliente.direccion,
                cliente.id,
            ))

    def eliminar(self, cliente_id: int) -> None:
        """Elimina un cliente de la base de datos por su ID."""
        sql = "DELETE FROM clientes WHERE id = ?"
        with self.conexion.transaccion() as cursor:
            cursor.execute(sql, (cliente_id,))

    def obtener_por_id(self, cliente_id: int) -> Cliente | None:
        """Busca un cliente por su clave primaria."""
        sql = "SELECT id, dni, nombre, apellido, telefono, email, direccion FROM clientes WHERE id = ?"
        fila = self.conexion.consultar_uno(sql, (cliente_id,))
        return self._mapear_fila(fila) if fila else None

    def obtener_por_dni(self, dni: str) -> Cliente | None:
        """Busca un cliente por su número de DNI único."""
        sql = "SELECT id, dni, nombre, apellido, telefono, email, direccion FROM clientes WHERE dni = ?"
        fila = self.conexion.consultar_uno(sql, (dni.strip(),))
        return self._mapear_fila(fila) if fila else None

    def listar_todos(self) -> list[Cliente]:
        """Obtiene la lista completa de clientes ordenados alfabéticamente."""
        sql = "SELECT id, dni, nombre, apellido, telefono, email, direccion FROM clientes ORDER BY apellido, nombre"
        filas = self.conexion.consultar_todos(sql)
        return [self._mapear_fila(f) for f in filas]

    def buscar(self, termino: str) -> list[Cliente]:
        """Busca clientes por coincidencia en DNI, apellido o nombre."""
        termino_like = f"%{termino.strip()}%"
        sql = """
            SELECT id, dni, nombre, apellido, telefono, email, direccion
            FROM clientes
            WHERE dni LIKE ? OR nombre LIKE ? OR apellido LIKE ?
            ORDER BY apellido, nombre
        """
        filas = self.conexion.consultar_todos(sql, (termino_like, termino_like, termino_like))
        return [self._mapear_fila(f) for f in filas]

    @staticmethod
    def _mapear_fila(fila: sqlite3.Row) -> Cliente:
        """Mapea una fila de SQLite a un objeto de dominio Cliente."""
        return Cliente(
            id=fila["id"],
            dni=fila["dni"],
            nombre=fila["nombre"],
            apellido=fila["apellido"],
            telefono=fila["telefono"],
            email=fila["email"],
            direccion=fila["direccion"],
        )
