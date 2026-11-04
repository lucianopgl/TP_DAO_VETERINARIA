"""
Vistas modulares de la capa de presentación (CustomTkinter).
"""

from src.interfaz.vistas.vista_clientes import VistaClientes
from src.interfaz.vistas.vista_consultas import VistaConsultas
from src.interfaz.vistas.vista_mascotas import VistaMascotas

__all__ = [
    "VistaClientes",
    "VistaMascotas",
    "VistaConsultas",
]
