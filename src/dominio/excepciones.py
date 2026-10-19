"""
Excepciones propias del sistema veterinario.

Todas las excepciones heredan de ``ErrorVeterinaria``. De esta forma la interfaz gráfica
puede capturar una única clase base y mostrar ``error.mensaje`` al usuario, sin conocer
detalles técnicos (sqlite3, nombres de tablas, etc.).

Jerarquía:

    ErrorVeterinaria
    ├── ErrorDatosInvalidos                    (dato de formulario incorrecto)
    ├── ErrorEntidadNoEncontrada               (búsqueda sin resultado)
    ├── ErrorValidacionNegocio                 (violación de una regla del negocio)
    │   ├── ErrorMascotaSinResponsable
    │   ├── ErrorSuperposicionTurno
    │   ├── ErrorVacunaObligatoriaFaltante
    │   ├── ErrorCapacidadConservadoraExcedida
    │   ├── ErrorClinicaNoCoincide
    │   └── ErrorTransicionEstadoInvalida      (usada por el patrón State)
    └── ErrorPersistencia                      (falla al acceder a la base de datos)
        └── ErrorIntegridadDatos               (traducción de sqlite3.IntegrityError)
"""

from __future__ import annotations

from collections.abc import Iterable


class ErrorVeterinaria(Exception):
    """
    Clase base de todas las excepciones del sistema.

    Atributos:
        mensaje: Texto en español, apto para ser mostrado al usuario final.
    """

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


# --------------------------------------------------------------------------------------
# Errores de datos de entrada y búsquedas
# --------------------------------------------------------------------------------------

class ErrorDatosInvalidos(ErrorVeterinaria):
    """
    Un dato ingresado no cumple el formato o rango esperado.

    Se lanza desde el dominio o los servicios, antes de llegar a la base de datos.

    Atributos:
        campo: Nombre del campo del formulario con error (permite resaltarlo en la UI).
    """

    def __init__(self, campo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.campo = campo


class ErrorEntidadNoEncontrada(ErrorVeterinaria):
    """
    No existe la entidad buscada.

    Atributos:
        entidad: Nombre de la entidad buscada (por ejemplo, "Cliente").
        identificador: Valor utilizado en la búsqueda (id, DNI, código...).
    """

    def __init__(self, entidad: str, identificador: object) -> None:
        super().__init__(f"No se encontró {entidad} con identificador '{identificador}'.")
        self.entidad = entidad
        self.identificador = identificador


# --------------------------------------------------------------------------------------
# Errores de reglas de negocio
# --------------------------------------------------------------------------------------

class ErrorValidacionNegocio(ErrorVeterinaria):
    """Clase base para la violación de cualquier regla del negocio veterinario."""


class ErrorMascotaSinResponsable(ErrorValidacionNegocio):
    """Validación obligatoria: toda mascota debe tener un responsable asociado."""

    def __init__(self) -> None:
        super().__init__("Toda mascota debe tener un responsable (cliente) asociado.")


class ErrorSuperposicionTurno(ErrorValidacionNegocio):
    """
    Validación obligatoria: evitar la superposición de turnos en la agenda médica.

    Atributos:
        inicio_conflicto: Fecha y hora de inicio del turno existente que se superpone.
        fin_conflicto: Fecha y hora de finalización de ese turno.
    """

    def __init__(self, inicio_conflicto: str, fin_conflicto: str) -> None:
        super().__init__(
            "El veterinario ya tiene una consulta asignada entre "
            f"{inicio_conflicto} y {fin_conflicto}. Elija otro horario."
        )
        self.inicio_conflicto = inicio_conflicto
        self.fin_conflicto = fin_conflicto


class ErrorVacunaObligatoriaFaltante(ErrorValidacionNegocio):
    """
    Validación obligatoria: controlar el esquema de vacunas al registrar atenciones.

    Atributos:
        vacunas_faltantes: Nombres de las vacunas obligatorias no aplicadas o vencidas.
    """

    def __init__(self, vacunas_faltantes: Iterable[str]) -> None:
        self.vacunas_faltantes = list(vacunas_faltantes)
        super().__init__(
            "La mascota no tiene al día las vacunas obligatorias: "
            + ", ".join(self.vacunas_faltantes)
            + "."
        )


class ErrorCapacidadConservadoraExcedida(ErrorValidacionNegocio):
    """
    Se intentó empaquetar más muestras de las que admite la conservadora isotérmica.

    Atributos:
        capacidad_maxima: Cantidad máxima de muestras que admite la conservadora.
    """

    def __init__(self, capacidad_maxima: int) -> None:
        super().__init__(
            f"La conservadora admite como máximo {capacidad_maxima} muestras."
        )
        self.capacidad_maxima = capacidad_maxima


class ErrorClinicaNoCoincide(ErrorValidacionNegocio):
    """Una muestra no pertenece a la clínica de origen del remito en el que se empaqueta."""

    def __init__(self) -> None:
        super().__init__(
            "La muestra proviene de una clínica distinta a la clínica de origen del remito."
        )


class ErrorTransicionEstadoInvalida(ErrorValidacionNegocio):
    """
    Se solicitó una acción que el estado actual no permite (patrón State).

    Ejemplo: intentar analizar una muestra que todavía está "En tránsito".

    Atributos:
        estado_actual: Nombre del estado en el que se encuentra el objeto.
        accion: Acción que se intentó realizar.
    """

    def __init__(self, estado_actual: str, accion: str) -> None:
        super().__init__(
            f"No es posible '{accion}' cuando el estado actual es '{estado_actual}'."
        )
        self.estado_actual = estado_actual
        self.accion = accion


# --------------------------------------------------------------------------------------
# Errores de persistencia
# --------------------------------------------------------------------------------------

class ErrorPersistencia(ErrorVeterinaria):
    """
    Falla al acceder a la base de datos.

    Atributos:
        detalle_tecnico: Mensaje original del motor (útil para depuración, no para el usuario).
    """

    def __init__(self, mensaje: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(mensaje)
        self.detalle_tecnico = detalle_tecnico


class ErrorIntegridadDatos(ErrorPersistencia):
    """
    La base de datos rechazó la operación por violar una restricción.

    Es la traducción de ``sqlite3.IntegrityError`` a un mensaje amigable.
    Ver ``persistencia/traductor_errores.py``.

    Atributos:
        tipo_restriccion: "UNIQUE", "CHECK", "NOT NULL", "FOREIGN KEY" o "TRIGGER".
        restriccion: Nombre de la restricción o columna involucrada, si se conoce.
    """

    def __init__(
        self,
        mensaje: str,
        tipo_restriccion: str,
        restriccion: str | None = None,
        detalle_tecnico: str | None = None,
    ) -> None:
        super().__init__(mensaje, detalle_tecnico)
        self.tipo_restriccion = tipo_restriccion
        self.restriccion = restriccion
