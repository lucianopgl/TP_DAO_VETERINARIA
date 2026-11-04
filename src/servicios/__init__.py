"""
Capa de servicios.

Coordina los procesos de negocio obligatorios (1 a 7), aplica las validaciones que no
pueden expresarse en la base de datos (por ejemplo, la superposición de turnos por rango
horario) y define las unidades de trabajo transaccionales. También genera los reportes.
"""

from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_laboratorio import ServicioLaboratorio
from src.servicios.servicio_logistica import ServicioLogistica
from src.servicios.servicio_reportes import ServicioReportes

__all__ = [
    "ServicioClinica",
    "ServicioLogistica",
    "ServicioLaboratorio",
    "ServicioReportes",
]
