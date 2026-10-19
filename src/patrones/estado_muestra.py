"""
Patrón de diseño: STATE (Estado)
================================

Problema que resuelve (según la guía de cátedra UTN FRC):
    State permite que un objeto modifique su comportamiento según su estado actual.
    Cada estado se representa mediante un objeto con sus propias operaciones. El objeto
    principal (MuestraBiologica) delega la acción al estado vigente mediante polimorfismo:
    ``self._estado.empaquetar(self, ...)``, ``self._estado.recibir(self, ...)``.

Ciclo de vida modelado para la Muestra Biológica:
    
            ┌───────────────┐
            │   Extraída    │
            └───────┬───────┘
                    │ empaquetar(remito)
                    ▼
            ┌───────────────┐
            │  Empaquetada  │
            └───────┬───────┘
                    │ despachar()
                    ▼
            ┌───────────────┐
            │  En Tránsito  │
            └───────┬───────┘
                    │ recibir(estado_precinto)
           ┌────────┴────────┐
   (Intacto)                 (Roto o Violado)
           ▼                 ▼
    ┌──────────────┐  ┌──────────────┐
    │   Recibida   │  │  Rechazada   │ ◄── [FIN: No viable]
    └──────┬───────┘  └──────────────┘
           │ analizar(resultado)
           ▼
    ┌──────────────┐
    │  Analizada   │ ◄── [FIN: Diagnóstico completado]
    └──────────────┘

Reglas de Trazabilidad e Inmutabilidad:
    - Cada cambio de estado genera un registro inmutable en el historial de la muestra.
    - Impedir el procesamiento/análisis si el precinto sanitario llega roto o violado.
    - Cualquier intento de ejecutar una acción no permitida para el estado actual
      lanza `ErrorTransicionEstadoInvalida`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.dominio.excepciones import ErrorTransicionEstadoInvalida, ErrorValidacionNegocio

if TYPE_CHECKING:
    from src.dominio.muestra_biologica import MuestraBiologica
    from src.dominio.logistica import RemitoBiologico
    from src.dominio.facturacion import ResultadoAnalisis


class EstadoMuestra(ABC):
    """
    Clase abstracta base para todos los estados de una muestra biológica.
    
    Define la interfaz común de operaciones que dependen del estado.
    Por defecto, cada método rechaza la operación lanzando `ErrorTransicionEstadoInvalida`,
    de modo que los estados concretos sólo implementan las transiciones válidas.
    """

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre identificatorio del estado (coincide con los valores de la BD)."""
        pass

    def empaquetar(self, muestra: MuestraBiologica, remito: RemitoBiologico, fecha_hora: str, observacion: str = "") -> None:
        """Acción de colocar la muestra dentro de una conservadora asignada a un remito."""
        raise ErrorTransicionEstadoInvalida(self.nombre, "empaquetar en remito")

    def despachar(self, muestra: MuestraBiologica, fecha_hora: str, observacion: str = "") -> None:
        """Acción de despachar la muestra desde la clínica hacia el laboratorio central."""
        raise ErrorTransicionEstadoInvalida(self.nombre, "despachar a transporte")

    def recibir(self, muestra: MuestraBiologica, estado_precinto: str, fecha_hora: str, observacion: str = "") -> None:
        """
        Acción de recibir la muestra en el laboratorio y verificar la integridad del precinto.
        
        Args:
            muestra: La instancia de MuestraBiologica que está cambiando de estado.
            estado_precinto: 'Intacto', 'Roto' o 'Violado'.
            fecha_hora: Marca temporal ISO 'YYYY-MM-DD HH:MM:SS'.
            observacion: Comentarios adicionales de la recepción.
        """
        raise ErrorTransicionEstadoInvalida(self.nombre, "recibir en laboratorio")

    def analizar(self, muestra: MuestraBiologica, resultado: ResultadoAnalisis, fecha_hora: str, observacion: str = "") -> None:
        """Acción de procesar y cargar los resultados analíticos de la muestra."""
        raise ErrorTransicionEstadoInvalida(self.nombre, "analizar muestra")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.nombre}>"


# ======================================================================================
# Estados Concretos
# ======================================================================================

class EstadoExtraida(EstadoMuestra):
    """Estado inicial tras la extracción física de la muestra al paciente."""

    @property
    def nombre(self) -> str:
        return "Extraida"

    def empaquetar(self, muestra: MuestraBiologica, remito: RemitoBiologico, fecha_hora: str, observacion: str = "") -> None:
        """Transición legal: Extraída -> Empaquetada."""
        muestra.remito_id = remito.id
        detalle_obs = f"Empaquetada en remito N° {remito.numero_remito}. {observacion}".strip()
        muestra.cambiar_estado(EstadoEmpaquetada(), fecha_hora=fecha_hora, observacion=detalle_obs)


