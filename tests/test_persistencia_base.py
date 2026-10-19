"""
Pruebas de la infraestructura de persistencia (Fase 3 - Paso 1).

Verifican:
    - El patrón Singleton de ConexionBD.
    - La creación del esquema y la precarga idempotente.
    - La unidad de trabajo: commit, rollback y anidamiento.
    - La traducción de sqlite3.IntegrityError a mensajes amigables.
    - Las restricciones del esquema que protegen las reglas de negocio.

Cada prueba usa una base nueva en memoria (":memory:"), por lo que no toca veterinaria.db.

Ejecución:  python -m unittest discover -s tests -v
"""

import unittest

from src.dominio.excepciones import ErrorIntegridadDatos, ErrorPersistencia
from src.persistencia.conexion_bd import RUTA_BD_EN_MEMORIA, ConexionBD
from src.persistencia.inicializador_bd import (
    ESPECIES,
    TIPOS_ESTUDIO,
    VACUNAS,
    inicializar_base_datos,
)

TABLAS_ESPERADAS = {
    "catalogo_especies", "catalogo_tipos_muestra", "catalogo_tipos_estudio",
    "catalogo_vacunas", "clinicas", "veterinarios", "laboratorios",
    "profesionales_laboratorio", "transportistas", "clientes", "mascotas",
    "historias_clinicas", "consultas_medicas", "tratamientos", "vacunas_aplicadas",
    "ordenes_derivacion", "conservadoras", "precintos_sanitarios", "remitos_biologicos",
    "historial_estados_remito", "muestras_biologicas", "historial_estados_muestra",
    "envios_laboratorio", "resultados_analisis", "comprobantes", "detalles_comprobante",
}

SQL_INSERTAR_CLIENTE = """
    INSERT INTO clientes (dni, nombre, apellido, telefono, email, direccion)
    VALUES (?, ?, ?, ?, ?, ?)
"""


class PruebaBaseConBD(unittest.TestCase):
    """Clase base: crea una base en memoria inicializada antes de cada prueba."""

    def setUp(self) -> None:
        ConexionBD.reiniciar_instancia()
        self.conexion = inicializar_base_datos(ConexionBD.obtener_instancia(RUTA_BD_EN_MEMORIA))

    def tearDown(self) -> None:
        ConexionBD.reiniciar_instancia()

    # ----- Ayudantes para armar datos de prueba -----

    def insertar_cliente(self, dni: str = "30111222") -> int:
        with self.conexion.transaccion() as cursor:
            cursor.execute(
                SQL_INSERTAR_CLIENTE,
                (dni, "Ana", "López", "351-1234567", "ana@correo.com", "Calle 1"),
            )
            return cursor.lastrowid

    def contar(self, tabla: str) -> int:
        return self.conexion.consultar_uno(f"SELECT COUNT(*) FROM {tabla}")[0]


# ======================================================================================
# Singleton
# ======================================================================================

class PruebaSingleton(PruebaBaseConBD):

    def test_obtener_instancia_devuelve_siempre_el_mismo_objeto(self):
        self.assertIs(ConexionBD.obtener_instancia(), ConexionBD.obtener_instancia())
        self.assertIs(ConexionBD(), self.conexion)

    def test_pedir_otra_ruta_con_instancia_creada_lanza_error(self):
        with self.assertRaises(ErrorPersistencia):
            ConexionBD.obtener_instancia("otra_base.db")

    def test_claves_foraneas_activadas(self):
        self.assertEqual(self.conexion.consultar_uno("PRAGMA foreign_keys")[0], 1)

    def test_conexion_cerrada_lanza_error(self):
        self.conexion.cerrar()
        with self.assertRaises(ErrorPersistencia):
            self.conexion.consultar_todos("SELECT 1")


# ======================================================================================
# Esquema y precarga
# ======================================================================================

