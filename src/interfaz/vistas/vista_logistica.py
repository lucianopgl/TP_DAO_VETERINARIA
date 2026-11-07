"""
Vista Gráfica: Procesos 4, 5 y 6 — Logística, Conservadoras, Remitos y Recepción
================================================================================

Coordina:
    - Proceso 4: Empaquetar muestras biológicas en conservadoras isotérmicas
      (Patrón ITERATOR) emitiendo remito biológico y precinto sanitario.
    - Proceso 5: Despachar remitos hacia el laboratorio central con asignación
      de transportista sanitario.
    - Proceso 6: Registrar la recepción en el laboratorio central verificando
      el estado del precinto ('Intacto', 'Roto', 'Violado'). Si el precinto llega
      roto o violado, las muestras pasan automáticamente a 'Rechazada' (Patrón STATE)
      y el Patrón OBSERVER emite una alerta sanitaria crítica.

Principios de Diseño POO aplicados:
    - Alta Cohesión / SRP: Pestañas dedicadas para cada proceso del circuito logístico.
    - Bajo Acoplamiento / DIP: Recibe `ServicioLogistica` y `ServicioClinica` sin
      conocer detalles de persistencia ni SQL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import customtkinter as ctk

from src.dominio.excepciones import ErrorDatosInvalidos
from src.dominio.logistica import RemitoBiologico
from src.dominio.muestra_biologica import MuestraBiologica
from src.interfaz.componentes.alertas import (
    confirmar_accion,
    ejecutar_accion_segura,
    limpiar_resaltado_campos,
    mostrar_advertencia,
    mostrar_exito,
)
from src.interfaz.componentes.tabla import TablaDatos
from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_logistica import ServicioLogistica


class VistaLogistica(ctk.CTkFrame):
    """Vista interactiva para los Procesos 4, 5 y 6 de Logística y Trazabilidad."""

    def __init__(
        self,
        master: Any,
        servicio_logistica: ServicioLogistica,
        servicio_clinica: ServicioClinica,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._srv_logistica = servicio_logistica
        self._srv_clinica = servicio_clinica

        self._remito_seleccionado_id: int | None = None
        self._remito_actual: RemitoBiologico | None = None
        self._mapa_campos_empaquetado: dict[str, ctk.CTkBaseClass] = {}

        # Mapeos de catálogos y entidades
        self._clinicas_por_nombre: dict[str, int] = {}
        self._nombre_por_clinica_id: dict[int, str] = {}
        self._laboratorios_por_nombre: dict[str, int] = {}
        self._nombre_por_lab_id: dict[int, str] = {}
        self._conservadoras_por_etiqueta: dict[str, int] = {}
        self._transportistas_por_etiqueta: dict[str, int] = {}
        self._muestras_pendientes_seleccionadas: set[int] = set()

        self._construir_ui()
        self.refrescar_datos()

    # ==================================================================================
    # Construcción de la Interfaz (UI)
    # ==================================================================================

    def _construir_ui(self) -> None:
        """Divide la pantalla en monitor de remitos (arriba) y panel de operaciones (abajo)."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Cabecera
        marco_cabecera = ctk.CTkFrame(self, fg_color="transparent")
        marco_cabecera.grid(row=0, column=0, sticky="ew", padx=10, pady=(2, 6))

        ctk.CTkLabel(
            marco_cabecera,
            text="Procesos 4, 5 y 6: Logística, Remitos Biológicos y Cadena de Custodia",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")

        self._etiqueta_contador_remitos = ctk.CTkLabel(
            marco_cabecera,
            text="0 remitos registrados",
            font=ctk.CTkFont(size=13),
            text_color=("gray35", "gray70"),
        )
        self._etiqueta_contador_remitos.pack(side="right", padx=8)

        # Panel maestro-detalle dividido verticalmente
        panel_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        panel_contenedor.grid(row=1, column=0, sticky="nsew", padx=6, pady=2)
        panel_contenedor.grid_rowconfigure(0, weight=4)
        panel_contenedor.grid_rowconfigure(1, weight=6)
        panel_contenedor.grid_columnconfigure(0, weight=1)

        # Mitad Superior: Monitor general de Remitos Biológicos
        self._construir_monitor_remitos(panel_contenedor)

        # Mitad Inferior: Pestañas para Empaquetado (P4), Despacho (P5), Recepción (P6) y Muestras
        self._construir_pestanas_operaciones(panel_contenedor)

    def _construir_monitor_remitos(self, contenedor: ctk.CTkFrame) -> None:
        """Crea la tabla de supervisión de remitos biológicos."""
        marco_remitos = ctk.CTkFrame(contenedor, corner_radius=10)
        marco_remitos.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        marco_remitos.grid_rowconfigure(1, weight=1)
        marco_remitos.grid_columnconfigure(0, weight=1)

        barra_titulo = ctk.CTkFrame(marco_remitos, fg_color="transparent")
        barra_titulo.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))
        barra_titulo.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            barra_titulo,
            text="Monitor de Remitos Biológicos (seleccione un remito para despachar, recibir o ver sus muestras)",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            barra_titulo,
            text="Actualizar Monitor",
            width=130,
            height=28,
            fg_color="#475569",
            hover_color="#334155",
            command=self.refrescar_datos,
        ).grid(row=0, column=1)

        columnas_remitos = [
            ("id", "ID", 45),
            ("numero", "Remito N°", 110),
            ("estado", "Estado Remito", 115),
            ("clinica", "Clínica Origen", 180),
            ("destino", "Laboratorio Destino", 190),
            ("conservadora", "Conservadora (Cap.)", 145),
            ("precinto", "Precinto (Sello)", 135),
            ("precinto_estado", "Estado Precinto", 115),
            ("muestras", "Muestras", 80),
            ("fecha", "Fecha Creación", 145),
        ]
        self._tabla_remitos = TablaDatos(
            marco_remitos,
            columnas=columnas_remitos,
            al_seleccionar=self._al_seleccionar_remito,
            altura_filas=5,
        )
        self._tabla_remitos.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

    def _construir_pestanas_operaciones(self, contenedor: ctk.CTkFrame) -> None:
        """Crea las pestañas operativas de los procesos 4, 5 y 6."""
        self._pestanas = ctk.CTkTabview(contenedor, height=310)
        self._pestanas.grid(row=1, column=0, sticky="nsew", pady=(2, 0))

        tab_p4 = self._pestanas.add("1. Empaquetar en Conservadora (Proceso 4)")
        tab_p5 = self._pestanas.add("2. Despachar a Laboratorio (Proceso 5)")
        tab_p6 = self._pestanas.add("3. Recepción y Verificación de Precinto (Proceso 6)")
        tab_muestras = self._pestanas.add("4. Muestras del Remito Seleccionado")

        self._construir_tab_empaquetado(tab_p4)
        self._construir_tab_despacho(tab_p5)
        self._construir_tab_recepcion(tab_p6)
        self._construir_tab_muestras_remito(tab_muestras)

    # ----------------------------------------------------------------------------------
    # Pestaña 1: Empaquetado en Conservadora (Proceso 4)
    # ----------------------------------------------------------------------------------

    def _construir_tab_empaquetado(self, tab: ctk.CTkFrame) -> None:
        """Formulario para empaquetar muestras extraídas en conservadora con remito y precinto."""
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=0, minsize=380)
        tab.grid_columnconfigure(1, weight=1)

        # Panel izquierdo del tab: Datos del Remito y Precinto
        panel_izq = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        panel_izq.grid(row=0, column=0, sticky="nsew", padx=(6, 10), pady=4)
        panel_izq.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel_izq,
            text="Datos de Remito, Conservadora y Precinto",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(2, 6))

        # Clínica Origen
        ctk.CTkLabel(
            panel_izq, text="Clínica Emisora de Origen *", font=ctk.CTkFont(size=11, weight="bold")
        ).grid(row=1, column=0, sticky="w")
        self._combo_p4_clinica = ctk.CTkComboBox(
            panel_izq,
            values=["Clínica Centro"],
            height=28,
            state="readonly",
            command=self._al_cambiar_clinica_empaquetado,
        )
        self._combo_p4_clinica.grid(row=2, column=0, sticky="ew", pady=(1, 4))

        # Laboratorio Destino
        ctk.CTkLabel(
            panel_izq, text="Laboratorio Central de Destino *", font=ctk.CTkFont(size=11, weight="bold")
        ).grid(row=3, column=0, sticky="w")
        self._combo_p4_lab = ctk.CTkComboBox(
            panel_izq, values=["Laboratorio Central"], height=28, state="readonly"
        )
        self._combo_p4_lab.grid(row=4, column=0, sticky="ew", pady=(1, 4))

        # Conservadora Isotérmica (Iterator)
        ctk.CTkLabel(
            panel_izq,
            text="Conservadora Isotérmica (Control de Capacidad - Iterator) *",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=5, column=0, sticky="w")
        self._combo_p4_conservadora = ctk.CTkComboBox(
            panel_izq, values=["CONS-001"], height=28, state="readonly"
        )
        self._combo_p4_conservadora.grid(row=6, column=0, sticky="ew", pady=(1, 4))

        # Número de Remito y Precinto Sanitario en una fila
        marco_rem_prec = ctk.CTkFrame(panel_izq, fg_color="transparent")
        marco_rem_prec.grid(row=7, column=0, sticky="ew", pady=(2, 4))
        marco_rem_prec.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            marco_rem_prec, text="N° Remito *", font=ctk.CTkFont(size=11, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=(0, 4))
        ctk.CTkLabel(
            marco_rem_prec, text="N° Serie Precinto *", font=ctk.CTkFont(size=11, weight="bold")
        ).grid(row=0, column=1, sticky="w", padx=(4, 0))

        self._entrada_p4_remito = ctk.CTkEntry(marco_rem_prec, height=28)
        self._entrada_p4_remito.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        self._mapa_campos_empaquetado["numero_remito"] = self._entrada_p4_remito

        self._entrada_p4_precinto = ctk.CTkEntry(marco_rem_prec, height=28)
        self._entrada_p4_precinto.grid(row=1, column=1, sticky="ew", padx=(4, 0))
        self._mapa_campos_empaquetado["numero_serie_precinto"] = self._entrada_p4_precinto

        # Observaciones
        ctk.CTkLabel(
            panel_izq, text="Observaciones de empaquetado:", font=ctk.CTkFont(size=11)
        ).grid(row=8, column=0, sticky="w", pady=(2, 1))
        self._entrada_p4_obs = ctk.CTkEntry(
            panel_izq, placeholder_text="Ej: Cadenas de frío refrigeradas a 4°C", height=28
        )
        self._entrada_p4_obs.grid(row=9, column=0, sticky="ew", pady=(0, 6))

        # Botones de acción
        marco_botones_p4 = ctk.CTkFrame(panel_izq, fg_color="transparent")
        marco_botones_p4.grid(row=10, column=0, sticky="ew", pady=(4, 6))
        marco_botones_p4.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            marco_botones_p4,
            text="Empaquetar y Precintar Remito",
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._al_empaquetar_muestras,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        ctk.CTkButton(
            marco_botones_p4,
            text="Nuevo Remito",
            fg_color="#475569",
            hover_color="#334155",
            height=28,
            command=self._limpiar_formulario_p4,
        ).grid(row=1, column=0, columnspan=2, sticky="ew")

        # Panel derecho del tab: Selector de Muestras Extraídas pendientes
        panel_der = ctk.CTkFrame(tab, corner_radius=8)
        panel_der.grid(row=0, column=1, sticky="nsew", padx=(6, 6), pady=4)
        panel_der.grid_rowconfigure(1, weight=1)
        panel_der.grid_columnconfigure(0, weight=1)

        barra_muestras = ctk.CTkFrame(panel_der, fg_color="transparent")
        barra_muestras.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 4))
        barra_muestras.grid_columnconfigure(0, weight=1)

        self._etiqueta_muestras_disponibles = ctk.CTkLabel(
            barra_muestras,
            text="Muestras Extraídas Disponibles (haga clic para agregar/quitar del lote):",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._etiqueta_muestras_disponibles.grid(row=0, column=0, sticky="w")

        self._etiqueta_seleccion_conteo = ctk.CTkLabel(
            barra_muestras,
            text="0 muestras seleccionadas",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1D4ED8",
        )
        self._etiqueta_seleccion_conteo.grid(row=0, column=1, sticky="e")

        columnas_extraidas = [
            ("id", "ID", 45),
            ("codigo", "Código Muestra", 130),
            ("tipo", "Tipo Muestra", 130),
            ("orden", "Orden #", 65),
            ("estado", "Estado (State)", 110),
            ("fecha", "Fecha Extracción", 145),
            ("seleccionada", "Incluida en Remito", 130),
        ]
        self._tabla_muestras_extraidas = TablaDatos(
            panel_der,
            columnas=columnas_extraidas,
            al_seleccionar=self._al_alternar_seleccion_muestra,
            altura_filas=5,
        )
        self._tabla_muestras_extraidas.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))

    # ----------------------------------------------------------------------------------
    # Pestaña 2: Despacho a Laboratorio (Proceso 5)
    # ----------------------------------------------------------------------------------

    def _construir_tab_despacho(self, tab: ctk.CTkFrame) -> None:
        """Formulario para despachar remitos precintados hacia el laboratorio central."""
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        marco_centro = ctk.CTkFrame(tab, corner_radius=10)
        marco_centro.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)
        marco_centro.grid_columnconfigure(0, weight=1)

        self._etiqueta_despacho_remito = ctk.CTkLabel(
            marco_centro,
            text="Despacho de Remito Biológico (Proceso 5)",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self._etiqueta_despacho_remito.grid(row=0, column=0, sticky="w", padx=18, pady=(12, 6))

        self._etiqueta_remito_despacho_info = ctk.CTkLabel(
            marco_centro,
            text="Seleccione un remito en estado 'Precintado' en la tabla superior para autorizar su salida.",
            font=ctk.CTkFont(size=12),
            text_color=("gray35", "gray70"),
        )
        self._etiqueta_remito_despacho_info.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 8))

        ctk.CTkLabel(
            marco_centro,
            text="Empresa de Transporte Sanitario / Chofer Habilitado *",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=2, column=0, sticky="w", padx=18, pady=(4, 1))

        self._combo_transportista = ctk.CTkComboBox(
            marco_centro,
            values=["Transporte Sanitario"],
            height=32,
            state="readonly",
        )
        self._combo_transportista.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 6))

        ctk.CTkLabel(
            marco_centro,
            text="Fecha y Hora de Despacho (AAAA-MM-DD HH:MM:SS) *",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=4, column=0, sticky="w", padx=18, pady=(4, 1))

        self._entrada_fecha_despacho = ctk.CTkEntry(marco_centro, height=32)
        self._entrada_fecha_despacho.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 6))

        ctk.CTkLabel(
            marco_centro,
            text="Observaciones de salida / transporte:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=6, column=0, sticky="w", padx=18, pady=(4, 1))

        self._entrada_obs_despacho = ctk.CTkEntry(
            marco_centro,
            placeholder_text="Ej: Salida puntual, conservadora asegurada en furgón isotérmico",
            height=32,
        )
        self._entrada_obs_despacho.grid(row=7, column=0, sticky="ew", padx=18, pady=(0, 12))

        self._btn_despachar = ctk.CTkButton(
            marco_centro,
            text="Despachar Remito a Laboratorio (Transición EnTransito)",
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._al_despachar_remito,
        )
        self._btn_despachar.grid(row=8, column=0, sticky="w", padx=18, pady=(0, 16))

    # ----------------------------------------------------------------------------------
    # Pestaña 3: Recepción y Verificación de Precinto (Proceso 6)
    # ----------------------------------------------------------------------------------

    def _construir_tab_recepcion(self, tab: ctk.CTkFrame) -> None:
        """Formulario de inspección de precinto sanitario en el laboratorio central."""
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        marco_recepcion = ctk.CTkScrollableFrame(tab, corner_radius=10)
        marco_recepcion.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)
        marco_recepcion.grid_columnconfigure(0, weight=1)

        self._etiqueta_recepcion_remito = ctk.CTkLabel(
            marco_recepcion,
            text="Recepción en Laboratorio Central y Verificación de Precinto (Proceso 6)",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self._etiqueta_recepcion_remito.grid(row=0, column=0, sticky="w", padx=18, pady=(12, 4))

        self._etiqueta_remito_recepcion_info = ctk.CTkLabel(
            marco_recepcion,
            text="Seleccione un remito en estado 'EnTransito' en la tabla superior para verificar su arribo.",
            font=ctk.CTkFont(size=12),
            text_color=("gray35", "gray70"),
        )
        self._etiqueta_remito_recepcion_info.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 8))

        # Estado del precinto
        ctk.CTkLabel(
            marco_recepcion,
            text="Estado del Precinto Sanitario al Arribo *",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=2, column=0, sticky="w", padx=18, pady=(4, 1))

        self._combo_estado_precinto = ctk.CTkComboBox(
            marco_recepcion,
            values=["Intacto", "Roto", "Violado"],
            height=32,
            state="readonly",
        )
        self._combo_estado_precinto.set("Intacto")
        self._combo_estado_precinto.grid(row=3, column=0, sticky="w", padx=18, pady=(0, 6))

        # Banner de advertencia sobre la regla crítica del TP
        banner_aviso = ctk.CTkFrame(marco_recepcion, corner_radius=6, fg_color="#FEF3C7")
        banner_aviso.grid(row=4, column=0, sticky="ew", padx=18, pady=(2, 8))
        ctk.CTkLabel(
            banner_aviso,
            text="REGLA SANITARIA OBLIGATORIA: Si el precinto llega 'Roto' o 'Violado', todas las muestras del "
            "remito se rechazarán automáticamente, impidiendo su análisis bioquímico y disparando alerta Observer.",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#92400E",
            wraplength=820,
            justify="left",
        ).pack(padx=10, pady=6)

        ctk.CTkLabel(
            marco_recepcion,
            text="Fecha y Hora de Recepción (AAAA-MM-DD HH:MM:SS) *",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=5, column=0, sticky="w", padx=18, pady=(4, 1))

        self._entrada_fecha_recepcion = ctk.CTkEntry(marco_recepcion, height=32)
        self._entrada_fecha_recepcion.grid(row=6, column=0, sticky="ew", padx=18, pady=(0, 6))

        ctk.CTkLabel(
            marco_recepcion,
            text="Observaciones de recepción / cadena de frío:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=7, column=0, sticky="w", padx=18, pady=(4, 1))

        self._entrada_obs_recepcion = ctk.CTkEntry(
            marco_recepcion,
            placeholder_text="Ej: Temperatura registrada 3.5°C, precinto verificado conforme",
            height=32,
        )
        self._entrada_obs_recepcion.grid(row=8, column=0, sticky="ew", padx=18, pady=(0, 12))

        self._btn_recibir = ctk.CTkButton(
            marco_recepcion,
            text="Registrar Recepción en Laboratorio",
            fg_color="#15803D",
            hover_color="#166534",
            height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._al_recibir_remito,
        )
        self._btn_recibir.grid(row=9, column=0, sticky="w", padx=18, pady=(0, 16))

    # ----------------------------------------------------------------------------------
    # Pestaña 4: Muestras del Remito Seleccionado
    # ----------------------------------------------------------------------------------

    def _construir_tab_muestras_remito(self, tab: ctk.CTkFrame) -> None:
        """Visualiza las muestras empaquetadas en el remito seleccionado y su trazabilidad."""
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        marco_sup = ctk.CTkFrame(tab, fg_color="transparent")
        marco_sup.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 4))
        marco_sup.grid_columnconfigure(0, weight=1)

        self._etiqueta_detalle_remito = ctk.CTkLabel(
            marco_sup,
            text="Muestras Biológicas del Remito: Seleccione un remito en la tabla superior",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self._etiqueta_detalle_remito.grid(row=0, column=0, sticky="ew")

        self._chk_solo_viables_iterator = ctk.CTkCheckBox(
            marco_sup,
            text="Filtrar solo viables (Conservadora.iterar_viables — Patrón Iterator)",
            font=ctk.CTkFont(size=12),
            command=self._al_alternar_filtro_viables_iterator,
        )
        self._chk_solo_viables_iterator.grid(row=0, column=1, sticky="e", padx=(10, 0))

        columnas_muestras_remito = [
            ("id", "ID", 45),
            ("codigo", "Código Muestra", 140),
            ("tipo", "Tipo de Muestra", 150),
            ("orden", "Orden #", 70),
            ("estado", "Estado Actual (Patrón State)", 140),
            ("viable", "Viabilidad", 100),
            ("motivo", "Motivo de Rechazo (si aplica)", 230),
            ("ultimo_evento", "Último Hito Inmutable de Trazabilidad", 220),
        ]
        self._tabla_muestras_remito = TablaDatos(
            tab,
            columnas=columnas_muestras_remito,
            altura_filas=5,
        )
        self._tabla_muestras_remito.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))

    def _al_alternar_filtro_viables_iterator(self) -> None:
        """Recarga la tabla de muestras del remito alternando entre IteradorMuestras e IteradorMuestrasFiltradas."""
        if self._remito_actual is not None:
            self._cargar_muestras_del_remito(self._remito_actual)

    # ==================================================================================
    # Manejadores de Eventos
    # ==================================================================================

    def _al_cambiar_clinica_empaquetado(self, _nombre_clinica: str) -> None:
        """Filtra las muestras extraídas pendientes según la clínica seleccionada."""
        self._muestras_pendientes_seleccionadas.clear()
        self._actualizar_contador_seleccion()
        self._recargar_muestras_extraidas_pendientes()

    def _al_alternar_seleccion_muestra(self, id_fila: str) -> None:
        """Agrega o quita una muestra extraída del lote a empaquetar."""
        muestra_id = int(id_fila)
        if muestra_id in self._muestras_pendientes_seleccionadas:
            self._muestras_pendientes_seleccionadas.remove(muestra_id)
        else:
            self._muestras_pendientes_seleccionadas.add(muestra_id)
        self._actualizar_contador_seleccion()
        self._recargar_muestras_extraidas_pendientes()

    def _actualizar_contador_seleccion(self) -> None:
        total = len(self._muestras_pendientes_seleccionadas)
        sufijo = "muestra seleccionada" if total == 1 else "muestras seleccionadas"
        self._etiqueta_seleccion_conteo.configure(text=f"{total} {sufijo}")

    def _al_empaquetar_muestras(self) -> None:
        """Empaqueta las muestras seleccionadas en la conservadora generando remito y precinto."""
        if not self._muestras_pendientes_seleccionadas:
            mostrar_advertencia(
                "Muestras requeridas",
                "Haga clic en la tabla de la derecha para seleccionar al menos una muestra para empaquetar.",
            )
            return

        clinica_id = self._clinicas_por_nombre.get(self._combo_p4_clinica.get(), 1)
        lab_id = self._laboratorios_por_nombre.get(self._combo_p4_lab.get(), 1)
        conservadora_id = self._conservadoras_por_etiqueta.get(self._combo_p4_conservadora.get())

        if conservadora_id is None:
            mostrar_advertencia(
                "Conservadora no disponible",
                "No hay conservadoras isotérmicas disponibles. Espere la liberación de una en recepción.",
            )
            return

        numero_remito = self._entrada_p4_remito.get().strip()
        numero_precinto = self._entrada_p4_precinto.get().strip()
        obs = self._entrada_p4_obs.get().strip()
        muestras_ids = list(self._muestras_pendientes_seleccionadas)

        remito = ejecutar_accion_segura(
            lambda: self._srv_logistica.empaquetar_muestras(
                numero_remito=numero_remito,
                clinica_origen_id=clinica_id,
                laboratorio_destino_id=lab_id,
                conservadora_id=conservadora_id,
                numero_serie_precinto=numero_precinto,
                muestras_ids=muestras_ids,
                observacion=obs,
            ),
            mapa_campos=self._mapa_campos_empaquetado,
            titulo_error="No se pudo empaquetar el remito",
        )
        if remito is not None:
            mostrar_exito(
                "Remito Empaquetado y Precintado",
                f"Remito '{remito.numero_remito}' sellado con precinto '{remito.precinto.numero_serie}'.\n"
                f"Se empaquetaron {len(remito.muestras)} muestras en estado 'Empaquetada' (Patrón State).",
            )
            self._limpiar_formulario_p4()
            self.refrescar_datos()
            if remito.id is not None:
                self._al_seleccionar_remito(str(remito.id))
                self._pestanas.set("2. Despachar a Laboratorio (Proceso 5)")

    def _al_seleccionar_remito(self, id_fila: str) -> None:
        """Carga el remito seleccionado en las pestañas de despacho, recepción y muestras."""
        remito_id = int(id_fila)
        self._remito_seleccionado_id = remito_id

        remito = ejecutar_accion_segura(
            lambda: self._srv_logistica.obtener_remito_completo(remito_id),
            titulo_error="Error al cargar remito",
        )
        if remito is None:
            return

        # Actualizar info en Pestaña Despacho
        self._etiqueta_remito_despacho_info.configure(
            text=f"Remito #{remito.id} ({remito.numero_remito}) — Estado: {remito.estado} "
            f"— Precinto: {remito.precinto.numero_serie if remito.precinto else 'Sin precinto'}"
        )
        self._entrada_fecha_despacho.delete(0, "end")
        self._entrada_fecha_despacho.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:00"))

        # Actualizar info en Pestaña Recepción
        self._etiqueta_remito_recepcion_info.configure(
            text=f"Remito #{remito.id} ({remito.numero_remito}) — Estado: {remito.estado} "
            f"— Conservadora: {remito.conservadora.codigo if remito.conservadora else 'N/A'}"
        )
        self._entrada_fecha_recepcion.delete(0, "end")
        self._entrada_fecha_recepcion.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:00"))

        # Actualizar tabla de muestras del remito (Pestaña 4)
        self._cargar_muestras_del_remito(remito)

    def _cargar_muestras_del_remito(self, remito: RemitoBiologico) -> None:
        """
        Puebla la tabla de muestras contenidas en el remito utilizando el Patrón ITERATOR
        de `ConservadoraIsotermica` (`__iter__` o `iterar_viables`).
        """
        self._remito_actual = remito
        solo_viables = bool(
            hasattr(self, "_chk_solo_viables_iterator") and self._chk_solo_viables_iterator.get()
        )
        if remito.conservadora is not None:
            iterador_muestras = (
                remito.conservadora.iterar_viables() if solo_viables else iter(remito.conservadora)
            )
            total_viables = sum(1 for _ in remito.conservadora.iterar_viables())
            total_alojadas = remito.conservadora.cantidad_muestras
        else:
            iterador_muestras = (
                (m for m in remito.muestras if m.esta_viable) if solo_viables else iter(remito.muestras)
            )
            total_viables = sum(1 for m in remito.muestras if m.esta_viable)
            total_alojadas = len(remito.muestras)

        self._etiqueta_detalle_remito.configure(
            text=f"Muestras del Remito #{remito.id} ({remito.numero_remito}) — "
            f"Estado: {remito.estado} — Viables: {total_viables}/{total_alojadas}"
        )
        filas = []
        for m in iterador_muestras:
            ultimo = (
                f"{m.historial[-1].estado_nuevo} ({m.historial[-1].fecha_hora})"
                if m.historial
                else m.estado_actual
            )
            filas.append(
                (
                    m.id,
                    (
                        m.id,
                        m.codigo_muestra,
                        m.nombre_tipo_muestra,
                        f"#{m.orden_id}",
                        m.estado_actual,
                        "VIABLE" if m.esta_viable else "RECHAZADA",
                        m.motivo_rechazo or "—",
                        ultimo,
                    ),
                )
            )
        self._tabla_muestras_remito.cargar_filas(filas)

    def _al_despachar_remito(self) -> None:
        """Registra el despacho del remito hacia el laboratorio."""
        if self._remito_seleccionado_id is None:
            mostrar_advertencia(
                "Seleccione un remito",
                "Haga clic en la tabla superior sobre el remito que desea despachar.",
            )
            return

        transportista_id = self._transportistas_por_etiqueta.get(self._combo_transportista.get())
        if transportista_id is None:
            mostrar_advertencia("Transportista requerido", "Seleccione un transportista.")
            return

        fecha_despacho = self._entrada_fecha_despacho.get().strip()
        obs = self._entrada_obs_despacho.get().strip()
        remito_id = self._remito_seleccionado_id

        envio = ejecutar_accion_segura(
            lambda: self._srv_logistica.despachar_remito(
                remito_id=remito_id,
                transportista_id=transportista_id,
                fecha_hora_despacho=fecha_despacho,
                observacion=obs,
            ),
            titulo_error="No se pudo despachar el remito",
        )
        if envio is not None:
            mostrar_exito(
                "Remito Despachado",
                f"El remito fue despachado exitosamente ({envio.fecha_hora_despacho}).\n"
                "Todas sus muestras pasaron a estado 'EnTransito' (Patrón State).",
            )
            self.refrescar_datos()
            self._al_seleccionar_remito(str(remito_id))
            self._pestanas.set("3. Recepción y Verificación de Precinto (Proceso 6)")

    def _al_recibir_remito(self) -> None:
        """Registra la recepción en el laboratorio verificando el estado del precinto."""
        if self._remito_seleccionado_id is None:
            mostrar_advertencia(
                "Seleccione un remito",
                "Haga clic en la tabla superior sobre el remito recibido.",
            )
            return

        estado_precinto = self._combo_estado_precinto.get().strip()
        fecha_recepcion = self._entrada_fecha_recepcion.get().strip()
        obs = self._entrada_obs_recepcion.get().strip()
        remito_id = self._remito_seleccionado_id

        if estado_precinto in ("Roto", "Violado"):
            if not confirmar_accion(
                "Confirmar Precinto Dañado / Violado",
                f"ATENCIÓN: Ha marcado el precinto como '{estado_precinto.upper()}'.\n\n"
                "Esta acción RECHAZARÁ de forma definitiva todas las muestras contenidas en el remito, "
                "bloqueando su procesamiento bioquímico y disparando una alerta a la clínica remitente.\n\n"
                "¿Desea confirmar la recepción con precinto dañado?",
            ):
                return

        remito = ejecutar_accion_segura(
            lambda: self._srv_logistica.recibir_remito_en_laboratorio(
                remito_id=remito_id,
                estado_precinto=estado_precinto,
                fecha_hora_recepcion=fecha_recepcion,
                observaciones=obs,
            ),
            titulo_error="No se pudo registrar la recepción",
        )
        if remito is not None:
            if estado_precinto == "Intacto":
                mostrar_exito(
                    "Recepción Conforme",
                    f"Remito '{remito.numero_remito}' recibido con precinto INTACTO.\n"
                    f"Muestras habilitadas en estado 'Recibida' para análisis en Laboratorio.",
                )
            else:
                mostrar_advertencia(
                    "Recepción con Muestras Rechazadas",
                    f"Remito '{remito.numero_remito}' recibido con precinto '{estado_precinto.upper()}'.\n"
                    f"Las muestras fueron RECHAZADAS y no podrán ser analizadas.",
                )
            self.refrescar_datos()
            self._al_seleccionar_remito(str(remito_id))
            self._pestanas.set("4. Muestras del Remito Seleccionado")

    def _limpiar_formulario_p4(self) -> None:
        """Restablece los campos de entrada de la pestaña de empaquetado."""
        limpiar_resaltado_campos(self._mapa_campos_empaquetado)
        marca = datetime.now().strftime("%H%M")
        self._entrada_p4_remito.delete(0, "end")
        self._entrada_p4_remito.insert(0, f"REM-{marca}")
        self._entrada_p4_precinto.delete(0, "end")
        self._entrada_p4_precinto.insert(0, f"PREC-{marca}")
        self._entrada_p4_obs.delete(0, "end")
        self._muestras_pendientes_seleccionadas.clear()
        self._actualizar_contador_seleccion()
        self._recargar_muestras_extraidas_pendientes()

    # ==================================================================================
    # Sincronización y Refresco de Datos
    # ==================================================================================

    def refrescar_datos(self) -> None:
        """Actualiza catálogos, conservadoras, transportistas y tablas de remitos."""
        # 1. Clínicas
        clinicas = self._srv_clinica.listar_clinicas()
        self._clinicas_por_nombre = {c["nombre"]: int(c["id"]) for c in clinicas}
        self._nombre_por_clinica_id = {int(c["id"]): c["nombre"] for c in clinicas}
        nombres_clinicas = list(self._clinicas_por_nombre.keys())
        if nombres_clinicas:
            self._combo_p4_clinica.configure(values=nombres_clinicas)
            if self._combo_p4_clinica.get() not in self._clinicas_por_nombre:
                self._combo_p4_clinica.set(nombres_clinicas[0])

        # 2. Laboratorios
        laboratorios = self._srv_logistica.listar_laboratorios()
        self._laboratorios_por_nombre = {lab["nombre"]: int(lab["id"]) for lab in laboratorios}
        self._nombre_por_lab_id = {int(lab["id"]): lab["nombre"] for lab in laboratorios}
        nombres_labs = list(self._laboratorios_por_nombre.keys())
        if nombres_labs:
            self._combo_p4_lab.configure(values=nombres_labs)
            if self._combo_p4_lab.get() not in self._laboratorios_por_nombre:
                self._combo_p4_lab.set(nombres_labs[0])

        # 3. Conservadoras disponibles (Iterator)
        conservadoras = self._srv_logistica.listar_conservadoras_disponibles()
        self._conservadoras_por_etiqueta.clear()
        opciones_cons: list[str] = []
        for c in conservadoras:
            etiqueta = f"{c.codigo} (Capacidad: {c.capacidad_maxima} muestras)"
            self._conservadoras_por_etiqueta[etiqueta] = c.id
            opciones_cons.append(etiqueta)

        if opciones_cons:
            self._combo_p4_conservadora.configure(values=opciones_cons)
            if self._combo_p4_conservadora.get() not in self._conservadoras_por_etiqueta:
                self._combo_p4_conservadora.set(opciones_cons[0])
        else:
            self._combo_p4_conservadora.configure(values=["Sin conservadoras disponibles"])
            self._combo_p4_conservadora.set("Sin conservadoras disponibles")

        # 4. Transportistas
        transportistas = self._srv_logistica.listar_transportistas()
        self._transportistas_por_etiqueta.clear()
        opciones_trans: list[str] = []
        for t in transportistas:
            patente = t.get("vehiculo_patente", "S/P")
            cuit = t.get("cuit_dni", "S/C")
            etiqueta = f"{t.get('nombre', '')} (Patente: {patente} - CUIT: {cuit})"
            self._transportistas_por_etiqueta[etiqueta] = int(t["id"])
            opciones_trans.append(etiqueta)

        if opciones_trans:
            self._combo_transportista.configure(values=opciones_trans)
            if self._combo_transportista.get() not in self._transportistas_por_etiqueta:
                self._combo_transportista.set(opciones_trans[0])

        # 5. Generar códigos sugeridos para P4 si están vacíos
        if not self._entrada_p4_remito.get().strip():
            marca = datetime.now().strftime("%H%M")
            self._entrada_p4_remito.insert(0, f"REM-{marca}")
        if not self._entrada_p4_precinto.get().strip():
            marca = datetime.now().strftime("%H%M")
            self._entrada_p4_precinto.insert(0, f"PREC-{marca}")

        # 6. Tabla general de remitos
        remitos = self._srv_logistica.listar_todos_los_remitos()
        filas_rem = []
        for r in remitos:
            if r.id is None:
                continue
            clinica_txt = self._nombre_por_clinica_id.get(r.clinica_origen_id, f"#{r.clinica_origen_id}")
            lab_txt = self._nombre_por_lab_id.get(r.laboratorio_destino_id, f"#{r.laboratorio_destino_id}")
            cons_txt = (
                f"{r.conservadora.codigo} ({r.conservadora.cantidad_muestras}/{r.conservadora.capacidad_maxima})"
                if r.conservadora
                else f"#{r.conservadora_id}"
            )
            prec_serie = r.precinto.numero_serie if r.precinto else "—"
            prec_estado = r.precinto.estado if r.precinto else "—"

            filas_rem.append(
                (
                    r.id,
                    (
                        r.id,
                        r.numero_remito,
                        r.estado,
                        clinica_txt,
                        lab_txt,
                        cons_txt,
                        prec_serie,
                        prec_estado,
                        len(r.muestras),
                        r.fecha_hora_creacion,
                    ),
                )
            )
        self._tabla_remitos.cargar_filas(filas_rem)
        total_rem = len(filas_rem)
        sufijo = "remito registrado" if total_rem == 1 else "remitos registrados"
        self._etiqueta_contador_remitos.configure(text=f"{total_rem} {sufijo}")

        # 7. Muestras extraídas pendientes de la clínica seleccionada
        self._recargar_muestras_extraidas_pendientes()

    def _recargar_muestras_extraidas_pendientes(self) -> None:
        """Carga en la tabla de la derecha las muestras en estado 'Extraida' de la clínica actual."""
        clinica_id = self._clinicas_por_nombre.get(self._combo_p4_clinica.get())
        muestras_extraidas = self._srv_logistica.listar_muestras_extraidas_pendientes(clinica_id)

        filas = []
        for m in muestras_extraidas:
            if m.id is None:
                continue
            seleccionada_txt = (
                "SÍ [SELECCIONADA]" if m.id in self._muestras_pendientes_seleccionadas else "No"
            )
            filas.append(
                (
                    m.id,
                    (
                        m.id,
                        m.codigo_muestra,
                        m.nombre_tipo_muestra,
                        f"#{m.orden_id}",
                        m.estado_actual,
                        m.fecha_hora_extraccion,
                        seleccionada_txt,
                    ),
                )
            )
        self._tabla_muestras_extraidas.cargar_filas(filas)
        total_extraidas = len(filas)
        self._etiqueta_muestras_disponibles.configure(
            text=f"Muestras Extraídas ({total_extraidas} disponibles para empaquetar):"
        )