class EstadoEmpaquetada(EstadoMuestra):
    """La muestra se encuentra debidamente asegurada dentro de una conservadora con remito."""

    @property
    def nombre(self) -> str:
        return "Empaquetada"

    def despachar(self, muestra: MuestraBiologica, fecha_hora: str, observacion: str = "") -> None:
        """Transición legal: Empaquetada -> EnTransito."""
        detalle_obs = f"Despachada hacia laboratorio central. {observacion}".strip()
        muestra.cambiar_estado(EstadoEnTransito(), fecha_hora=fecha_hora, observacion=detalle_obs)


class EstadoEnTransito(EstadoMuestra):
    """La muestra está siendo trasladada por el transportista en la cadena de frío."""

    @property
    def nombre(self) -> str:
        return "EnTransito"

    def recibir(self, muestra: MuestraBiologica, estado_precinto: str, fecha_hora: str, observacion: str = "") -> None:
        """
        Transición legal: EnTransito -> Recibida (si precinto intacto)
                          EnTransito -> Rechazada (si precinto roto o violado)
        """
        estado_limpio = estado_precinto.strip().capitalize()
        
        if estado_limpio == "Intacto":
            detalle_obs = f"Recepción conforme. Precinto sanitario verificado intacto. {observacion}".strip()
            muestra.cambiar_estado(EstadoRecibida(), fecha_hora=fecha_hora, observacion=detalle_obs)
        elif estado_limpio in ("Roto", "Violado"):
            motivo = f"Precinto sanitario {estado_limpio.lower()} en recepción. Cadena de custodia vulnerada."
            if observacion:
                motivo = f"{motivo} Obs: {observacion}"
            muestra.motivo_rechazo = motivo
            muestra.cambiar_estado(EstadoRechazada(), fecha_hora=fecha_hora, observacion=motivo)
        else:
            raise ErrorValidacionNegocio(
                f"Estado de precinto desconocido '{estado_precinto}'. Debe ser 'Intacto', 'Roto' o 'Violado'."
            )


class EstadoRecibida(EstadoMuestra):
    """La muestra fue aceptada en el laboratorio central con precinto intacto y está apta."""

    @property
    def nombre(self) -> str:
        return "Recibida"

    def analizar(self, muestra: MuestraBiologica, resultado: ResultadoAnalisis, fecha_hora: str, observacion: str = "") -> None:
        """Transición legal: Recibida -> Analizada."""
        muestra.resultado = resultado
        detalle_obs = f"Análisis completado satisfactoriamente por {resultado.bioquimico_nombre}. {observacion}".strip()
        muestra.cambiar_estado(EstadoAnalizada(), fecha_hora=fecha_hora, observacion=detalle_obs)


class EstadoAnalizada(EstadoMuestra):
    """Estado terminal exitoso. La muestra fue procesada y cuenta con informe bioquímico."""

    @property
    def nombre(self) -> str:
        return "Analizada"


class EstadoRechazada(EstadoMuestra):
    """
    Estado terminal por falla sanitaria/transporte.
    
    Regla estricta del TP: Se impide el procesamiento de muestras si el precinto sanitario
    llega roto o violado. Ninguna acción posterior es permitida.
    """

    @property
    def nombre(self) -> str:
        return "Rechazada"


# Diccionario mapeador para instanciar el estado correspondiente a partir del texto de la base de datos
MAPA_ESTADOS: dict[str, type[EstadoMuestra]] = {
    "Extraida": EstadoExtraida,
    "Empaquetada": EstadoEmpaquetada,
    "EnTransito": EstadoEnTransito,
    "Recibida": EstadoRecibida,
    "Analizada": EstadoAnalizada,
    "Rechazada": EstadoRechazada,
}


def crear_estado_desde_nombre(nombre_estado: str) -> EstadoMuestra:
    """
    Factoría para reconstruir el objeto EstadoMuestra a partir del valor textual de la BD.
    
    Raises:
        ErrorValidacionNegocio: Si el nombre del estado no existe en el mapa de estados.
    """
    clase_estado = MAPA_ESTADOS.get(nombre_estado)
    if clase_estado is None:
        raise ErrorValidacionNegocio(f"No existe el estado de muestra '{nombre_estado}'.")
    return clase_estado()
