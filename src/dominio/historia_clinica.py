"""
Entidades de Dominio: Historia Clínica, Tratamiento y Vacunación
===============================================================

Gestiona los antecedentes médicos de la mascota, sus tratamientos prescriptos
y su esquema de vacunación obligatoria y optativa.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from src.dominio.excepciones import ErrorDatosInvalidos

DIAS_PROMEDIO_POR_MES: float = 30.4


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
        self.validar()

    def validar(self) -> None:
        """Valida los datos obligatorios de la aplicación de vacuna."""
        if not self.fecha_aplicacion or not str(self.fecha_aplicacion).strip():
            raise ErrorDatosInvalidos("fecha_aplicacion", "La fecha de aplicación de la vacuna es obligatoria.")
        self.fecha_aplicacion = self.fecha_aplicacion.strip()


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
        self.validar()

    def validar(self) -> None:
        """Valida los campos del tratamiento prescripto."""
        if not self.descripcion or not self.descripcion.strip():
            raise ErrorDatosInvalidos("descripcion", "La descripción del tratamiento no puede estar vacía.")
        self.descripcion = self.descripcion.strip()
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

    def __post_init__(self) -> None:
        self.validar()

    def validar(self) -> None:
        """Valida los datos base de apertura de la historia clínica."""
        if not self.fecha_apertura or not self.fecha_apertura.strip():
            raise ErrorDatosInvalidos("fecha_apertura", "La fecha de apertura de la historia clínica es obligatoria.")
        self.fecha_apertura = self.fecha_apertura.strip()

    def calcular_vacunas_pendientes(
        self,
        catalogo_obligatorias: Iterable[dict],
        fecha_referencia: str | None = None,
    ) -> list[dict]:
        """
        Regla de dominio (Experto en Información):
        Evalúa qué vacunas obligatorias del catálogo nunca fueron aplicadas o tienen
        su refuerzo vencido respecto a las vacunas registradas en esta historia clínica.

        Args:
            catalogo_obligatorias: Vacunas obligatorias para la especie de la mascota.
            fecha_referencia: Fecha ISO 'YYYY-MM-DD' de control (por defecto hoy).

        Returns:
            Lista de diccionarios con el detalle de cada vacuna pendiente o vencida.
        """
        fechas_ultimas: dict[int, str] = {}
        for va in self.vacunas:
            if va.vacuna_id not in fechas_ultimas or va.fecha_aplicacion > fechas_ultimas[va.vacuna_id]:
                fechas_ultimas[va.vacuna_id] = va.fecha_aplicacion

        fecha_ref_str = fecha_referencia or datetime.now().strftime("%Y-%m-%d")
        fecha_ref_dt = datetime.strptime(fecha_ref_str, "%Y-%m-%d")

        pendientes: list[dict] = []
        for vac in catalogo_obligatorias:
            vid = vac["id"]
            nombre = vac["nombre"]
            frecuencia_meses = vac.get("frecuencia_refuerzo_meses") or 12

            if vid not in fechas_ultimas:
                pendientes.append({
                    "vacuna_id": vid,
                    "nombre_vacuna": nombre,
                    "es_obligatoria": True,
                    "motivo_pendiente": "Nunca aplicada",
                    "ultima_fecha_aplicacion": None,
                })
            else:
                ultima_fecha_str = fechas_ultimas[vid]
                ultima_fecha_dt = datetime.strptime(ultima_fecha_str, "%Y-%m-%d")
                dias_transcurridos = (fecha_ref_dt - ultima_fecha_dt).days
                dias_limite = int(frecuencia_meses * DIAS_PROMEDIO_POR_MES)

                if dias_transcurridos > dias_limite:
                    pendientes.append({
                        "vacuna_id": vid,
                        "nombre_vacuna": nombre,
                        "es_obligatoria": True,
                        "motivo_pendiente": f"Refuerzo vencido (última: {ultima_fecha_str})",
                        "ultima_fecha_aplicacion": ultima_fecha_str,
                    })

        return pendientes
