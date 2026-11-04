"""
Punto de Entrada Principal del Sistema Veterinario (`main.py`)
==============================================================

Cátedra: Desarrollo de Aplicaciones con Objetos (DAO) — UTN FRC (2026)
Tema 2: Veterinaria — Red de Clínicas y Derivación de Laboratorio
Grupo: Grupo 089

Actúa como raíz de composición (Composition Root) respetando la Inversión de
Dependencias (DIP):
    1. Inicializa el esquema y los catálogos idempotentes de SQLite (`veterinaria.db`).
    2. Instancia el publicador de eventos (`SujetoEventos`) del patrón Observer.
    3. Instancia los servicios de negocio y de reportes inyectándoles sus dependencias.
    4. Lanza la interfaz gráfica `VentanaPrincipal` en CustomTkinter.

Ejecución desde la raíz del repositorio:
    python main.py
"""

from __future__ import annotations

from src.interfaz.app import VentanaPrincipal
from src.patrones.observador_eventos import ObservadorAuditoria, SujetoEventos
from src.persistencia.inicializador_bd import inicializar_base_datos
from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_laboratorio import ServicioLaboratorio
from src.servicios.servicio_logistica import ServicioLogistica
from src.servicios.servicio_reportes import ServicioReportes


def iniciar_aplicacion() -> None:
    """Inicializa la infraestructura, construye los servicios y ejecuta el bucle gráfico."""
    conexion = inicializar_base_datos()

    sujeto_eventos = SujetoEventos()
    auditor_memoria = ObservadorAuditoria()
    sujeto_eventos.suscribir(auditor_memoria)

    servicio_clinica = ServicioClinica(conexion=conexion)
    servicio_logistica = ServicioLogistica(conexion=conexion, sujeto_eventos=sujeto_eventos)
    servicio_laboratorio = ServicioLaboratorio(conexion=conexion, sujeto_eventos=sujeto_eventos)
    servicio_reportes = ServicioReportes(conexion=conexion)

    app = VentanaPrincipal(
        servicio_clinica=servicio_clinica,
        servicio_logistica=servicio_logistica,
        servicio_laboratorio=servicio_laboratorio,
        servicio_reportes=servicio_reportes,
        sujeto_eventos=sujeto_eventos,
    )

    def _al_cerrar_ventana() -> None:
        app.destroy()
        conexion.cerrar()

    app.protocol("WM_DELETE_WINDOW", _al_cerrar_ventana)
    app.mainloop()


if __name__ == "__main__":
    iniciar_aplicacion()
