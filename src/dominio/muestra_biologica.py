"""
Entidad de Dominio: Muestra Biológica y Trazabilidad Inmutable
=============================================================

Representa la muestra biológica (sangre, orina, tejido, etc.) extraída a un paciente.
Es el núcleo de trazabilidad del sistema e integra el patrón STATE para garantizar
que todas las transiciones respeten la cadena de custodia sanitaria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from src.dominio.excepciones import ErrorDatosInvalidos
from src.patrones.estado_muestra import EstadoMuestra, EstadoExtraida, crear_estado_desde_nombre

if TYPE_CHECKING:
    from src.dominio.logistica import RemitoBiologico
    from src.dominio.facturacion import ResultadoAnalisis


@dataclass(frozen=True)
class RegistroTrazabilidad:
    """
    Entrada inmutable en el historial de trazabilidad de la muestra.
    Al ser frozen=True, ninguna de sus propiedades puede modificarse una vez instanciada.
    """
    id: int | None
    muestra_id: int
    estado_anterior: str | None
    estado_nuevo: str
    fecha_hora: str
    observacion: str | None = None


class MuestraBiologica:
    """
    Muestra extraída sujeta a cadena de frío y custodia de laboratorio.
    Aplica el patrón State: delega las acciones en el objeto de estado actual.
    """

    def __init__(
        self,
        id: int | None,
        codigo_muestra: str,
        orden_id: int,
        tipo_muestra_id: int,
        fecha_hora_extraccion: str,
        remito_id: int | None = None,
        estado_inicial: str = "Extraida",
        motivo_rechazo: str | None = None,
        nombre_tipo_muestra: str = "",
        historial_inicial: list[RegistroTrazabilidad] | None = None,
    ) -> None:
        if not codigo_muestra or not codigo_muestra.strip():
            raise ErrorDatosInvalidos("codigo_muestra", "El código identificador de la muestra es obligatorio.")

        self.id = id
        self.codigo_muestra = codigo_muestra.strip().upper()
        self.orden_id = orden_id
        self.tipo_muestra_id = tipo_muestra_id
        self.fecha_hora_extraccion = fecha_hora_extraccion
        self.remito_id = remito_id
        self.motivo_rechazo = motivo_rechazo
        self.nombre_tipo_muestra = nombre_tipo_muestra
        self.resultado: ResultadoAnalisis | None = None

        # Historial interno (protegido)
        self._historial: list[RegistroTrazabilidad] = list(historial_inicial or [])

        # Estado actual (Patrón State)
        self._estado: EstadoMuestra = crear_estado_desde_nombre(estado_inicial)

        # Si el historial está vacío (muestra recién creada), se registra su extracción inicial
        if not self._historial:
            self._historial.append(RegistroTrazabilidad(
                id=None,
                muestra_id=self.id or 0,
                estado_anterior=None,
                estado_nuevo=self._estado.nombre,
                fecha_hora=fecha_hora_extraccion,
                observacion="Muestra biológica extraída del paciente.",
            ))

    # ----------------------------------------------------------------------------------
    # Propiedades
    # ----------------------------------------------------------------------------------

    @property
    def estado(self) -> EstadoMuestra:
        """Devuelve el objeto de estado polimórfico actual."""
        return self._estado

    @property
    def estado_actual(self) -> str:
        """Devuelve el nombre textual del estado (para la BD y vistas)."""
        return self._estado.nombre

    @property
    def historial(self) -> tuple[RegistroTrazabilidad, ...]:
        """Devuelve una tupla inmutable con todo el historial de trazabilidad."""
        return tuple(self._historial)

    @property
    def esta_viable(self) -> bool:
        """Indica si la muestra sigue apta (no fue rechazada)."""
        return self._estado.nombre != "Rechazada"

    # ----------------------------------------------------------------------------------
    # Transición y Registro de Auditoría
    # ----------------------------------------------------------------------------------

    def cambiar_estado(self, nuevo_estado: EstadoMuestra, fecha_hora: str, observacion: str = "") -> None:
        """
        Reemplaza la referencia de estado y genera el registro inmutable en el historial.
        """
        estado_anterior = self._estado.nombre
        self._estado = nuevo_estado

        registro = RegistroTrazabilidad(
            id=None,
            muestra_id=self.id or 0,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado.nombre,
            fecha_hora=fecha_hora,
            observacion=observacion or None,
        )
        self._historial.append(registro)

    # ----------------------------------------------------------------------------------
    # Métodos delegados en el Patrón State
    # ----------------------------------------------------------------------------------

    def empaquetar(self, remito: RemitoBiologico, fecha_hora: str, observacion: str = "") -> None:
        """Delega en el estado actual la acción de empaquetar."""
        self._estado.empaquetar(self, remito=remito, fecha_hora=fecha_hora, observacion=observacion)

    def despachar(self, fecha_hora: str, observacion: str = "") -> None:
        """Delega en el estado actual la acción de despachar."""
        self._estado.despachar(self, fecha_hora=fecha_hora, observacion=observacion)

    def recibir(self, estado_precinto: str, fecha_hora: str, observacion: str = "") -> None:
        """Delega en el estado actual la recepción y verificación del precinto sanitario."""
        self._estado.recibir(self, estado_precinto=estado_precinto, fecha_hora=fecha_hora, observacion=observacion)

    def analizar(self, resultado: ResultadoAnalisis, fecha_hora: str, observacion: str = "") -> None:
        """Delega en el estado actual la carga del resultado de laboratorio."""
        self._estado.analizar(self, resultado=resultado, fecha_hora=fecha_hora, observacion=observacion)

    def __repr__(self) -> str:
        return f"<MuestraBiologica {self.codigo_muestra} [{self.estado_actual}]>"
