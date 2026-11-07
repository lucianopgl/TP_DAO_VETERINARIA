"""
Capa de persistencia.

Responsabilidades:
    - conexion_bd.py        : única conexión a SQLite (patrón Singleton) y transacciones.
    - esquema.sql           : definición de tablas STRICT, restricciones, índices y triggers.
    - inicializador_bd.py   : creación del esquema y precarga idempotente de catálogos.
    - traductor_errores.py  : conversión de errores de sqlite3 en excepciones amigables.
    - *_dao.py              : objetos de acceso a datos (Patrón DAO).

Ninguna otra capa debe importar sqlite3 directamente.
"""

from src.persistencia.cliente_dao import ClienteDAO
from src.persistencia.conexion_bd import ConexionBD
from src.persistencia.consulta_dao import ConsultaDAO
from src.persistencia.dao_base import DAOBase
from src.persistencia.facturacion_dao import FacturacionDAO
from src.persistencia.logistica_dao import LogisticaDAO
from src.persistencia.mascota_dao import MascotaDAO
from src.persistencia.muestra_dao import MuestraDAO

__all__ = [
    "ConexionBD",
    "DAOBase",
    "ClienteDAO",
    "MascotaDAO",
    "ConsultaDAO",
    "MuestraDAO",
    "LogisticaDAO",
    "FacturacionDAO",
]
