"""
Inicialización de la base de datos: creación del esquema y precarga de datos base.

¿Qué se precarga y por qué?
    - Catálogos paramétricos (especies, tipos de muestra, tipos de estudio, vacunas):
      son los valores que el usuario elige en listas desplegables, en lugar de escribirlos.
    - Entidades de la red (clínicas, veterinarios, laboratorio, bioquímicos,
      transportistas y conservadoras): el enunciado no pide administrarlas, pero los
      procesos obligatorios las necesitan para funcionar.

No se precargan clientes ni mascotas: se dan de alta desde la interfaz (Procesos 1 y 2).

Idempotencia:
    Puede ejecutarse muchas veces sin duplicar datos. El esquema usa IF NOT EXISTS y las
    inserciones usan "ON CONFLICT DO NOTHING", que sólo ignora la fila cuando ya existe
    (conflicto de UNIQUE). A diferencia de "INSERT OR IGNORE", no oculta violaciones de
    CHECK o NOT NULL: si un dato de la precarga fuera inválido, el error se informaría.

Ejecución manual desde la raíz del proyecto:

    python -m src.persistencia.inicializador_bd
"""

from __future__ import annotations

from pathlib import Path

from src.persistencia.conexion_bd import ConexionBD

RUTA_ESQUEMA: Path = Path(__file__).with_name("esquema.sql")


# ======================================================================================
# Datos de precarga
# Los importes son valores de referencia para la demostración (en pesos argentinos).
# ======================================================================================

ESPECIES: tuple[tuple[str], ...] = (
    ("Canino",),
    ("Felino",),
    ("Ave",),
    ("Roedor",),
    ("Reptil",),
)

# (codigo, nombre)
TIPOS_MUESTRA: tuple[tuple[str, str], ...] = (
    ("SANGRE", "Sangre entera"),
    ("SUERO", "Suero sanguíneo"),
    ("ORINA", "Orina"),
    ("MATERIA_FECAL", "Materia fecal"),
    ("BIOPSIA", "Tejido / biopsia"),
    ("HISOPADO", "Hisopado"),
)

# (codigo, nombre, costo_base)
TIPOS_ESTUDIO: tuple[tuple[str, str, float], ...] = (
    ("HEMOGRAMA", "Hemograma completo", 18000.0),
    ("PERFIL_BIOQUIMICO", "Perfil bioquímico", 32000.0),
    ("URIANALISIS", "Urianálisis completo", 15000.0),
    ("COPROPARASITOLOGICO", "Coproparasitológico", 12000.0),
    ("CITOLOGIA", "Citología", 25000.0),
    ("HISTOPATOLOGIA", "Histopatología", 45000.0),
    ("CULTIVO_ANTIBIOGRAMA", "Cultivo y antibiograma", 38000.0),
)

# (nombre_vacuna, nombre_especie, es_obligatoria, frecuencia_refuerzo_meses)
VACUNAS: tuple[tuple[str, str, int, int | None], ...] = (
    ("Antirrábica", "Canino", 1, 12),
    ("Séxtuple canina", "Canino", 1, 12),
    ("Tos de las perreras", "Canino", 0, 12),
    ("Antirrábica", "Felino", 1, 12),
    ("Triple felina", "Felino", 1, 12),
    ("Leucemia felina", "Felino", 0, 12),
)

# (nombre, direccion, telefono)
CLINICAS: tuple[tuple[str, str, str], ...] = (
    ("Clínica Veterinaria Centro", "Av. Colón 1250, Córdoba", "351-4210001"),
    ("Clínica Veterinaria Nueva Córdoba", "Bv. Illia 480, Córdoba", "351-4210002"),
    ("Clínica Veterinaria Cerro de las Rosas", "Av. Rafael Núñez 4600, Córdoba", "351-4210003"),
)

# (matricula, nombre, apellido, especialidad)
VETERINARIOS: tuple[tuple[str, str, str, str], ...] = (
    ("MP-1001", "Laura", "Giménez", "Clínica general"),
    ("MP-1002", "Martín", "Sosa", "Cirugía"),
    ("MP-1003", "Carolina", "Ferreyra", "Dermatología"),
    ("MP-1004", "Diego", "Paz", "Clínica de felinos"),
)

# (nombre, direccion, telefono)
LABORATORIOS: tuple[tuple[str, str, str], ...] = (
    ("Laboratorio Central de Diagnóstico Veterinario", "Av. Vélez Sarsfield 2100, Córdoba", "351-4300100"),
)

# (matricula, nombre, apellido, nombre_laboratorio)
PROFESIONALES_LABORATORIO: tuple[tuple[str, str, str, str], ...] = (
    ("BQ-2001", "Valeria", "Ríos", "Laboratorio Central de Diagnóstico Veterinario"),
    ("BQ-2002", "Javier", "Molina", "Laboratorio Central de Diagnóstico Veterinario"),
)

