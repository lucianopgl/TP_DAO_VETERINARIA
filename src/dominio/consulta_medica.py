"""
Entidades de Dominio: Consulta Médica y Orden de Derivación
==========================================================

Modela la atención médica veterinaria con soporte para cálculo preciso de
intervalos horarios (prevención de superposición de turnos) y la emisión
de derivaciones hacia laboratorios centrales.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from src.dominio.excepciones import ErrorDatosInvalidos

if TYPE_CHECKING:
    from src.dominio.historia_clinica import Tratamiento
    from src.dominio.muestra_biologica import MuestraBiologica

FORMATO_FECHA_HORA = "%Y-%m-%d %H:%M:%S"


@dataclass
class ConsultaMedica:
    """
    Atención clínica realizada por un veterinario en una sede de la red.

    Atributos:
        id: Identificador único en la BD.
        mascota_id: Paciente atendido.
        clinica_id: Clínica donde se llevó a cabo la consulta.
        veterinario_id: Profesional actuante.
        fecha_hora_inicio: Fecha y hora de inicio (ISO 'YYYY-MM-DD HH:MM:SS').
        duracion_minutos: Tiempo estimado de atención (mínimo 1 minuto, default 30).
        motivo: Causa de la consulta o urgencia.
        diagnostico: Diagnóstico clínico preliminar o definitivo.
        costo_consulta: Arancel cobrado por la clínica veterinaria.
        tratamientos: Lista de tratamientos prescriptos.
        ordenes: Lista de órdenes de derivación a laboratorio emitidas.
    """
    id: int | None
    mascota_id: int
    clinica_id: int
    veterinario_id: int
    fecha_hora_inicio: str
    motivo: str
    duracion_minutos: int = 30
    diagnostico: str | None = None
    costo_consulta: float = 0.0
    tratamientos: list[Tratamiento] = field(default_factory=list)
    ordenes: list[OrdenDerivacion] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validar()

    def validar(self) -> None:
        """Valida los campos obligatorios y rangos numéricos de la consulta."""
        if not self.motivo or not self.motivo.strip():
            raise ErrorDatosInvalidos("motivo", "El motivo de la consulta es obligatorio.")
        self.motivo = self.motivo.strip()

        if self.duracion_minutos <= 0:
            raise ErrorDatosInvalidos("duracion_minutos", "La duración de la consulta debe ser mayor a 0 minutos.")

        if self.costo_consulta < 0:
            raise ErrorDatosInvalidos("costo_consulta", "El costo de la consulta no puede ser negativo.")

        # Valida que la fecha y hora cumpla el formato estricto ISO
        try:
            datetime.strptime(self.fecha_hora_inicio, FORMATO_FECHA_HORA)
        except (ValueError, TypeError):
            raise ErrorDatosInvalidos("fecha_hora_inicio", f"Formato inválido. Se espera '{FORMATO_FECHA_HORA}'.")

    @property
    def inicio_dt(self) -> datetime:
        """Devuelve el inicio como objeto datetime de Python."""
        return datetime.strptime(self.fecha_hora_inicio, FORMATO_FECHA_HORA)

    @property
    def fin_dt(self) -> datetime:
        """Calcula el instante exacto de finalización de la consulta."""
        return self.inicio_dt + timedelta(minutes=self.duracion_minutos)

    @property
    def fecha_hora_fin(self) -> str:
        """Devuelve la fecha y hora de finalización en formato ISO."""
        return self.fin_dt.strftime(FORMATO_FECHA_HORA)

    def se_superpone_con(self, inicio_iso: str, duracion_min: int) -> bool:
        """
        Verifica matemáticamente si esta consulta se solapa en el tiempo con otro turno:
            Inicio_A < Fin_B  y  Fin_A > Inicio_B
        """
        otro_inicio = datetime.strptime(inicio_iso, FORMATO_FECHA_HORA)
        otro_fin = otro_inicio + timedelta(minutes=duracion_min)
        return (self.inicio_dt < otro_fin) and (self.fin_dt > otro_inicio)


@dataclass
class OrdenDerivacion:
    """
    Solicitud formal de estudios complejos derivados al laboratorio central.

    Atributos:
        id: Identificador único en la BD.
        consulta_id: Consulta médica en la que se ordenó.
        tipo_estudio_id: Tipo de estudio del catálogo (Hemograma, Bioquímica, etc.).
        indicaciones: Instrucciones médicas o sospechas diagnósticas.
        prioridad: 'Normal' o 'Urgente'.
        fecha_hora_emision: Momento de emisión (ISO 'YYYY-MM-DD HH:MM:SS').
        nombre_estudio: Nombre legible del estudio para reportes/UI.
        costo_base: Costo arancelario base del estudio.
        muestras: Muestras biológicas extraídas para cumplir esta orden.
    """
    id: int | None
    consulta_id: int
    tipo_estudio_id: int
    fecha_hora_emision: str
    indicaciones: str | None = None
    prioridad: str = "Normal"
    nombre_estudio: str = ""
    costo_base: float = 0.0
    muestras: list[MuestraBiologica] = field(default_factory=list)

    def __post_init__(self) -> None:
        prioridad_limpia = self.prioridad.strip().capitalize() if self.prioridad else ""
        if prioridad_limpia not in ("Normal", "Urgente"):
            raise ErrorDatosInvalidos("prioridad", "La prioridad de la orden debe ser 'Normal' o 'Urgente'.")
        self.prioridad = prioridad_limpia
