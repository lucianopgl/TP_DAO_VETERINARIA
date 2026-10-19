"""
Capa de persistencia.

Responsabilidades:
    - conexion_bd.py        : única conexión a SQLite (patrón Singleton) y transacciones.
    - esquema.sql           : definición de tablas, restricciones, índices y triggers.
    - inicializador_bd.py   : creación del esquema y precarga de catálogos.
    - traductor_errores.py  : conversión de errores de sqlite3 en excepciones amigables.
    - *_dao.py              : objetos de acceso a datos (se agregan en pasos posteriores).

Ninguna otra capa debe importar sqlite3 directamente.
"""
