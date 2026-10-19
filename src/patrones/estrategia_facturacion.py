"""
Patrón de diseño: STRATEGY (Estrategia)
======================================

Problema que resuelve (según la guía de cátedra UTN FRC):
    Cuando una operación admite varias maneras de calcularse, Strategy permite
    encapsular cada algoritmo en una clase intercambiable. La clase que utiliza el
    algoritmo no necesita conocer cuál es la estrategia concreta.
    En lugar de utilizar if/elif para cada tipo de liquidación o tarifa, recibe un
    objeto estrategia que implementa una interfaz polimórfica común.

Estrategias de Facturación implementadas:
    1. TarifaEstandar: Suma directa de la consulta clínica y los estudios solicitados.
    2. TarifaUrgenciaLaboratorio: Aplica un recargo prioritario (ej. +30%) sobre los
       estudios de laboratorio para derivaciones de urgencia procesadas en guardia.
    3. TarifaConvenioRed: Aplica una bonificación institucional (ej. 15% de descuento)
       para clientes adheridos al programa de red de clínicas veterinarias.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ItemFactura:
    """Representa un ítem desagregado del comprobante de atención."""
    tipo_concepto: str  # 'Consulta', 'Laboratorio', 'Recargo', 'Bonificacion'
    concepto: str
    monto: float


@dataclass
class LiquidacionFactura:
    """Resultado del cálculo polimórfico realizado por la estrategia."""
    nombre_estrategia: str
    subtotal_clinica: float
    subtotal_laboratorio: float
    items: list[ItemFactura] = field(default_factory=list)
    total: float = 0.0


class EstrategiaFacturacion(ABC):
    """
    Interfaz abstracta para el cálculo del comprobante de atención.
    """

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre identificatorio de la estrategia (guardado en el comprobante)."""
        pass

    @abstractmethod
    def liquidar(
        self,
        costo_consulta: float,
        costos_laboratorio: list[tuple[str, float]],
        motivo_consulta: str = "Consulta médica veterinaria",
    ) -> LiquidacionFactura:
        """
        Calcula el desglose y el monto total de la atención médica y sus derivaciones.

        Args:
            costo_consulta: Arancel base de la consulta médica en la clínica.
            costos_laboratorio: Lista de tuplas (nombre_estudio, costo) derivados.
            motivo_consulta: Descripción o motivo de la consulta.

        Returns:
            LiquidacionFactura con todos los ítems detallados y el monto total.
        """
        pass


class TarifaEstandar(EstrategiaFacturacion):
    """Liquidación estándar sin recargos ni bonificaciones especiales."""

    @property
    def nombre(self) -> str:
        return "Tarifa Estándar"

    def liquidar(
        self,
        costo_consulta: float,
        costos_laboratorio: list[tuple[str, float]],
        motivo_consulta: str = "Consulta médica veterinaria",
    ) -> LiquidacionFactura:
        items: list[ItemFactura] = []
        subtotal_clinica = max(0.0, float(costo_consulta))
        items.append(ItemFactura(tipo_concepto="Consulta", concepto=motivo_consulta, monto=subtotal_clinica))

        subtotal_lab = 0.0
        for nombre_estudio, costo in costos_laboratorio:
            monto_estudio = max(0.0, float(costo))
            subtotal_lab += monto_estudio
            items.append(ItemFactura(tipo_concepto="Laboratorio", concepto=f"Análisis: {nombre_estudio}", monto=monto_estudio))

        total = subtotal_clinica + subtotal_lab
        return LiquidacionFactura(
            nombre_estrategia=self.nombre,
            subtotal_clinica=subtotal_clinica,
            subtotal_laboratorio=subtotal_lab,
            items=items,
            total=round(total, 2),
        )


