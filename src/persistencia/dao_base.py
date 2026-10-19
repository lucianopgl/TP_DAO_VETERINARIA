"""
Capa de Persistencia: Clase Base DAO
====================================

Patrón de diseño: DATA ACCESS OBJECT (DAO)
------------------------------------------
Separa la lógica de negocio de los detalles de acceso a la base de datos relacional.
Ningún objeto de dominio ni de la interfaz gráfica contiene código SQL: todos se
comunican a través de los DAO concretos.

Esta clase base proporciona la referencia a la conexión Singleton y métodos de
utilidad para la ejecución de consultas y transacciones atómicas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from src.persistencia.conexion_bd import ConexionBD

if TYPE_CHECKING:
    import sqlite3


class DAOBase:
    """
    Clase abstracta/base para todos los Objetos de Acceso a Datos.

    Atributos:
        conexion: Instancia de ConexionBD utilizada para interactuar con SQLite.
    """

    def __init__(self, conexion: ConexionBD | None = None) -> None:
        """
        Permite inyectar una conexión específica (útil para pruebas unitarias en memoria)
        o utilizar la instancia Singleton global por defecto.
        """
        self.conexion = conexion or ConexionBD.obtener_instancia()

    @property
    def cursor_transaccional(self):
        """Atajo al context manager transaccional de la conexión."""
        return self.conexion.transaccion()
