"""
Capa de interfaz gráfica.

Pantallas, formularios y eventos construidos con CustomTkinter. Sólo se comunica con la
capa de servicios y muestra al usuario los mensajes de las excepciones del sistema.
"""

from src.interfaz.app import VentanaPrincipal, formatear_evento_notificacion

__all__ = [
    "VentanaPrincipal",
    "formatear_evento_notificacion",
]