class TarifaUrgenciaLaboratorio(EstrategiaFacturacion):
    """
    Aplica un recargo por urgencia (por defecto 30%) exclusivamente sobre los
    servicios de laboratorio derivados con carácter urgente.
    """

    def __init__(self, porcentaje_recargo: float = 30.0) -> None:
        self.porcentaje_recargo = max(0.0, float(porcentaje_recargo))

    @property
    def nombre(self) -> str:
        return f"Tarifa Urgencia (+{int(self.porcentaje_recargo)}% Lab)"

    def liquidar(
        self,
        costo_consulta: float,
        costos_laboratorio: list[tuple[str, float]],
        motivo_consulta: str = "Consulta médica veterinaria (Urgencia)",
    ) -> LiquidacionFactura:
        items: list[ItemFactura] = []
        subtotal_clinica = max(0.0, float(costo_consulta))
        items.append(ItemFactura(tipo_concepto="Consulta", concepto=motivo_consulta, monto=subtotal_clinica))

        subtotal_lab_base = 0.0
        for nombre_estudio, costo in costos_laboratorio:
            monto_estudio = max(0.0, float(costo))
            subtotal_lab_base += monto_estudio
            items.append(ItemFactura(tipo_concepto="Laboratorio", concepto=f"Análisis urgente: {nombre_estudio}", monto=monto_estudio))

        recargo = round(subtotal_lab_base * (self.porcentaje_recargo / 100.0), 2)
        if recargo > 0:
            items.append(ItemFactura(
                tipo_concepto="Recargo",
                concepto=f"Recargo Guardia / Urgencia de Laboratorio ({int(self.porcentaje_recargo)}%)",
                monto=recargo,
            ))

        subtotal_lab_final = subtotal_lab_base + recargo
        total = subtotal_clinica + subtotal_lab_final
        return LiquidacionFactura(
            nombre_estrategia=self.nombre,
            subtotal_clinica=subtotal_clinica,
            subtotal_laboratorio=subtotal_lab_final,
            items=items,
            total=round(total, 2),
        )


class TarifaConvenioRed(EstrategiaFacturacion):
    """
    Aplica una bonificación del convenio institucional de la Red de Clínicas
    (por defecto 15%) sobre el servicio clínico.
    """

    def __init__(self, porcentaje_descuento: float = 15.0) -> None:
        self.porcentaje_descuento = max(0.0, min(100.0, float(porcentaje_descuento)))

    @property
    def nombre(self) -> str:
        return f"Tarifa Convenio Red (-{int(self.porcentaje_descuento)}% Clínica)"

    def liquidar(
        self,
        costo_consulta: float,
        costos_laboratorio: list[tuple[str, float]],
        motivo_consulta: str = "Consulta médica veterinaria",
    ) -> LiquidacionFactura:
        items: list[ItemFactura] = []
        subtotal_clinica_bruto = max(0.0, float(costo_consulta))
        items.append(ItemFactura(tipo_concepto="Consulta", concepto=motivo_consulta, monto=subtotal_clinica_bruto))

        descuento = round(subtotal_clinica_bruto * (self.porcentaje_descuento / 100.0), 2)
        if descuento > 0:
            items.append(ItemFactura(
                tipo_concepto="Bonificacion",
                concepto=f"Bonificación Convenio Red Veterinaria ({int(self.porcentaje_descuento)}%)",
                monto=-descuento,
            ))

        subtotal_lab = 0.0
        for nombre_estudio, costo in costos_laboratorio:
            monto_estudio = max(0.0, float(costo))
            subtotal_lab += monto_estudio
            items.append(ItemFactura(tipo_concepto="Laboratorio", concepto=f"Análisis: {nombre_estudio}", monto=monto_estudio))

        subtotal_clinica_neto = max(0.0, subtotal_clinica_bruto - descuento)
        total = subtotal_clinica_neto + subtotal_lab
        return LiquidacionFactura(
            nombre_estrategia=self.nombre,
            subtotal_clinica=subtotal_clinica_neto,
            subtotal_laboratorio=subtotal_lab,
            items=items,
            total=round(total, 2),
        )


MAPA_ESTRATEGIAS: dict[str, type[EstrategiaFacturacion]] = {
    "Tarifa Estándar": TarifaEstandar,
    "Tarifa Urgencia": TarifaUrgenciaLaboratorio,
    "Tarifa Convenio Red": TarifaConvenioRed,
}
