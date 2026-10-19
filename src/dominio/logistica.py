"""
Entidades de Dominio: Logística de Transporte Seguro
===================================================

Modela conservadoras isotérmicas, precintos sanitarios, remitos biológicos y
envíos en tránsito, garantizando la cadena de frío y custodia de muestras.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.dominio.excepciones import (
    ErrorCapacidadConservadoraExcedida,
    ErrorDatosInvalidos,
    ErrorValidacionNegocio,
)
from src.patrones.iterador_muestras import IteradorMuestras, IteradorMuestrasFiltradas
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from src.dominio.muestra_biologica import MuestraBiologica


@dataclass
class PrecintoSanitario:
    """
    Sello de seguridad inviolable colocado en la conservadora isotérmica.

    Atributos:
        id: Identificador único en la BD.
        numero_serie: Código alfanumérico único e irrepetible.
        estado: 'Intacto', 'Roto' o 'Violado'.
    """
    id: int | None
    numero_serie: str
    estado: str = "Intacto"

    def __post_init__(self) -> None:
        if not self.numero_serie or not self.numero_serie.strip():
            raise ErrorDatosInvalidos("numero_serie", "El número de serie del precinto es obligatorio.")
        self.numero_serie = self.numero_serie.strip().upper()
        self.validar_estado()

    def validar_estado(self) -> None:
        estado_limpio = self.estado.strip().capitalize() if self.estado else ""
        if estado_limpio not in ("Intacto", "Roto", "Violado"):
            raise ErrorDatosInvalidos("estado", "El estado del precinto debe ser 'Intacto', 'Roto' o 'Violado'.")
        self.estado = estado_limpio

    @property
    def esta_intacto(self) -> bool:
        return self.estado == "Intacto"


class ConservadoraIsotermica:
    """
    Contenedor térmico para el transporte de muestras biológicas.
    Aplica el patrón ITERATOR para recorrer sus muestras encapsuladas.
    """

    def __init__(
        self,
        id: int | None,
        codigo: str,
        capacidad_maxima: int,
        temperatura_min: float | None = None,
        temperatura_max: float | None = None,
        disponible: bool = True,
    ) -> None:
        if not codigo or not codigo.strip():
            raise ErrorDatosInvalidos("codigo", "El código de la conservadora es obligatorio.")
        if capacidad_maxima <= 0:
            raise ErrorDatosInvalidos("capacidad_maxima", "La capacidad de la conservadora debe ser mayor a 0.")
        if temperatura_min is not None and temperatura_max is not None and temperatura_min > temperatura_max:
            raise ErrorDatosInvalidos("temperatura", "La temperatura mínima no puede ser mayor que la máxima.")

        self.id = id
        self.codigo = codigo.strip().upper()
        self.capacidad_maxima = int(capacidad_maxima)
        self.temperatura_min = float(temperatura_min) if temperatura_min is not None else None
        self.temperatura_max = float(temperatura_max) if temperatura_max is not None else None
        self.disponible = bool(disponible)
        self._muestras: list[MuestraBiologica] = []

    @property
    def cantidad_muestras(self) -> int:
        return len(self._muestras)

    @property
    def espacio_disponible(self) -> int:
        return max(0, self.capacidad_maxima - len(self._muestras))

    def agregar_muestra(self, muestra: MuestraBiologica) -> None:
        """Agrega una muestra verificando que no se exceda la capacidad máxima física."""
        if len(self._muestras) >= self.capacidad_maxima:
            raise ErrorCapacidadConservadoraExcedida(self.capacidad_maxima)
        if muestra not in self._muestras:
            self._muestras.append(muestra)

    def vaciar(self) -> None:
        """Remueve todas las muestras alojadas."""
        self._muestras.clear()

    # ----------------------------------------------------------------------------------
    # Implementación del Patrón ITERATOR
    # ----------------------------------------------------------------------------------

    def __iter__(self) -> IteradorMuestras:
        """Devuelve un iterador explícito sobre las muestras cargadas."""
        return IteradorMuestras(self._muestras)

    def iterar_viables(self) -> IteradorMuestrasFiltradas:
        """Devuelve un iterador que filtra únicamente las muestras viables (no rechazadas)."""
        return IteradorMuestrasFiltradas(self._muestras, lambda m: m.esta_viable)

    def __repr__(self) -> str:
        return f"<Conservadora {self.codigo} ({self.cantidad_muestras}/{self.capacidad_maxima})>"


@dataclass
class RemitoBiologico:
    """
    Documento legal de traslado sanitario que vincula muestras, conservadora y precinto.

    Estados posibles:
        'EnPreparacion' -> 'Precintado' -> 'EnTransito' -> ('Recibido' | 'Rechazado')
    """
    id: int | None
    numero_remito: str
    clinica_origen_id: int
    laboratorio_destino_id: int
    conservadora_id: int
    fecha_hora_creacion: str
    precinto_id: int | None = None
    estado: str = "EnPreparacion"
    conservadora: ConservadoraIsotermica | None = None
    precinto: PrecintoSanitario | None = None
    muestras: list[MuestraBiologica] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.numero_remito or not self.numero_remito.strip():
            raise ErrorDatosInvalidos("numero_remito", "El número de remito es obligatorio.")
        self.numero_remito = self.numero_remito.strip().upper()
        self.validar_estado()

    def validar_estado(self) -> None:
        estados_validos = ("EnPreparacion", "Precintado", "EnTransito", "Recibido", "Rechazado")
        if self.estado not in estados_validos:
            raise ErrorDatosInvalidos("estado", f"Estado de remito inválido '{self.estado}'.")

    def precintar(self, precinto: PrecintoSanitario) -> None:
        """Asigna y sella el remito con un precinto sanitario intacto."""
        if self.estado != "EnPreparacion":
            raise ErrorValidacionNegocio(f"No se puede precintar un remito en estado '{self.estado}'.")
        if not precinto.esta_intacto:
            raise ErrorValidacionNegocio("No se puede colocar un precinto que no esté intacto.")
        if not self.muestras:
            raise ErrorValidacionNegocio("No se puede precintar un remito sin muestras empaquetadas.")

        self.precinto_id = precinto.id
        self.precinto = precinto
        self.estado = "Precintado"

    def despachar(self) -> None:
        """Avanza el remito al estado EnTransito una vez precintado y cargado en el transporte."""
        if self.estado != "Precintado":
            raise ErrorValidacionNegocio(
                f"No se puede despachar un remito en estado '{self.estado}'. Debe estar 'Precintado'."
            )
        self.estado = "EnTransito"

    def recibir(self, estado_precinto: str) -> None:
        """
        Registra la recepción del remito en el laboratorio central evaluando el precinto.
        Si el precinto está Intacto pasa a 'Recibido'.
        Si el precinto está Roto o Violado pasa a 'Rechazado'.
        """
        if self.estado != "EnTransito":
            raise ErrorValidacionNegocio(
                f"No se puede recibir un remito en estado '{self.estado}'. Debe estar 'EnTransito'."
            )
        estado_limpio = estado_precinto.strip().capitalize() if estado_precinto else ""
        if estado_limpio == "Intacto":
            self.estado = "Recibido"
        elif estado_limpio in ("Roto", "Violado"):
            self.estado = "Rechazado"
        else:
            raise ErrorValidacionNegocio(
                f"Estado de precinto desconocido '{estado_precinto}'. Debe ser 'Intacto', 'Roto' o 'Violado'."
            )


@dataclass
class EnvioLaboratorio:
    """
    Registro del transporte físico desde la clínica origen hacia el laboratorio.
    """
    id: int | None
    remito_id: int
    transportista_id: int
    fecha_hora_despacho: str
    fecha_hora_recepcion: str | None = None
    observaciones_recepcion: str | None = None
