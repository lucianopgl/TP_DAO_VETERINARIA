"""
Componentes visuales reutilizables para la interfaz gráfica CustomTkinter.
"""

from src.interfaz.componentes.alertas import (
    confirmar_accion,
    ejecutar_accion_segura,
    limpiar_resaltado_campos,
    mostrar_advertencia,
    mostrar_error,
    mostrar_exito,
    resaltar_campo_invalido,
)
from src.interfaz.componentes.tabla import TablaDatos

__all__ = [
    "TablaDatos",
    "mostrar_exito",
    "mostrar_advertencia",
    "mostrar_error",
    "confirmar_accion",
    "limpiar_resaltado_campos",
    "resaltar_campo_invalido",
    "ejecutar_accion_segura",
]
