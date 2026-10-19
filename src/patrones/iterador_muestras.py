"""
Patrón de diseño: ITERATOR (Iterador)
====================================

Problema que resuelve (según la guía de cátedra UTN FRC):
    Iterator permite recorrer los elementos de una colección sin exponer cómo los
    almacena internamente. En Python, se implementa mediante el protocolo de iteración:
    ``__iter__()`` que devuelve el iterador y ``__next__()`` que devuelve el siguiente
    elemento hasta levantar ``StopIteration``.

Aplicación en el sistema veterinario:
    Una conservadora isotérmica o un remito biológico transporta un conjunto de muestras.
    El iterador permite recorrer las muestras secuencialmente, o recorrer únicamente
    aquellas que cumplan un criterio específico (ej.: muestras viables/aptas para análisis,
    o muestras de un determinado tipo) sin que el cliente acceda directamente a la lista interna.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.dominio.muestra_biologica import MuestraBiologica


class IteradorMuestras:
    """
    Iterador explícito sobre una colección de muestras biológicas.
    Cumple con el protocolo Iterator de Python (__iter__ y __next__).
    """

    def __init__(self, muestras: list[MuestraBiologica]) -> None:
        self._muestras = list(muestras)
        self._posicion = 0

    def __iter__(self) -> IteradorMuestras:
        return self

    def __next__(self) -> MuestraBiologica:
        if self._posicion >= len(self._muestras):
            raise StopIteration
        muestra = self._muestras[self._posicion]
        self._posicion += 1
        return muestra


class IteradorMuestrasFiltradas:
    """
    Iterador con filtro: entrega únicamente las muestras que satisfacen un predicado,
    sin construir listas intermedias en memoria ni exponer la estructura subyacente.
    """

    def __init__(
        self,
        muestras: list[MuestraBiologica],
        filtro: Callable[[MuestraBiologica], bool],
    ) -> None:
        self._muestras = list(muestras)
        self._filtro = filtro
        self._posicion = 0

    def __iter__(self) -> IteradorMuestrasFiltradas:
        return self

    def __next__(self) -> MuestraBiologica:
        while self._posicion < len(self._muestras):
            muestra = self._muestras[self._posicion]
            self._posicion += 1
            if self._filtro(muestra):
                return muestra
        raise StopIteration
