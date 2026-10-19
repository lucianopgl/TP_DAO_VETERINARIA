"""
Conexión única a la base de datos SQLite.

Patrón de diseño aplicado: **SINGLETON**
-----------------------------------------
Problema que resuelve (según el material de la cátedra):
    - La clase debe tener una única instancia.
    - Esa instancia debe tener un único punto de acceso.
    - Se utiliza para el acceso a recursos compartidos: aquí, el archivo veterinaria.db.

Solución aplicada:
    - ``__new__`` controla la creación: la primera vez crea el objeto y lo guarda en el
      atributo de clase ``_instancia``; las siguientes veces devuelve el mismo objeto.
    - ``obtener_instancia()`` es el método de clase que funciona como punto de acceso.

Consecuencias:
    + Todos los DAO comparten la misma conexión y, por lo tanto, la misma transacción:
      eso es lo que permite que una operación de varios pasos sea atómica.
    - Es un estado global; para las pruebas se ofrece ``reiniciar_instancia()``.

Unidad de trabajo (transacciones)
---------------------------------
Siguiendo la guía "Acceso a SQLite desde Python": la conexión controla la transacción
(commit / rollback) y el cursor ejecuta las sentencias. El método ``transaccion()`` es un
administrador de contexto que agrupa varias operaciones como una sola unidad:

    conexion = ConexionBD.obtener_instancia()
    with conexion.transaccion() as cursor:
        cursor.execute("UPDATE muestras_biologicas SET estado_actual = ? WHERE id = ?", (...))
        cursor.execute("INSERT INTO historial_estados_muestra (...) VALUES (?, ?, ?, ?, ?)", (...))
    # Si el bloque termina bien  -> commit()   (se confirman los dos cambios).
    # Si ocurre cualquier error  -> rollback() (no se aplica ninguno).

Las transacciones pueden anidarse: si un servicio abre una transacción y llama a varios
DAO que abren la suya, sólo la más externa confirma o deshace. Así un servicio puede
componer operaciones de distintos DAO en una única unidad de trabajo.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.dominio.excepciones import ErrorPersistencia
from src.persistencia.traductor_errores import traducir_error_sqlite

# La base se guarda en la raíz del proyecto: proyecto_veterinaria/veterinaria.db
RUTA_BD_POR_DEFECTO: Path = Path(__file__).resolve().parents[2] / "veterinaria.db"

# Ruta especial de SQLite para una base temporal en memoria (se usa en las pruebas).
RUTA_BD_EN_MEMORIA = ":memory:"


class ConexionBD:
    """
    Única conexión del sistema con la base de datos SQLite (patrón Singleton).

    Uso habitual:
        conexion = ConexionBD.obtener_instancia()
        fila = conexion.consultar_uno("SELECT * FROM clientes WHERE dni = ?", ("30111222",))
    """

    # Atributo de clase que almacena la única instancia.
    _instancia: ConexionBD | None = None

    # ----------------------------------------------------------------------------------
    # Creación y acceso a la instancia única
    # ----------------------------------------------------------------------------------

    def __new__(cls, ruta_bd: str | Path | None = None) -> ConexionBD:
        """
        Crea la instancia la primera vez y la reutiliza en las llamadas siguientes.

        Args:
            ruta_bd: Archivo de la base de datos. Sólo se tiene en cuenta en la primera
                llamada; si se omite se usa ``RUTA_BD_POR_DEFECTO``.

        Raises:
            ErrorPersistencia: Si se pide una ruta distinta a la de la instancia ya creada,
                o si no se puede abrir la base de datos.
        """
        ruta_solicitada = str(ruta_bd) if ruta_bd is not None else None

        if cls._instancia is None:
            instancia = super().__new__(cls)
            instancia._abrir(ruta_solicitada or str(RUTA_BD_POR_DEFECTO))
            cls._instancia = instancia
        elif ruta_solicitada is not None and ruta_solicitada != cls._instancia.ruta_bd:
            raise ErrorPersistencia(
                "La conexión a la base de datos ya fue creada con otro archivo.",
                detalle_tecnico=(
                    f"Ruta actual: {cls._instancia.ruta_bd} / solicitada: {ruta_solicitada}"
                ),
            )
        return cls._instancia

    @classmethod
    def obtener_instancia(cls, ruta_bd: str | Path | None = None) -> ConexionBD:
        """Punto de acceso global a la conexión única (ver ``__new__``)."""
        return cls(ruta_bd)

    @classmethod
    def reiniciar_instancia(cls) -> None:
        """
        Cierra y descarta la instancia actual.

        Pensado para las pruebas unitarias: permite que cada prueba trabaje con una
        base nueva en memoria. La aplicación no necesita llamarlo.
        """
        if cls._instancia is not None:
            cls._instancia.cerrar()
            cls._instancia = None

    def _abrir(self, ruta_bd: str) -> None:
        """
        Abre la conexión y la configura.

        - ``isolation_level=None``: sqlite3 no abre transacciones implícitas; las abrimos
          nosotros explícitamente con BEGIN en ``transaccion()``. Así el inicio y el fin de
          cada unidad de trabajo quedan visibles en el código.
        - ``row_factory = sqlite3.Row``: cada fila se puede leer por posición (como una
          tupla) o por nombre de columna (``fila["dni"]``), lo que simplifica los DAO.
        - ``PRAGMA foreign_keys = ON``: SQLite NO valida las claves foráneas por defecto;
          hay que activarlo en cada conexión.
        """
        try:
            conexion = sqlite3.connect(ruta_bd, isolation_level=None)
            conexion.row_factory = sqlite3.Row
            conexion.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error as error:
            raise ErrorPersistencia(
                f"No se pudo abrir la base de datos '{ruta_bd}'.",
                detalle_tecnico=str(error),
            ) from error

        self._conexion: sqlite3.Connection | None = conexion
        self._ruta_bd = ruta_bd
        # Cantidad de bloques transaccion() abiertos actualmente (para el anidamiento).
        self._profundidad_transaccion = 0
        # Se activa si una transacción interna falló: la externa no podrá confirmar.
        self._solo_deshacer = False

    # ----------------------------------------------------------------------------------
    # Propiedades
    # ----------------------------------------------------------------------------------

    @property
    def ruta_bd(self) -> str:
        """Ruta del archivo de base de datos en uso."""
        return self._ruta_bd

    @property
    def esta_abierta(self) -> bool:
        """Indica si la conexión sigue abierta."""
        return self._conexion is not None

    @property
    def en_transaccion(self) -> bool:
        """Indica si hay una unidad de trabajo en curso."""
        return self._profundidad_transaccion > 0

    # ----------------------------------------------------------------------------------
    # Unidad de trabajo
    # ----------------------------------------------------------------------------------

    @contextmanager
    def transaccion(self) -> Iterator[sqlite3.Cursor]:
        """
        Agrupa varias sentencias en una transacción atómica.

        Yields:
            Cursor para ejecutar las sentencias SQL de la unidad de trabajo.

        Raises:
            ErrorIntegridadDatos: Si el motor rechaza una operación por una restricción.
            ErrorPersistencia: Ante cualquier otro error de base de datos.
            Cualquier otra excepción lanzada dentro del bloque se propaga sin cambios,
            luego de deshacer la transacción.
        """
        conexion = self._obtener_conexion()
        es_externa = self._profundidad_transaccion == 0

        if es_externa:
            self._solo_deshacer = False
            self._ejecutar_control(conexion, "BEGIN")
        self._profundidad_transaccion += 1
        cursor = conexion.cursor()

        try:
            yield cursor
        except sqlite3.Error as error:
            self._finalizar(conexion, es_externa, confirmar=False)
            raise traducir_error_sqlite(error) from error
        except BaseException:
            self._finalizar(conexion, es_externa, confirmar=False)
            raise
        else:
            self._finalizar(conexion, es_externa, confirmar=True)
        finally:
            cursor.close()

    def _finalizar(self, conexion: sqlite3.Connection, es_externa: bool, confirmar: bool) -> None:
        """
        Cierra un nivel de transacción.

        Sólo el nivel externo ejecuta commit() o rollback(). Si un nivel interno falla,
        se marca la transacción como "solo deshacer": aunque el código que la invocó
        capture la excepción y continúe, la transacción externa terminará en rollback.
        """
        self._profundidad_transaccion -= 1

        if not confirmar:
            self._solo_deshacer = True

        if not es_externa:
            return

        if confirmar and not self._solo_deshacer:
            try:
                conexion.commit()
            except sqlite3.Error as error:
                conexion.rollback()
                raise traducir_error_sqlite(error) from error
            return

        conexion.rollback()
        self._solo_deshacer = False
        if confirmar:
            # El bloque externo terminó bien, pero un bloque interno había fallado.
            raise ErrorPersistencia(
                "La operación no se guardó porque uno de sus pasos falló.",
                detalle_tecnico="Transacción marcada como 'solo deshacer' por un nivel interno.",
            )

    @staticmethod
    def _ejecutar_control(conexion: sqlite3.Connection, sentencia: str) -> None:
        """Ejecuta una sentencia de control (BEGIN) traduciendo los errores."""
        try:
            conexion.execute(sentencia)
        except sqlite3.Error as error:
            raise traducir_error_sqlite(error) from error

    # ----------------------------------------------------------------------------------
    # Consultas (SELECT) fuera de una unidad de trabajo
    # ----------------------------------------------------------------------------------

    def consultar_uno(self, sql: str, parametros: Sequence[Any] = ()) -> sqlite3.Row | None:
        """
        Ejecuta un SELECT y devuelve la primera fila, o None si no hay resultados.

        Los valores siempre se pasan como parámetros ``?`` (nunca concatenados en el SQL),
        tal como indica la guía de la cátedra.
        """
        conexion = self._obtener_conexion()
        try:
            return conexion.execute(sql, parametros).fetchone()
        except sqlite3.Error as error:
            raise traducir_error_sqlite(error) from error

    def consultar_todos(self, sql: str, parametros: Sequence[Any] = ()) -> list[sqlite3.Row]:
        """Ejecuta un SELECT y devuelve todas las filas (lista vacía si no hay resultados)."""
        conexion = self._obtener_conexion()
        try:
            return conexion.execute(sql, parametros).fetchall()
        except sqlite3.Error as error:
            raise traducir_error_sqlite(error) from error

    # ----------------------------------------------------------------------------------
    # Scripts DDL
    # ----------------------------------------------------------------------------------

    def ejecutar_script(self, script: str) -> None:
        """
        Ejecuta un script SQL completo (varias sentencias) dentro de una transacción.

        Se usa para crear el esquema. Si una sentencia falla, se deshace todo el script.

        Raises:
            ErrorPersistencia: Si se invoca dentro de ``transaccion()`` (executescript
                confirmaría la transacción en curso) o si el script falla.
        """
        conexion = self._obtener_conexion()
        if self.en_transaccion:
            raise ErrorPersistencia(
                "No se puede ejecutar un script dentro de una transacción en curso."
            )
        try:
            conexion.executescript(f"BEGIN;\n{script}\nCOMMIT;")
        except sqlite3.Error as error:
            if conexion.in_transaction:
                conexion.rollback()
            raise traducir_error_sqlite(error) from error

    # ----------------------------------------------------------------------------------
    # Cierre
    # ----------------------------------------------------------------------------------

    def cerrar(self) -> None:
        """Cierra la conexión. Las llamadas posteriores lanzarán ErrorPersistencia."""
        if self._conexion is not None:
            self._conexion.close()
            self._conexion = None

    def _obtener_conexion(self) -> sqlite3.Connection:
        """Devuelve la conexión abierta o lanza un error si ya fue cerrada."""
        if self._conexion is None:
            raise ErrorPersistencia("La conexión a la base de datos está cerrada.")
        return self._conexion