# (nombre, cuit_dni, vehiculo_patente, telefono)
TRANSPORTISTAS: tuple[tuple[str, str, str, str], ...] = (
    ("Logística Sanitaria Córdoba", "30-71234567-8", "AF123BC", "351-5550001"),
    ("BioTraslados SRL", "30-79876543-2", "AE987ZX", "351-5550002"),
)

# (codigo, capacidad_maxima, temperatura_min, temperatura_max)
CONSERVADORAS: tuple[tuple[str, int, float, float], ...] = (
    ("CONS-001", 10, 2.0, 8.0),      # Refrigerada
    ("CONS-002", 20, 2.0, 8.0),      # Refrigerada de mayor capacidad
    ("CONS-003", 6, -20.0, -10.0),   # Congelada (biopsias / muestras especiales)
)


# ======================================================================================
# Funciones públicas
# ======================================================================================

def crear_esquema(conexion: ConexionBD) -> None:
    """Ejecuta esquema.sql: crea tablas, índices y triggers que todavía no existan."""
    script = RUTA_ESQUEMA.read_text(encoding="utf-8")
    conexion.ejecutar_script(script)


def cargar_datos_iniciales(conexion: ConexionBD) -> None:
    """
    Precarga catálogos y entidades de la red en una única unidad de trabajo.

    Si cualquier inserción falla, se deshace la precarga completa.
    """
    with conexion.transaccion() as cursor:
        cursor.executemany(
            "INSERT INTO catalogo_especies (nombre) VALUES (?) ON CONFLICT DO NOTHING",
            ESPECIES,
        )
        cursor.executemany(
            """
            INSERT INTO catalogo_tipos_muestra (codigo, nombre)
            VALUES (?, ?)
            ON CONFLICT DO NOTHING
            """,
            TIPOS_MUESTRA,
        )
        cursor.executemany(
            """
            INSERT INTO catalogo_tipos_estudio (codigo, nombre, costo_base)
            VALUES (?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            TIPOS_ESTUDIO,
        )
        # La especie se busca por nombre para no depender de los id generados.
        cursor.executemany(
            """
            INSERT INTO catalogo_vacunas (nombre, especie_id, es_obligatoria,
                                          frecuencia_refuerzo_meses)
            SELECT ?, id, ?, ?
            FROM catalogo_especies
            WHERE nombre = ?
            ON CONFLICT DO NOTHING
            """,
            [(nombre, obligatoria, frecuencia, especie)
             for nombre, especie, obligatoria, frecuencia in VACUNAS],
        )
        cursor.executemany(
            """
            INSERT INTO clinicas (nombre, direccion, telefono)
            VALUES (?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            CLINICAS,
        )
        cursor.executemany(
            """
            INSERT INTO veterinarios (matricula, nombre, apellido, especialidad)
            VALUES (?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            VETERINARIOS,
        )
        cursor.executemany(
            """
            INSERT INTO laboratorios (nombre, direccion, telefono)
            VALUES (?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            LABORATORIOS,
        )
        cursor.executemany(
            """
            INSERT INTO profesionales_laboratorio (matricula, nombre, apellido, laboratorio_id)
            SELECT ?, ?, ?, id
            FROM laboratorios
            WHERE nombre = ?
            ON CONFLICT DO NOTHING
            """,
            PROFESIONALES_LABORATORIO,
        )
        cursor.executemany(
            """
            INSERT INTO transportistas (nombre, cuit_dni, vehiculo_patente, telefono)
            VALUES (?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            TRANSPORTISTAS,
        )
        cursor.executemany(
            """
            INSERT INTO conservadoras (codigo, capacidad_maxima, temperatura_min, temperatura_max)
            VALUES (?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            CONSERVADORAS,
        )


def inicializar_base_datos(conexion: ConexionBD | None = None) -> ConexionBD:
    """
    Deja la base lista para usar: crea el esquema y precarga los datos base.

    Args:
        conexion: Conexión a utilizar. Si se omite, se usa la instancia única por defecto.

    Returns:
        La conexión utilizada (útil para encadenar en main.py).
    """
    conexion = conexion or ConexionBD.obtener_instancia()
    crear_esquema(conexion)
    cargar_datos_iniciales(conexion)
    return conexion


# ======================================================================================
# Ejecución manual
# ======================================================================================

if __name__ == "__main__":
    conexion_bd = inicializar_base_datos()
    print(f"Base de datos inicializada en: {conexion_bd.ruta_bd}\n")

    tablas = conexion_bd.consultar_todos(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    for tabla in tablas:
        # El nombre de la tabla proviene de sqlite_master (no del usuario), por lo que
        # es seguro incluirlo en el SQL. Los parámetros ? sólo sirven para valores.
        cantidad = conexion_bd.consultar_uno(f"SELECT COUNT(*) FROM {tabla['name']}")[0]
        print(f"  {tabla['name']:<28} {cantidad:>4} registros")

    conexion_bd.cerrar()
