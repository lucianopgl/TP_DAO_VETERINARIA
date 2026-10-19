"""
Entidad de Dominio: Mascota
===========================

Representa a un paciente atendido en las clínicas de la red.
Cumple con la validación de negocio obligatoria:
    "Toda mascota debe tener un responsable asociado".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from src.dominio.excepciones import ErrorDatosInvalidos, ErrorMascotaSinResponsable

if TYPE_CHECKING:
    from src.dominio.cliente import Cliente


@dataclass
class Mascota:
    """
    Entidad de dominio que modela a una mascota / paciente.

    Atributos:
        id: Identificador único en la base de datos (None si es nueva).
        nombre: Nombre de la mascota.
        especie_id: Identificador de la especie en el catálogo.
        edad: Edad cronológica cumplida en años.
        sexo: 'Macho' o 'Hembra'.
        cliente_id: Identificador del cliente responsable (Obligatorio).
        raza: Raza o cruza de la mascota (opcional).
        nombre_especie: Nombre descriptivo de la especie (para visualización).
        cliente: Objeto Cliente asociado (opcional, para navegación).
    """
    id: int | None
    nombre: str
    especie_id: int
    edad: int
    sexo: str
    cliente_id: int
    raza: str | None = None
    nombre_especie: str | None = None
    cliente: Cliente | None = None

    def __post_init__(self) -> None:
        self.validar()

    def validar(self) -> None:
        """Valida las reglas de integridad y negocio de la mascota."""
        if not self.cliente_id:
            raise ErrorMascotaSinResponsable()

        if not self.nombre or not self.nombre.strip():
            raise ErrorDatosInvalidos("nombre", "El nombre de la mascota es obligatorio.")
        self.nombre = self.nombre.strip()

        if self.edad is None or self.edad < 0:
            raise ErrorDatosInvalidos("edad", "La edad de la mascota no puede ser negativa.")

        sexo_limpio = self.sexo.strip().capitalize() if self.sexo else ""
        if sexo_limpio not in ("Macho", "Hembra"):
            raise ErrorDatosInvalidos("sexo", "El sexo de la mascota debe ser 'Macho' o 'Hembra'.")
        self.sexo = sexo_limpio

        if self.raza:
            self.raza = self.raza.strip() or None

    def __str__(self) -> str:
        especie_str = f" ({self.nombre_especie})" if self.nombre_especie else ""
        return f"{self.nombre}{especie_str} - {self.edad} años - {self.sexo}"
