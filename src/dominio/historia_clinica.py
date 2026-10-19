"""
Entidades de Dominio: Historia Clínica, Tratamiento y Vacunación
===============================================================

Gestiona los antecedentes médicos de la mascota, sus tratamientos prescriptos
y su esquema de vacunación obligatoria y optativa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.dominio.excepciones import ErrorDatosInvalidos


@dataclass
class VacunaAplicada:
    """
    Registro histórico de una vacuna administrada a un paciente.

    Atributos:
        id: Identificador único en BD.
        mascota_id: Paciente receptor.
        vacuna_id: Identificador en el catálogo de vacunas.
        fecha_aplicacion: Fecha en formato ISO 'YYYY-MM-DD'.
        nombre_vacuna: Nombre de la vacuna (para visualización y reportes).
        es_obligatoria: Indica si la vacuna forma parte del plan sanitario legal.
        consulta_id: Consulta médica en la que se aplicó (opcional si es externa).
    """
    id: int | None
    mascota_id: int
    vacuna_id: int
    fecha_aplicacion: str
    nombre_vacuna: str = ""
    es_obligatoria: bool = False
    consulta_id: int | None = None

    def __post_init__(self) -> None:
        if not self.fecha_aplicacion:
            raise ErrorDatosInvalidos("fecha_aplicacion", "La fecha de aplicación de la vacuna es obligatoria.")


@dataclass
class Tratamiento:
    """
    Tratamiento o indicación terapéutica prescripta durante una consulta médica.

    Atributos:
        id: Identificador único en BD.
        consulta_id: Consulta donde se indicó.
        descripcion: Detalle clínico del tratamiento.
        medicamento: Nombre comercial o droga indicada.
        dosis: Posología (ej.: '1 comprimido cada 12 hs').
        duracion_dias: Días de duración del tratamiento (debe ser mayor a 0).
    """
    id: int | None
    consulta_id: int
    descripcion: str
    medicamento: str | None = None
    dosis: str | None = None
    duracion_dias: int | None = None

    def __post_init__(self) -> None:
        if not self.descripcion or not self.descripcion.strip():
            raise ErrorDatosInvalidos("descripcion", "La descripción del tratamiento no puede estar vacía.")
        if self.duracion_dias is not None and self.duracion_dias <= 0:
            raise ErrorDatosInvalidos("duracion_dias", "La duración del tratamiento debe ser mayor a 0 días.")


@dataclass
class HistoriaClinica:
    """
    Carpeta médica integral del paciente veterinario.

    Atributos:
        id: Identificador único en BD.
        mascota_id: Paciente al que pertenece.
        fecha_apertura: Fecha de alta de la historia (ISO 'YYYY-MM-DD').
        antecedentes: Antecedentes clínicos o quirúrgicos de relevancia.
        alergias: Alergias o intolerancias conocidas.
        vacunas: Lista de vacunas registradas.
        tratamientos: Lista de tratamientos históricos.
    """
    id: int | None
    mascota_id: int
    fecha_apertura: str
    antecedentes: str | None = None
    alergias: str | None = None
    vacunas: list[VacunaAplicada] = field(default_factory=list)
    tratamientos: list[Tratamiento] = field(default_factory=list)
