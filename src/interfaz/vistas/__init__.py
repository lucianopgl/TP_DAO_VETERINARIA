"""
Vistas modulares de la capa de presentación (CustomTkinter).
"""

from src.interfaz.vistas.vista_clientes import VistaClientes
from src.interfaz.vistas.vista_consultas import VistaConsultas
from src.interfaz.vistas.vista_laboratorio import VistaLaboratorio
from src.interfaz.vistas.vista_logistica import VistaLogistica
from src.interfaz.vistas.vista_mascotas import VistaMascotas
from src.interfaz.vistas.vista_reportes import VistaReportes

__all__ = [
    "VistaClientes",
    "VistaMascotas",
    "VistaConsultas",
    "VistaLogistica",
    "VistaLaboratorio",
    "VistaReportes",
]
