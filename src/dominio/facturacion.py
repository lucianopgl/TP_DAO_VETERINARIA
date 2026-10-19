"""
Entidades de Dominio: Resultados de Análisis y Comprobantes de Atención
======================================================================

Modela la emisión de resultados bioquímicos y la facturación desglosada
en cabecera y detalles para cada consulta médica y sus derivaciones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.dominio.excepciones import ErrorDatosInvalidos


@dataclass
class ResultadoAnalisis:
    """
    Informe técnico-diagnóstico emitido por el laboratorio central.

    Atributos:
        id: Identificador único en BD.
        muestra_id: Muestra biológica analizada.
        profesional_laboratorio_id: Bioquímico firmante.
        valores_medidos: Valores de laboratorio obtenidos (ej: 'Hematocrito 38%, Glucosa 95 mg/dl').
        conclusion: Diagnóstico o apreciación del bioquímico.
        costo_analisis: Arancel final del estudio.
        fecha_hora_analisis: Momento de carga (ISO 'YYYY-MM-DD HH:MM:SS').
        bioquimico_nombre: Nombre legible del profesional para visualización.
    """
    id: int | None
    muestra_id: int
    profesional_laboratorio_id: int
    valores_medidos: str
    conclusion: str
    costo_analisis: float
    fecha_hora_analisis: str
    bioquimico_nombre: str = ""

    def __post_init__(self) -> None:
        if not self.valores_medidos or not self.valores_medidos.strip():
            raise ErrorDatosInvalidos("valores_medidos", "Los valores medidos del análisis no pueden estar vacíos.")
        if not self.conclusion or not self.conclusion.strip():
            raise ErrorDatosInvalidos("conclusion", "La conclusión médica del análisis es obligatoria.")
        if self.costo_analisis < 0:
            raise ErrorDatosInvalidos("costo_analisis", "El costo del análisis no puede ser negativo.")


@dataclass
class DetalleComprobante:
    """
    Ítem individual de la factura o comprobante de atención.

    Atributos:
        id: Identificador único en BD.
        comprobante_id: Comprobante cabecera al que pertenece.
        tipo_concepto: 'Consulta', 'Laboratorio', 'Vacuna', 'Tratamiento', 'Recargo', 'Bonificacion'.
        concepto: Descripción detallada del ítem.
        monto: Importe (positivo para cobros, negativo para bonificaciones).
    """
    id: int | None
    comprobante_id: int | None
    tipo_concepto: str
    concepto: str
    monto: float

    def __post_init__(self) -> None:
        tipos_validos = ("Consulta", "Laboratorio", "Vacuna", "Tratamiento", "Recargo", "Bonificacion")
        if self.tipo_concepto not in tipos_validos:
            raise ErrorDatosInvalidos("tipo_concepto", f"Tipo de concepto '{self.tipo_concepto}' no válido.")
        if not self.concepto or not self.concepto.strip():
            raise ErrorDatosInvalidos("concepto", "El concepto del ítem no puede estar vacío.")


@dataclass
class ComprobanteAtencion:
    """
    Cabecera del comprobante fiscal o recibo de atención de la clínica.

    Atributos:
        id: Identificador único en BD.
        numero_comprobante: Código alfanumérico único (ej: 'FAC-0001-00000123').
        consulta_id: Consulta médica facturada.
        estrategia_tarifa: Nombre de la estrategia de facturación aplicada (Patrón Strategy).
        monto_total: Total liquidado a cobrar.
        fecha_hora_emision: Fecha y hora de emisión (ISO 'YYYY-MM-DD HH:MM:SS').
        detalles: Lista de ítems desagregados.
    """
    id: int | None
    numero_comprobante: str
    consulta_id: int
    estrategia_tarifa: str
    monto_total: float
    fecha_hora_emision: str
    detalles: list[DetalleComprobante] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.numero_comprobante or not self.numero_comprobante.strip():
            raise ErrorDatosInvalidos("numero_comprobante", "El número de comprobante es obligatorio.")
        if self.monto_total < 0:
            raise ErrorDatosInvalidos("monto_total", "El monto total no puede ser negativo.")
