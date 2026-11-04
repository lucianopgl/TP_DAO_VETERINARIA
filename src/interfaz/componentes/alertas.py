"""
Componente Reutilizable: Manejador de Alertas y Excepciones de Interfaz
=======================================================================

Centraliza la presentación de cuadros de diálogo, el resaltado visual de campos
con errores de validación y el protocolo obligatorio de captura de excepciones
tipadas del dominio (`ErrorDatosInvalidos` y `ErrorVeterinaria`).

Principios aplicados:
    - DRY (Don't Repeat Yourself): Evita duplicar bloques try/except y configuración
      de bordes rojos en cada formulario de la aplicación.
    - Bajo Acoplamiento: Sólo depende de la jerarquía de excepciones de `src/dominio/`.
"""

from __future__ import annotations

from collections.abc import Callable
from tkinter import messagebox
from typing import TypeVar

import customtkinter as ctk

from src.dominio.excepciones import ErrorDatosInvalidos, ErrorVeterinaria

T = TypeVar("T")

COLOR_BORDE_ERROR = "#DC2626"
COLOR_BORDE_NORMAL = ("#979DA2", "#565B5E")


def mostrar_exito(titulo: str, mensaje: str) -> None:
    """Muestra un cuadro de diálogo informativo ante una operación exitosa."""
    messagebox.showinfo(titulo, mensaje)


def mostrar_advertencia(titulo: str, mensaje: str) -> None:
    """Muestra un cuadro de diálogo de advertencia al usuario."""
    messagebox.showwarning(titulo, mensaje)


def mostrar_error(titulo: str, mensaje: str) -> None:
    """Muestra un cuadro de diálogo de error amigable para el usuario."""
    messagebox.showerror(titulo, mensaje)


def confirmar_accion(titulo: str, pregunta: str) -> bool:
    """Solicita confirmación booleana (Sí/No) antes de ejecutar una acción crítica."""
    return bool(messagebox.askyesno(titulo, pregunta))


def limpiar_resaltado_campos(mapa_campos: dict[str, ctk.CTkBaseClass] | None) -> None:
    """Restaura el color de borde predeterminado en todos los campos del formulario."""
    if not mapa_campos:
        return
    for widget in mapa_campos.values():
        if hasattr(widget, "configure"):
            try:
                widget.configure(border_color=COLOR_BORDE_NORMAL)
            except Exception:
                pass


def resaltar_campo_invalido(
    mapa_campos: dict[str, ctk.CTkBaseClass] | None,
    nombre_campo: str,
) -> None:
    """
    Resalta con borde rojo el campo específico que originó un `ErrorDatosInvalidos`
    y posiciona el foco del teclado sobre él.
    """
    if not mapa_campos or nombre_campo not in mapa_campos:
        return
    widget = mapa_campos[nombre_campo]
    if hasattr(widget, "configure"):
        try:
            widget.configure(border_color=COLOR_BORDE_ERROR)
        except Exception:
            pass
    if hasattr(widget, "focus_set"):
        try:
            widget.focus_set()
        except Exception:
            pass


def ejecutar_accion_segura(
    accion: Callable[[], T],
    mapa_campos: dict[str, ctk.CTkBaseClass] | None = None,
    titulo_error: str = "Operación no válida",
) -> T | None:
    """
    Ejecuta una acción de negocio capturando de forma estandarizada las excepciones
    de la jerarquía `ErrorVeterinaria`:
        1. Limpia el resaltado previo de campos.
        2. Si ocurre `ErrorDatosInvalidos`, resalta `error.campo` en rojo y muestra `error.mensaje`.
        3. Si ocurre cualquier otra `ErrorVeterinaria` (negocio o persistencia traducida),
           muestra `error.mensaje` al usuario.
    """
    limpiar_resaltado_campos(mapa_campos)
    try:
        return accion()
    except ErrorDatosInvalidos as error:
        resaltar_campo_invalido(mapa_campos, error.campo)
        mostrar_error(
            "Dato inválido en el formulario",
            f"Campo '{error.campo}':\n{error.mensaje}",
        )
        return None
    except ErrorVeterinaria as error:
        mostrar_error(titulo_error, error.mensaje)
        return None