class PruebaInicializacion(PruebaBaseConBD):

    def test_se_crean_todas_las_tablas(self):
        filas = self.conexion.consultar_todos(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
        self.assertEqual({fila["name"] for fila in filas}, TABLAS_ESPERADAS)

    def test_precarga_de_catalogos(self):
        self.assertEqual(self.contar("catalogo_especies"), len(ESPECIES))
        self.assertEqual(self.contar("catalogo_tipos_estudio"), len(TIPOS_ESTUDIO))
        self.assertEqual(self.contar("catalogo_vacunas"), len(VACUNAS))
        self.assertGreater(self.contar("profesionales_laboratorio"), 0)

    def test_inicializar_dos_veces_no_duplica_datos(self):
        tablas = ("catalogo_especies", "catalogo_vacunas", "clinicas", "conservadoras")
        antes = {tabla: self.contar(tabla) for tabla in tablas}
        inicializar_base_datos(self.conexion)
        despues = {tabla: self.contar(tabla) for tabla in tablas}
        self.assertEqual(antes, despues)


# ======================================================================================
# Unidad de trabajo
# ======================================================================================

class PruebaTransacciones(PruebaBaseConBD):

    def test_commit_al_terminar_el_bloque_sin_errores(self):
        self.insertar_cliente()
        self.assertEqual(self.contar("clientes"), 1)
        self.assertFalse(self.conexion.en_transaccion)

    def test_rollback_si_el_bloque_lanza_una_excepcion(self):
        with self.assertRaises(ValueError):
            with self.conexion.transaccion() as cursor:
                cursor.execute(
                    SQL_INSERTAR_CLIENTE,
                    ("30111222", "Ana", "López", "351-1234567", None, None),
                )
                raise ValueError("Falla simulada a mitad de la operación")
        self.assertEqual(self.contar("clientes"), 0)

    def test_rollback_deshace_todos_los_pasos_de_la_unidad(self):
        """El segundo INSERT viola el UNIQUE del DNI: el primero tampoco debe quedar."""
        with self.assertRaises(ErrorIntegridadDatos):
            with self.conexion.transaccion() as cursor:
                cursor.execute(SQL_INSERTAR_CLIENTE,
                               ("30111222", "Ana", "López", "351-1", None, None))
                cursor.execute(SQL_INSERTAR_CLIENTE,
                               ("30111222", "Juan", "Pérez", "351-2", None, None))
        self.assertEqual(self.contar("clientes"), 0)

    def test_transaccion_anidada_solo_confirma_la_externa(self):
        with self.conexion.transaccion():
            self.insertar_cliente("30111222")   # abre una transacción interna
            self.insertar_cliente("30333444")
            self.assertTrue(self.conexion.en_transaccion)
        self.assertEqual(self.contar("clientes"), 2)

    def test_falla_interna_capturada_igual_deshace_la_externa(self):
        """Aunque el código capture el error interno, la unidad completa no se guarda."""
        with self.assertRaises(ErrorPersistencia):
            with self.conexion.transaccion():
                self.insertar_cliente("30111222")
                try:
                    self.insertar_cliente("30111222")   # DNI duplicado
                except ErrorIntegridadDatos:
                    pass
        self.assertEqual(self.contar("clientes"), 0)

    def test_no_se_permite_ejecutar_script_dentro_de_una_transaccion(self):
        with self.assertRaises(ErrorPersistencia):
            with self.conexion.transaccion():
                self.conexion.ejecutar_script("SELECT 1;")


# ======================================================================================
# Traducción de errores y restricciones del esquema
# ======================================================================================

class PruebaRestricciones(PruebaBaseConBD):

    def assert_error_integridad(self, sql: str, parametros: tuple, mensaje: str) -> None:
        """Ejecuta el SQL y verifica que se lance ErrorIntegridadDatos con ese mensaje."""
        with self.assertRaises(ErrorIntegridadDatos) as contexto:
            with self.conexion.transaccion() as cursor:
                cursor.execute(sql, parametros)
        self.assertEqual(contexto.exception.mensaje, mensaje)

    def test_dni_duplicado(self):
        self.insertar_cliente("30111222")
        self.assert_error_integridad(
            SQL_INSERTAR_CLIENTE,
            ("30111222", "Juan", "Pérez", "351-2", None, None),
            "Ya existe un cliente registrado con el DNI ingresado.",
        )

    def test_dni_con_letras(self):
        self.assert_error_integridad(
            SQL_INSERTAR_CLIENTE,
            ("30A11222", "Juan", "Pérez", "351-2", None, None),
            "El DNI debe contener solo números (7 u 8 dígitos).",
        )

    def test_mascota_sin_responsable(self):
        self.assert_error_integridad(
            "INSERT INTO mascotas (nombre, especie_id, edad, sexo, cliente_id) "
            "VALUES (?, 1, 3, 'Macho', NULL)",
            ("Firulais",),
            "Toda mascota debe tener un responsable (cliente) asociado.",
        )

    def test_mascota_con_edad_negativa(self):
        cliente_id = self.insertar_cliente()
        self.assert_error_integridad(
            "INSERT INTO mascotas (nombre, especie_id, edad, sexo, cliente_id) "
            "VALUES ('Michi', 2, -1, 'Hembra', ?)",
            (cliente_id,),
            "La edad de la mascota no puede ser negativa.",
        )

    def test_mascota_con_edad_de_tipo_incorrecto_tabla_strict(self):
        cliente_id = self.insertar_cliente()
        with self.assertRaises(ErrorIntegridadDatos) as contexto:
            with self.conexion.transaccion() as cursor:
                cursor.execute(
                    "INSERT INTO mascotas (nombre, especie_id, edad, sexo, cliente_id) "
                    "VALUES ('Michi', 2, 'tres', 'Hembra', ?)",
                    (cliente_id,),
                )
        self.assertEqual(contexto.exception.tipo_restriccion, "TIPO_DATO")

    def test_clave_foranea_inexistente(self):
        with self.assertRaises(ErrorIntegridadDatos) as contexto:
            with self.conexion.transaccion() as cursor:
                cursor.execute(
                    "INSERT INTO mascotas (nombre, especie_id, edad, sexo, cliente_id) "
                    "VALUES ('Rex', 1, 2, 'Macho', 9999)"
                )
        self.assertEqual(contexto.exception.tipo_restriccion, "FOREIGN KEY")

    def test_fecha_con_formato_invalido(self):
        cliente_id = self.insertar_cliente()
        with self.conexion.transaccion() as cursor:
            cursor.execute(
                "INSERT INTO mascotas (nombre, especie_id, edad, sexo, cliente_id) "
                "VALUES ('Rex', 1, 2, 'Macho', ?)", (cliente_id,))
            mascota_id = cursor.lastrowid
        self.assert_error_integridad(
            "INSERT INTO historias_clinicas (mascota_id, fecha_apertura) VALUES (?, ?)",
            (mascota_id, "19/10/2026"),
            "La fecha u hora ingresada no tiene un formato válido "
            "(se espera AAAA-MM-DD o AAAA-MM-DD HH:MM:SS).",
        )

    def test_remito_no_puede_avanzar_sin_precinto(self):
        self.assert_error_integridad(
            "INSERT INTO remitos_biologicos (numero_remito, clinica_origen_id, "
            "laboratorio_destino_id, conservadora_id, estado, fecha_hora_creacion) "
            "VALUES ('R-0001', 1, 1, 1, 'EnTransito', '2026-10-19 10:00:00')",
            (),
            "El remito debe tener un precinto sanitario asignado para avanzar de estado.",
        )


# ======================================================================================
# Trazabilidad de la muestra
# ======================================================================================

class PruebaTrazabilidadMuestra(PruebaBaseConBD):
    """Arma el circuito mínimo cliente -> mascota -> consulta -> orden -> muestra."""

    def setUp(self) -> None:
        super().setUp()
        cliente_id = self.insertar_cliente()
        with self.conexion.transaccion() as cursor:
            cursor.execute(
                "INSERT INTO mascotas (nombre, especie_id, edad, sexo, cliente_id) "
                "VALUES ('Rex', 1, 4, 'Macho', ?)", (cliente_id,))
            mascota_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO consultas_medicas (mascota_id, clinica_id, veterinario_id, "
                "fecha_hora_inicio, motivo) VALUES (?, 1, 1, '2026-10-19 10:00:00', 'Control')",
                (mascota_id,))
            consulta_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO ordenes_derivacion (consulta_id, tipo_estudio_id, "
                "fecha_hora_emision) VALUES (?, 1, '2026-10-19 10:20:00')", (consulta_id,))
            orden_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO muestras_biologicas (codigo_muestra, orden_id, tipo_muestra_id, "
                "fecha_hora_extraccion) VALUES ('M-0001', ?, 1, '2026-10-19 10:25:00')",
                (orden_id,))
            self.muestra_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO historial_estados_muestra (muestra_id, estado_anterior, "
                "estado_nuevo, fecha_hora) VALUES (?, NULL, 'Extraida', '2026-10-19 10:25:00')",
                (self.muestra_id,))

    def test_muestra_extraida_comienza_en_estado_extraida(self):
        fila = self.conexion.consultar_uno(
            "SELECT estado_actual FROM muestras_biologicas WHERE id = ?", (self.muestra_id,))
        self.assertEqual(fila["estado_actual"], "Extraida")

    def test_muestra_no_puede_empaquetarse_sin_remito(self):
        with self.assertRaises(ErrorIntegridadDatos) as contexto:
            with self.conexion.transaccion() as cursor:
                cursor.execute(
                    "UPDATE muestras_biologicas SET estado_actual = 'Empaquetada' WHERE id = ?",
                    (self.muestra_id,))
        self.assertEqual(contexto.exception.restriccion, "ck_muestras_remito_requerido")

    def test_historial_no_se_puede_modificar(self):
        with self.assertRaises(ErrorIntegridadDatos) as contexto:
            with self.conexion.transaccion() as cursor:
                cursor.execute("UPDATE historial_estados_muestra SET estado_nuevo = 'Analizada'")
        self.assertEqual(contexto.exception.tipo_restriccion, "TRIGGER")
        self.assertIn("inmutable", contexto.exception.mensaje)

    def test_historial_no_se_puede_eliminar(self):
        with self.assertRaises(ErrorIntegridadDatos):
            with self.conexion.transaccion() as cursor:
                cursor.execute("DELETE FROM historial_estados_muestra")
        self.assertEqual(self.contar("historial_estados_muestra"), 1)


if __name__ == "__main__":
    unittest.main()
