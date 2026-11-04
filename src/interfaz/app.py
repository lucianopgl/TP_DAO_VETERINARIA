"""
Ventana Principal del Sistema Veterinario (`VentanaPrincipal`)
==============================================================

Orquesta la navegación entre las vistas modulares del sistema e implementa
el patrón de diseño **Observer** (`Observador`) para recibir y mostrar alertas
en tiempo real emitidas por `ServicioLogistica` y `ServicioLaboratorio`.

Principios de Diseño POO aplicados:
    - Patrón Observer (GoF): Se suscribe a `SujetoEventos` sin acoplar los servicios
      de negocio a la biblioteca gráfica CustomTkinter.
    - Inversión de Dependencias (DIP): Recibe las instancias de los 4 servicios
      por constructor e inyecta a cada vista únicamente el servicio que necesita.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import customtkinter as ctk

from src.interfaz.vistas.vista_clientes import VistaClientes
from src.interfaz.vistas.vista_consultas import VistaConsultas
from src.interfaz.vistas.vista_mascotas import VistaMascotas
from src.patrones.observador_eventos import Observador, SujetoEventos
from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_laboratorio import ServicioLaboratorio
from src.servicios.servicio_logistica import ServicioLogistica
from src.servicios.servicio_reportes import ServicioReportes


def formatear_evento_notificacion(tipo_evento: str, datos: dict[str, Any]) -> tuple[str, str]:
    """
    Traduce un evento del patrón Observer a un mensaje legible para la barra de
    notificaciones y su color semántico asociado.

    Returns:
        Tupla `(mensaje_formateado, color_hex)`.
    """
    hora = datetime.now().strftime("%H:%M:%S")
    if tipo_evento == "MUESTRAS_RECHAZADAS_EN_RECEPCION":
        remito = datos.get("numero_remito", "S/N")
        estado_precinto = datos.get("estado_precinto", "Violado/Roto")
        codigos = ", ".join(datos.get("muestras_rechazadas", []))
        return (
            f"[{hora}] ALERTA CRÍTICA: Remito {remito} rechazado por precinto '{estado_precinto}'. "
            f"Muestras invalidadas: {codigos}",
            "#DC2626",
        )
    if tipo_evento == "REMITO_RECIBIDO_CONFORME":
        remito = datos.get("numero_remito", "S/N")
        cantidad = datos.get("cantidad_muestras", 0)
        return (
            f"[{hora}] Recepción conforme en Laboratorio: Remito {remito} "
            f"(Precinto Intacto — {cantidad} muestra/s lista/s para análisis).",
            "#15803D",
        )
    if tipo_evento == "REMITO_DESPACHADO":
        remito = datos.get("numero_remito", "S/N")
        fecha_despacho = datos.get("fecha_hora_despacho", "")
        return (
            f"[{hora}] En tránsito: Remito {remito} despachado hacia el laboratorio central ({fecha_despacho}).",
            "#1D4ED8",
        )
    if tipo_evento == "RESULTADO_ANALISIS_LISTO":
        codigo = datos.get("codigo_muestra", "S/C")
        conclusion = datos.get("conclusion", "")
        return (
            f"[{hora}] Resultado bioquímico disponible — Muestra {codigo}: {conclusion}",
            "#0F766E",
        )
    return (f"[{hora}] Evento del sistema: {tipo_evento}", "#334155")


class VentanaPrincipal(ctk.CTk, Observador):
    """
    Ventana raíz de la aplicación gráfica en CustomTkinter.
    Actúa como contenedor de navegación lateral y como Observador de eventos de negocio.
    """

    def __init__(
        self,
        servicio_clinica: ServicioClinica,
        servicio_logistica: ServicioLogistica,
        servicio_laboratorio: ServicioLaboratorio,
        servicio_reportes: ServicioReportes,
        sujeto_eventos: SujetoEventos,
    ) -> None:
        super().__init__()
        self._srv_clinica = servicio_clinica
        self._srv_logistica = servicio_logistica
        self._srv_laboratorio = servicio_laboratorio
        self._srv_reportes = servicio_reportes
        self._sujeto_eventos = sujeto_eventos
        self._historial_notificaciones: list[str] = []

        # Suscripción explícita al patrón Observer
        self._sujeto_eventos.suscribir(self)

        self._configurar_ventana()
        self._construir_estructura_principal()
        self.mostrar_vista("clientes")

    # ==================================================================================
    # Configuración y Construcción Visual
    # ==================================================================================

    def _configurar_ventana(self) -> None:
        """Define apariencia, título, geometría inicial y comportamiento redimensionable."""
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title(
            "Sistema Veterinario: Red de Clínicas y Derivación de Laboratorio — UTN FRC (DAO 2026 - Grupo 089)"
        )
        self.geometry("1280x760")
        self.minsize(1080, 660)

    def _construir_estructura_principal(self) -> None:
        """Crea el menú lateral izquierdo, la barra superior Observer y el área de contenido."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 1. Barra lateral de navegación (Sidebar)
        self._sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color="#0F172A")
        self._sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._sidebar.grid_rowconfigure(8, weight=1)

        ctk.CTkLabel(
            self._sidebar,
            text="RED VETERINARIA",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color="#F8FAFC",
        ).grid(row=0, column=0, padx=20, pady=(22, 2), sticky="w")

        ctk.CTkLabel(
            self._sidebar,
            text="Derivación de Laboratorio\nUTN FRC — Grupo 089",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8",
            justify="left",
        ).grid(row=1, column=0, padx=20, pady=(0, 18), sticky="w")

        self._botones_nav: dict[str, ctk.CTkButton] = {}
        items_menu = [
            ("clientes", "1. Clientes"),
            ("mascotas", "2. Mascotas e H. Clínica"),
            ("consultas", "3. Consultas y Muestras"),
            ("logistica", "4. Logística y Remitos"),
            ("laboratorio", "5. Laboratorio y Facturas"),
            ("reportes", "6. Reportes Gerenciales"),
        ]

        for idx, (clave, texto) in enumerate(items_menu, start=2):
            boton = ctk.CTkButton(
                self._sidebar,
                text=texto,
                anchor="w",
                height=40,
                corner_radius=8,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="transparent",
                text_color="#E2E8F0",
                hover_color="#1E293B",
                command=lambda c=clave: self.mostrar_vista(c),
            )
            boton.grid(row=idx, column=0, padx=14, pady=4, sticky="ew")
            self._botones_nav[clave] = boton

        # Pie institucional en la barra lateral
        ctk.CTkLabel(
            self._sidebar,
            text="Cátedra DAO — TPI 2026\nPatrones: State · Strategy\nIterator · Observer · DAO",
            font=ctk.CTkFont(size=11),
            text_color="#64748B",
            justify="left",
        ).grid(row=9, column=0, padx=18, pady=16, sticky="sw")

        # 2. Barra superior de notificaciones en tiempo real (Patrón Observer)
        self._barra_notificaciones = ctk.CTkFrame(
            self, height=44, corner_radius=8, fg_color="#E2E8F0"
        )
        self._barra_notificaciones.grid(row=0, column=1, sticky="ew", padx=14, pady=(12, 4))
        self._barra_notificaciones.grid_columnconfigure(0, weight=1)

        self._etiqueta_notificacion = ctk.CTkLabel(
            self._barra_notificaciones,
            text="Centro de Notificaciones (Observer): Sistema iniciado y listo para operar.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1E293B",
            anchor="w",
        )
        self._etiqueta_notificacion.grid(row=0, column=0, sticky="ew", padx=14, pady=8)

        # 3. Contenedor central dinámico de vistas
        self._contenedor_central = ctk.CTkFrame(self, fg_color="transparent")
        self._contenedor_central.grid(row=1, column=1, sticky="nsew", padx=8, pady=(4, 10))
        self._contenedor_central.grid_rowconfigure(0, weight=1)
        self._contenedor_central.grid_columnconfigure(0, weight=1)

        self._vistas: dict[str, ctk.CTkFrame] = {}
        self._inicializar_vistas()

    def _inicializar_vistas(self) -> None:
        """Instancia las vistas disponibles inyectando el servicio correspondiente."""
        self._vistas["clientes"] = VistaClientes(
            self._contenedor_central,
            servicio_clinica=self._srv_clinica,
        )
        self._vistas["mascotas"] = VistaMascotas(
            self._contenedor_central,
            servicio_clinica=self._srv_clinica,
        )
        self._vistas["consultas"] = VistaConsultas(
            self._contenedor_central,
            servicio_clinica=self._srv_clinica,
        )

        # Vistas de las Etapas 3 y 4 (se habilitarán en los próximos pasos)
        etapas_pendientes = {
            "logistica": (
                "Procesos 4, 5 y 6: Conservadoras (Iterator), Remitos, Despacho y Recepción",
                "Se implementará en la Etapa 3 tras validar la Etapa 2.",
            ),
            "laboratorio": (
                "Proceso 7: Resultados Bioquímicos (State) y Facturación (Strategy)",
                "Se implementará en la Etapa 3 tras validar la Etapa 2.",
            ),
            "reportes": (
                "Reportes Gerenciales y Sanitarios + Exportación CSV",
                "Se implementará en la Etapa 4.",
            ),
        }
        for clave, (titulo, descripcion) in etapas_pendientes.items():
            self._vistas[clave] = self._crear_panel_etapa_futura(titulo, descripcion)

    def _crear_panel_etapa_futura(self, titulo: str, subtitulo: str) -> ctk.CTkFrame:
        """Crea un panel informativo limpio para las vistas programadas en etapas siguientes."""
        marco = ctk.CTkFrame(self._contenedor_central, corner_radius=12)
        marco.grid_rowconfigure(0, weight=1)
        marco.grid_columnconfigure(0, weight=1)

        interior = ctk.CTkFrame(marco, fg_color="transparent")
        interior.grid(row=0, column=0, padx=30, pady=30)

        ctk.CTkLabel(
            interior,
            text=titulo,
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            interior,
            text=subtitulo,
            font=ctk.CTkFont(size=14),
            text_color=("gray35", "gray70"),
        ).pack()
        return marco

    # ==================================================================================
    # Navegación entre Vistas
    # ==================================================================================

    def mostrar_vista(self, clave_vista: str) -> None:
        """Muestra la vista solicitada, resalta su botón en el menú y refresca sus datos."""
        for clave, boton in self._botones_nav.items():
            if clave == clave_vista:
                boton.configure(fg_color="#2563EB", text_color="#FFFFFF")
            else:
                boton.configure(fg_color="transparent", text_color="#E2E8F0")

        for vista in self._vistas.values():
            vista.grid_forget()

        vista_activa = self._vistas[clave_vista]
        vista_activa.grid(row=0, column=0, sticky="nsew")
        if hasattr(vista_activa, "refrescar_datos"):
            vista_activa.refrescar_datos()

    # ==================================================================================
    # Implementación del Patrón OBSERVER (`Observador`)
    # ==================================================================================

    def actualizar(self, tipo_evento: str, datos: dict[str, Any]) -> None:
        """
        Recibe las notificaciones difundidas por `SujetoEventos` y actualiza en vivo
        la barra superior de estado de la ventana principal.
        """
        mensaje, color_fondo = formatear_evento_notificacion(tipo_evento, datos)
        self._historial_notificaciones.append(mensaje)
        self._barra_notificaciones.configure(fg_color=color_fondo)
        self._etiqueta_notificacion.configure(text=mensaje, text_color="#FFFFFF")

    @property
    def historial_notificaciones(self) -> list[str]:
        """Devuelve la copia de las notificaciones recibidas por la interfaz."""
        return list(self._historial_notificaciones)
