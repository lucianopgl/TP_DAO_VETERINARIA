"""
Patrón de diseño: OBSERVER (Observador)
======================================

Problema que resuelve (según las diapositivas de cátedra UTN FRC 'Patrones.pdf'):
    - Permite que múltiples objetos se notifiquen ante cambios de estado de otro objeto.
    - Se logra sin herencia y con mínimo acoplamiento (relación 1 a N).
    - El Sujeto (Subject) mantiene la lista de observadores y dispara la notificación.
    - El Observador (Observer) define la interfaz común `actualizar()`.

Casos de uso en el sistema veterinario:
    1. Notificación de Muestra Rechazada: Cuando un precinto llega roto/violado,
       se alerta a la clínica remitente y al responsable para tomar una nueva muestra.
    2. Notificación de Resultados Listos: Cuando el bioquímico carga los resultados,
       se avisa a la clínica y al veterinario solicitante para coordinar el diagnóstico.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Observador(ABC):
    """Interfaz abstracta que deben implementar los suscriptores a eventos."""

    @abstractmethod
    def actualizar(self, tipo_evento: str, datos: dict[str, Any]) -> None:
        """
        Método invocado por el sujeto ante la ocurrencia de un evento de negocio.

        Args:
            tipo_evento: Cadena que describe el suceso ('MUESTRA_RECHAZADA', 'RESULTADO_LISTO', etc.)
            datos: Diccionario con la información relevante del suceso.
        """
        pass


class SujetoEventos:
    """
    Sujeto publicador (Subject): mantiene la colección de observadores suscritos
    y difunde las alertas sin acoplarse a clases concretas.
    """

    def __init__(self) -> None:
        self._observadores: list[Observador] = []

    def suscribir(self, observador: Observador) -> None:
        """Agrega un observador si no estaba ya registrado."""
        if observador not in self._observadores:
            self._observadores.append(observador)

    def desuscribir(self, observador: Observador) -> None:
        """Elimina un observador de la lista de difusión."""
        if observador in self._observadores:
            self._observadores.remove(observador)

    def notificar(self, tipo_evento: str, **datos: Any) -> None:
        """Notifica el evento a todos los observadores registrados."""
        for observador in list(self._observadores):
            observador.actualizar(tipo_evento, datos)


class ObservadorAuditoria(Observador):
    """Observador concreto que registra una bitácora en memoria de todos los eventos."""

    def __init__(self) -> None:
        self.registro_eventos: list[dict[str, Any]] = []

    def actualizar(self, tipo_evento: str, datos: dict[str, Any]) -> None:
        self.registro_eventos.append({"evento": tipo_evento, "datos": dict(datos)})
