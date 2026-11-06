"""
Vista Gráfica: Proceso 7 — Resultados de Análisis y Facturación de Atención
===========================================================================

Coordina:
    - Proceso 7A: Registrar resultados de análisis bioquímicos sobre muestras
      biológicas viables recibidas en el laboratorio central (Patrón STATE).
      Solo permite procesar muestras en estado 'Recibida', bloqueando muestras
      rechazadas o en tránsito.
    - Proceso 7B: Liquidar y emitir comprobantes de atención médica con desglose
      polimórfico de aranceles (Patrón STRATEGY: Tarifa Estándar, Tarifa Urgencia
      y Tarifa Convenio Red).

Principios de Diseño POO aplicados:
    - Alta Cohesión / SRP: Pestañas independientes para carga bioquímica y facturación.
    - Bajo Acoplamiento / DIP: Recibe `ServicioLaboratorio` y `ServicioClinica` sin
      conocer detalles de persistencia ni SQL.
    - Experto en Información: Delega las liquidaciones y transiciones de estado
      en los objetos de dominio y patrones del núcleo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import customtkinter as ctk

from src.dominio.consulta_medica import FORMATO_FECHA_HORA, ConsultaMedica
from src.dominio.excepciones import ErrorDatosInvalidos
from src.dominio.facturacion import ComprobanteAtencion, ResultadoAnalisis
from src.dominio.muestra_biologica import MuestraBiologica
from src.interfaz.componentes.alertas import (
    ejecutar_accion_segura,
    limpiar_resaltado_campos,
    mostrar_advertencia,
    mostrar_exito,
)
from src.interfaz.componentes.tabla import TablaDatos
from src.patrones.estrategia_facturacion import (
    MAPA_ESTRATEGIAS,
    EstrategiaFacturacion,
    LiquidacionFactura,
    TarifaEstandar,
)
from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_laboratorio import ServicioLaboratorio

DESCRIPCION_ESTRATEGIAS: dict[str, str] = {
    "Tarifa Estándar": "Suma directa de arancel clínico de consulta y costo de estudios de laboratorio.",
    "Tarifa Urgencia": "+30% de recargo sobre los estudios de laboratorio procesados.",
    "Tarifa Convenio Red": "-15% de bonificación institucional sobre la consulta clínica.",
}


class VistaLaboratorio(ctk.CTkFrame):
    """Vista interactiva para el Proceso 7: Resultados Bioquímicos y Facturación con Strategy."""

    def __init__(
        self,
        master: Any,
        servicio_laboratorio: ServicioLaboratorio,
        servicio_clinica: ServicioClinica,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._srv_lab = servicio_laboratorio
        self._srv_clinica = servicio_clinica

        self._muestra_seleccionada_id: int | None = None
        self._consulta_seleccionada_id: int | None = None
        self._comprobante_seleccionado_id: int | None = None

        self._mapa_campos_resultado: dict[str, ctk.CTkBaseClass] = {}
        self._mapa_campos_facturacion: dict[str, ctk.CTkBaseClass] = {}

        # Mapeos de catálogos
        self._bioquimicos_por_etiqueta: dict[str, int] = {}
        self._consultas_por_etiqueta: dict[str, int] = {}
        self._consultas_por_id: dict[int, ConsultaMedica] = {}
        self._comprobantes_por_id: dict[int, ComprobanteAtencion] = {}
        self._muestras_recibidas_por_id: dict[int, MuestraBiologica] = {}
        self._muestras_analizadas_por_id: dict[int, MuestraBiologica] = {}

        self._construir_ui()
        self.refrescar_datos()

    # ==================================================================================
    # Construcción de la Interfaz (UI)
    # ==================================================================================

    def _construir_ui(self) -> None:
        """Construye la cabecera y el panel con dos pestañas de trabajo."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Cabecera principal
        marco_cabecera = ctk.CTkFrame(self, fg_color="transparent")
        marco_cabecera.grid(row=0, column=0, sticky="ew", padx=10, pady=(2, 6))

        ctk.CTkLabel(
            marco_cabecera,
            text="Proceso 7: Laboratorio Central, Resultados Bioquímicos y Facturación",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")

        self._etiqueta_resumen = ctk.CTkLabel(
            marco_cabecera,
            text="0 muestras pendientes | 0 comprobantes",
            font=ctk.CTkFont(size=13),
            text_color=("gray35", "gray70"),
        )
        self._etiqueta_resumen.pack(side="right", padx=8)

        # Tabview con las 2 áreas del Proceso 7
        self._tabview = ctk.CTkTabview(self, corner_radius=10)
        self._tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self._tab_analisis = self._tabview.add("1. Carga de Resultados Bioquímicos (State)")
        self._tab_facturacion = self._tabview.add("2. Liquidación y Facturación (Strategy)")

        self._construir_tab_analisis()
        self._construir_tab_facturacion()

    # ----------------------------------------------------------------------------------
    # Pestaña 1: Carga de Resultados de Análisis (Patrón State)
    # ----------------------------------------------------------------------------------

    def _construir_tab_analisis(self) -> None:
        """Diseña el formulario de carga bioquímica y las tablas de muestras recibidas/analizadas."""
        self._tab_analisis.grid_rowconfigure(0, weight=1)
        self._tab_analisis.grid_columnconfigure(0, weight=4, minsize=380)
        self._tab_analisis.grid_columnconfigure(1, weight=6)

        # --- Panel Izquierdo: Formulario de Carga ---
        panel_izq = ctk.CTkScrollableFrame(self._tab_analisis, corner_radius=8)
        panel_izq.grid(row=0, column=0, sticky="nsew", padx=(6, 8), pady=6)
        panel_izq.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel_izq,
            text="Registro de Informe Bioquímico",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        # Tarjeta informativa de la muestra activa
        self._marco_info_muestra = ctk.CTkFrame(panel_izq, fg_color=("gray90", "gray20"), corner_radius=8)
        self._marco_info_muestra.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self._marco_info_muestra.grid_columnconfigure(0, weight=1)

        self._lbl_info_muestra_titulo = ctk.CTkLabel(
            self._marco_info_muestra,
            text="Muestra: Ninguna seleccionada",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self._lbl_info_muestra_titulo.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        self._lbl_info_muestra_detalle = ctk.CTkLabel(
            self._marco_info_muestra,
            text="Seleccione una muestra en estado 'Recibida' en la tabla de la derecha para cargar su informe.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70"),
            wraplength=340,
            justify="left",
            anchor="w",
        )
        self._lbl_info_muestra_detalle.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))

        # Campos del formulario
        fila = 2

        ctk.CTkLabel(panel_izq, text="Bioquímico Firmante *:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=fila, column=0, sticky="w", padx=12, pady=(4, 2)
        )
        fila += 1
        self._combo_bioquimico = ctk.CTkComboBox(panel_izq, values=["(Sin profesionales)"], state="readonly")
        self._combo_bioquimico.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 6))
        self._mapa_campos_resultado["profesional_laboratorio_id"] = self._combo_bioquimico
        fila += 1

        ctk.CTkLabel(panel_izq, text="Costo del Análisis ($) *:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=fila, column=0, sticky="w", padx=12, pady=(4, 2)
        )
        fila += 1
        self._txt_costo_analisis = ctk.CTkEntry(panel_izq, placeholder_text="Ej: 4500.00")
        self._txt_costo_analisis.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 6))
        self._mapa_campos_resultado["costo_analisis"] = self._txt_costo_analisis
        fila += 1

        ctk.CTkLabel(panel_izq, text="Valores Medidos / Mediciones *:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=fila, column=0, sticky="w", padx=12, pady=(4, 2)
        )
        fila += 1
        self._txt_valores_medidos = ctk.CTkTextbox(panel_izq, height=75, corner_radius=6)
        self._txt_valores_medidos.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 6))
        self._mapa_campos_resultado["valores_medidos"] = self._txt_valores_medidos
        fila += 1

        ctk.CTkLabel(panel_izq, text="Conclusión Médica / Diagnóstico *:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=fila, column=0, sticky="w", padx=12, pady=(4, 2)
        )
        fila += 1
        self._txt_conclusion = ctk.CTkTextbox(panel_izq, height=75, corner_radius=6)
        self._txt_conclusion.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 6))
        self._mapa_campos_resultado["conclusion"] = self._txt_conclusion
        fila += 1

        ctk.CTkLabel(panel_izq, text="Observación de Trazabilidad:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=fila, column=0, sticky="w", padx=12, pady=(4, 2)
        )
        fila += 1
        self._txt_obs_resultado = ctk.CTkEntry(panel_izq, placeholder_text="Opcional: nota del procesamiento")
        self._txt_obs_resultado.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 6))
        fila += 1

        ctk.CTkLabel(panel_izq, text="Fecha y Hora de Carga *:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=fila, column=0, sticky="w", padx=12, pady=(4, 2)
        )
        fila += 1
        self._txt_fecha_analisis = ctk.CTkEntry(panel_izq)
        self._txt_fecha_analisis.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 10))
        fila += 1

        # Botones de acción del formulario (sin duplicados, nombres estándar)
        marco_botones = ctk.CTkFrame(panel_izq, fg_color="transparent")
        marco_botones.grid(row=fila, column=0, sticky="ew", padx=12, pady=(4, 14))
        marco_botones.grid_columnconfigure((0, 1), weight=1)

        self._btn_nuevo_resultado = ctk.CTkButton(
            marco_botones,
            text="Nuevo Resultado",
            fg_color="#64748B",
            hover_color="#475569",
            command=self._limpiar_formulario_resultado,
        )
        self._btn_nuevo_resultado.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self._btn_guardar_resultado = ctk.CTkButton(
            marco_botones,
            text="Registrar Resultado",
            fg_color="#16A34A",
            hover_color="#15803D",
            command=self._accion_registrar_resultado,
        )
        self._btn_guardar_resultado.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        # --- Panel Derecho: Tablas de Muestras ---
        panel_der = ctk.CTkFrame(self._tab_analisis, fg_color="transparent")
        panel_der.grid(row=0, column=1, sticky="nsew", padx=(6, 6), pady=6)
        panel_der.grid_rowconfigure(1, weight=1)
        panel_der.grid_rowconfigure(3, weight=1)
        panel_der.grid_columnconfigure(0, weight=1)

        # 1. Tabla de Muestras Pendientes (Recibidas + opción de auditar bloqueadas por State)
        marco_titulo_recibidas = ctk.CTkFrame(panel_der, fg_color="transparent")
        marco_titulo_recibidas.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(
            marco_titulo_recibidas,
            text="Muestras Biológicas en Bandeja de Laboratorio",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        self._lbl_cant_recibidas = ctk.CTkLabel(
            marco_titulo_recibidas,
            text="0 pendientes",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70"),
        )
        self._lbl_cant_recibidas.pack(side="right", padx=(8, 0))

        self._chk_incluir_bloqueadas = ctk.CTkCheckBox(
            marco_titulo_recibidas,
            text="Mostrar bloqueadas (Auditar Patrón State)",
            font=ctk.CTkFont(size=11),
            command=self._cargar_muestras_recibidas,
        )
        self._chk_incluir_bloqueadas.pack(side="right", padx=(8, 4))

        columnas_recibidas = [
            ("id", "ID", 45),
            ("codigo", "Cód. Muestra", 120),
            ("tipo", "Tipo de Muestra", 110),
            ("orden_id", "ID Orden", 65),
            ("fecha_extraccion", "Fecha Extracción", 135),
            ("estado", "Estado Actual", 85),
        ]
        self._tabla_recibidas = TablaDatos(
            panel_der,
            columnas=columnas_recibidas,
            al_seleccionar=self._al_seleccionar_muestra_recibida,
            altura_filas=8,
        )
        self._tabla_recibidas.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        # 2. Tabla de Muestras Analizadas (Completadas)
        marco_titulo_analizadas = ctk.CTkFrame(panel_der, fg_color="transparent")
        marco_titulo_analizadas.grid(row=2, column=0, sticky="ew", pady=(4, 4))
        ctk.CTkLabel(
            marco_titulo_analizadas,
            text="Historial de Muestras Analizadas (Resultados Emitidos)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        self._lbl_cant_analizadas = ctk.CTkLabel(
            marco_titulo_analizadas,
            text="0 analizadas",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70"),
        )
        self._lbl_cant_analizadas.pack(side="right")

        columnas_analizadas = [
            ("id", "ID", 45),
            ("codigo", "Cód. Muestra", 120),
            ("tipo", "Tipo", 100),
            ("bioquimico", "Bioquímico Firmante", 150),
            ("costo", "Arancel ($)", 85),
            ("fecha_analisis", "Fecha Análisis", 135),
        ]
        self._tabla_analizadas = TablaDatos(
            panel_der,
            columnas=columnas_analizadas,
            al_seleccionar=self._al_seleccionar_muestra_analizada,
            altura_filas=8,
        )
        self._tabla_analizadas.grid(row=3, column=0, sticky="nsew", pady=(0, 2))

    # ----------------------------------------------------------------------------------
    # Pestaña 2: Liquidación y Comprobantes de Atención (Patrón Strategy)
    # ----------------------------------------------------------------------------------

    def _construir_tab_facturacion(self) -> None:
        """Diseña el formulario de previsualización/emisión y el listado de comprobantes."""
        self._tab_facturacion.grid_rowconfigure(0, weight=1)
        self._tab_facturacion.grid_columnconfigure(0, weight=4, minsize=400)
        self._tab_facturacion.grid_columnconfigure(1, weight=6)

        # --- Panel Izquierdo: Configuración de Liquidación ---
        panel_izq = ctk.CTkScrollableFrame(self._tab_facturacion, corner_radius=8)
        panel_izq.grid(row=0, column=0, sticky="nsew", padx=(6, 8), pady=6)
        panel_izq.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel_izq,
            text="Emisión de Comprobante de Atención",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        fila = 1

        ctk.CTkLabel(panel_izq, text="Consulta Médica a Liquidar *:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=fila, column=0, sticky="w", padx=12, pady=(4, 2)
        )
        fila += 1
        self._combo_consulta = ctk.CTkComboBox(
            panel_izq,
            values=["(Sin consultas)"],
            state="readonly",
            command=self._al_cambiar_consulta_combo,
        )
        self._combo_consulta.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 6))
        self._mapa_campos_facturacion["consulta_id"] = self._combo_consulta
        fila += 1

        # Tarjeta informativa de la consulta seleccionada
        self._marco_info_consulta = ctk.CTkFrame(panel_izq, fg_color=("gray90", "gray20"), corner_radius=8)
        self._marco_info_consulta.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._marco_info_consulta.grid_columnconfigure(0, weight=1)

        self._lbl_info_consulta_titulo = ctk.CTkLabel(
            self._marco_info_consulta,
            text="Seleccione una consulta médica",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        self._lbl_info_consulta_titulo.grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))

        self._lbl_info_consulta_detalle = ctk.CTkLabel(
            self._marco_info_consulta,
            text="La consulta aportará el arancel clínico y los análisis completados vinculados.",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray70"),
            wraplength=340,
            justify="left",
            anchor="w",
        )
        self._lbl_info_consulta_detalle.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))
        fila += 1

        ctk.CTkLabel(
            panel_izq,
            text="Estrategia de Facturación (Patrón Strategy) *:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=fila, column=0, sticky="w", padx=12, pady=(4, 2))
        fila += 1

        self._combo_estrategia = ctk.CTkComboBox(
            panel_izq,
            values=["Tarifa Estándar", "Tarifa Urgencia", "Tarifa Convenio Red"],
            state="readonly",
            command=self._al_cambiar_estrategia_combo,
        )
        self._combo_estrategia.set("Tarifa Estándar")
        self._combo_estrategia.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 2))
        fila += 1

        self._lbl_desc_estrategia = ctk.CTkLabel(
            panel_izq,
            text=DESCRIPCION_ESTRATEGIAS["Tarifa Estándar"],
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray70"),
            wraplength=340,
            justify="left",
            anchor="w",
        )
        self._lbl_desc_estrategia.grid(row=fila, column=0, sticky="w", padx=12, pady=(0, 8))
        fila += 1

        # Botón para previsualizar liquidación polimórfica
        self._btn_previsualizar = ctk.CTkButton(
            panel_izq,
            text="Previsualizar Liquidación (Strategy)",
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._accion_previsualizar_liquidacion,
        )
        self._btn_previsualizar.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 10))
        fila += 1

        # Tarjeta de desglose de liquidación calculada
        self._marco_liquidacion = ctk.CTkFrame(panel_izq, fg_color=("#E0F2FE", "#0F2942"), corner_radius=8)
        self._marco_liquidacion.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 10))
        self._marco_liquidacion.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            self._marco_liquidacion,
            text="Desglose Calculado por Strategy:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#0369A1", "#7DD3FC"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(6, 4))

        self._lbl_subtotal_clinica = ctk.CTkLabel(
            self._marco_liquidacion,
            text="Subtotal Clínica: $0.00",
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self._lbl_subtotal_clinica.grid(row=1, column=0, sticky="w", padx=10, pady=1)

        self._lbl_subtotal_lab = ctk.CTkLabel(
            self._marco_liquidacion,
            text="Subtotal Lab: $0.00",
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self._lbl_subtotal_lab.grid(row=1, column=1, sticky="w", padx=10, pady=1)

        self._lbl_total_factura = ctk.CTkLabel(
            self._marco_liquidacion,
            text="TOTAL: $0.00",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("#0F766E", "#2DD4BF"),
            anchor="w",
        )
        self._lbl_total_factura.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(4, 8))
        fila += 1

        # Campos de comprobante
        ctk.CTkLabel(panel_izq, text="Número de Comprobante *:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=fila, column=0, sticky="w", padx=12, pady=(4, 2)
        )
        fila += 1
        self._txt_numero_comprobante = ctk.CTkEntry(panel_izq, placeholder_text="Ej: FAC-0001-00000001")
        self._txt_numero_comprobante.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 6))
        self._mapa_campos_facturacion["numero_comprobante"] = self._txt_numero_comprobante
        fila += 1

        ctk.CTkLabel(panel_izq, text="Fecha y Hora de Emisión *:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=fila, column=0, sticky="w", padx=12, pady=(4, 2)
        )
        fila += 1
        self._txt_fecha_emision = ctk.CTkEntry(panel_izq)
        self._txt_fecha_emision.grid(row=fila, column=0, sticky="ew", padx=12, pady=(0, 10))
        fila += 1

        # Botones de emisión (sin duplicados, nombres estándar)
        marco_botones_fac = ctk.CTkFrame(panel_izq, fg_color="transparent")
        marco_botones_fac.grid(row=fila, column=0, sticky="ew", padx=12, pady=(4, 14))
        marco_botones_fac.grid_columnconfigure((0, 1), weight=1)

        self._btn_nuevo_comprobante = ctk.CTkButton(
            marco_botones_fac,
            text="Nuevo Comprobante",
            fg_color="#64748B",
            hover_color="#475569",
            command=self._limpiar_formulario_facturacion,
        )
        self._btn_nuevo_comprobante.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self._btn_emitir_comprobante = ctk.CTkButton(
            marco_botones_fac,
            text="Emitir Comprobante",
            fg_color="#16A34A",
            hover_color="#15803D",
            command=self._accion_emitir_comprobante,
        )
        self._btn_emitir_comprobante.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        # --- Panel Derecho: Comprobantes Emitidos y Detalles ---
        panel_der = ctk.CTkFrame(self._tab_facturacion, fg_color="transparent")
        panel_der.grid(row=0, column=1, sticky="nsew", padx=(6, 6), pady=6)
        panel_der.grid_rowconfigure(1, weight=3)
        panel_der.grid_rowconfigure(3, weight=2)
        panel_der.grid_columnconfigure(0, weight=1)

        # 1. Tabla de comprobantes emitidos
        marco_titulo_comp = ctk.CTkFrame(panel_der, fg_color="transparent")
        marco_titulo_comp.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(
            marco_titulo_comp,
            text="Comprobantes de Atención Emitidos",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        self._lbl_cant_comprobantes = ctk.CTkLabel(
            marco_titulo_comp,
            text="0 emitidos",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70"),
        )
        self._lbl_cant_comprobantes.pack(side="right")

        columnas_comprobantes = [
            ("id", "ID", 45),
            ("numero", "Nro. Comprobante", 140),
            ("consulta_id", "ID Consulta", 75),
            ("estrategia", "Estrategia Tarifa", 160),
            ("total", "Total ($)", 90),
            ("fecha_emision", "Fecha Emisión", 135),
        ]
        self._tabla_comprobantes = TablaDatos(
            panel_der,
            columnas=columnas_comprobantes,
            al_seleccionar=self._al_seleccionar_comprobante,
            altura_filas=8,
        )
        self._tabla_comprobantes.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        # 2. Tabla de detalles desglosados del comprobante seleccionado
        marco_titulo_detalles = ctk.CTkFrame(panel_der, fg_color="transparent")
        marco_titulo_detalles.grid(row=2, column=0, sticky="ew", pady=(4, 4))
        ctk.CTkLabel(
            marco_titulo_detalles,
            text="Desglose de Ítems del Comprobante Seleccionado",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        self._lbl_comp_detalle_seleccionado = ctk.CTkLabel(
            marco_titulo_detalles,
            text="Seleccione un comprobante arriba",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70"),
        )
        self._lbl_comp_detalle_seleccionado.pack(side="right")

        columnas_detalles = [
            ("tipo", "Tipo Concepto", 110),
            ("concepto", "Descripción / Concepto", 320),
            ("monto", "Importe ($)", 95),
        ]
        self._tabla_detalles = TablaDatos(
            panel_der,
            columnas=columnas_detalles,
            altura_filas=8,
        )
        self._tabla_detalles.grid(row=3, column=0, sticky="nsew", pady=(0, 2))

    # ==================================================================================
    # Carga y Actualización de Datos (Refresco)
    # ==================================================================================

    def refrescar_datos(self) -> None:
        """Carga y actualiza todos los datos visuales desde los servicios."""
        self._cargar_profesionales_laboratorio()
        self._cargar_consultas()
        self._cargar_muestras_recibidas()
        self._cargar_muestras_analizadas()
        self._cargar_comprobantes()
        self._actualizar_contador_general()

    def _actualizar_contador_general(self) -> None:
        cant_rec = len(self._tabla_recibidas.obtener_todas_las_filas())
        cant_comp = len(self._tabla_comprobantes.obtener_todas_las_filas())
        self._etiqueta_resumen.configure(
            text=f"{cant_rec} muestra/s pendientes | {cant_comp} comprobante/s emitido/s"
        )

    def _cargar_profesionales_laboratorio(self) -> None:
        """Llena el selector de bioquímicos firmantes."""
        profesionales = self._srv_lab.listar_profesionales_laboratorio()
        self._bioquimicos_por_etiqueta.clear()

        etiquetas: list[str] = []
        for pl in profesionales:
            etiqueta = f"{pl['apellido']}, {pl['nombre']} (Mat: {pl['matricula']})"
            self._bioquimicos_por_etiqueta[etiqueta] = pl["id"]
            etiquetas.append(etiqueta)

        if etiquetas:
            self._combo_bioquimico.configure(values=etiquetas)
            if self._combo_bioquimico.get() not in self._bioquimicos_por_etiqueta:
                self._combo_bioquimico.set(etiquetas[0])
        else:
            self._combo_bioquimico.configure(values=["(Sin profesionales)"])
            self._combo_bioquimico.set("(Sin profesionales)")

    def _cargar_consultas(self) -> None:
        """Llena el selector de consultas médicas para facturación."""
        consultas = self._srv_clinica.listar_consultas()
        self._consultas_por_etiqueta.clear()
        self._consultas_por_id.clear()

        etiquetas: list[str] = []
        for c in consultas:
            if c.id is not None:
                self._consultas_por_id[c.id] = c
                # Buscamos nombre de la mascota
                mascota = self._srv_clinica.obtener_mascota(c.mascota_id)
                nombre_mascota = mascota.nombre if mascota else f"Mascota #{c.mascota_id}"
                comprobante_existente = self._srv_lab.obtener_comprobante_por_consulta(c.id)
                marca_facturado = " [FACTURADO]" if comprobante_existente else ""
                etiqueta = (
                    f"Consulta #{c.id} - {c.fecha_hora_inicio[:10]} - "
                    f"{nombre_mascota} (${c.costo_consulta:.2f}){marca_facturado}"
                )
                self._consultas_por_etiqueta[etiqueta] = c.id
                etiquetas.append(etiqueta)

        if etiquetas:
            self._combo_consulta.configure(values=etiquetas)
            if self._combo_consulta.get() not in self._consultas_por_etiqueta:
                self._combo_consulta.set(etiquetas[0])
                self._al_cambiar_consulta_combo(etiquetas[0])
        else:
            self._combo_consulta.configure(values=["(Sin consultas)"])
            self._combo_consulta.set("(Sin consultas)")

    def _cargar_muestras_recibidas(self) -> None:
        """
        Carga en la tabla las muestras en estado 'Recibida' listas para análisis.
        Si está activo el check de auditoría, incluye las muestras bloqueadas por State.
        """
        muestras = list(self._srv_lab.listar_muestras_recibidas_pendientes_analisis())
        incluir_bloqueadas = bool(
            hasattr(self, "_chk_incluir_bloqueadas") and self._chk_incluir_bloqueadas.get()
        )
        if incluir_bloqueadas:
            muestras.extend(self._srv_lab.listar_muestras_bloqueadas_para_analisis())

        self._muestras_recibidas_por_id.clear()
        filas = []
        for m in muestras:
            if m.id is None:
                continue
            self._muestras_recibidas_por_id[m.id] = m
            tipo_txt = m.nombre_tipo_muestra or f"Tipo {m.tipo_muestra_id}"
            filas.append(
                (
                    m.id,
                    (
                        m.id,
                        m.codigo_muestra,
                        tipo_txt,
                        m.orden_id,
                        m.fecha_hora_extraccion,
                        m.estado_actual,
                    ),
                )
            )
        self._tabla_recibidas.cargar_filas(filas)
        self._lbl_cant_recibidas.configure(text=f"{len(filas)} en bandeja")

    def _cargar_muestras_analizadas(self) -> None:
        """Carga las muestras que ya pasaron a 'Analizada'."""
        muestras = self._srv_lab.listar_muestras_analizadas()
        self._muestras_analizadas_por_id.clear()
        filas = []
        for m in muestras:
            if m.id is None:
                continue
            self._muestras_analizadas_por_id[m.id] = m
            resultado = self._srv_lab.obtener_resultado_de_muestra(m.id)
            bioquimico_nombre = resultado.bioquimico_nombre if resultado else "S/D"
            costo = f"${resultado.costo_analisis:.2f}" if resultado else "S/D"
            fecha_analisis = resultado.fecha_hora_analisis if resultado else "S/D"
            tipo_txt = m.nombre_tipo_muestra or f"Tipo {m.tipo_muestra_id}"

            filas.append(
                (
                    m.id,
                    (
                        m.id,
                        m.codigo_muestra,
                        tipo_txt,
                        bioquimico_nombre,
                        costo,
                        fecha_analisis,
                    ),
                )
            )
        self._tabla_analizadas.cargar_filas(filas)
        self._lbl_cant_analizadas.configure(text=f"{len(filas)} analizada/s")

    def _cargar_comprobantes(self) -> None:
        """Carga el historial de comprobantes de atención emitidos."""
        comprobantes = self._srv_lab.listar_comprobantes()
        self._comprobantes_por_id.clear()

        filas = []
        for comp in comprobantes:
            if comp.id is not None:
                self._comprobantes_por_id[comp.id] = comp
            filas.append(
                (
                    comp.id or 0,
                    (
                        comp.id or 0,
                        comp.numero_comprobante,
                        comp.consulta_id,
                        comp.estrategia_tarifa,
                        f"${comp.monto_total:.2f}",
                        comp.fecha_hora_emision,
                    ),
                )
            )
        self._tabla_comprobantes.cargar_filas(filas)
        self._lbl_cant_comprobantes.configure(text=f"{len(filas)} emitido/s")

    # ==================================================================================
    # Eventos de Selección y Control de UI
    # ==================================================================================

    def _al_seleccionar_muestra_recibida(self, seleccion: Any) -> None:
        """Carga la muestra seleccionada en el formulario de informe bioquímico."""
        limpiar_resaltado_campos(self._mapa_campos_resultado)
        if isinstance(seleccion, dict):
            muestra_id = int(seleccion["id"])
        else:
            muestra_id = int(seleccion)
        self._muestra_seleccionada_id = muestra_id

        m = self._muestras_recibidas_por_id.get(muestra_id)
        if m is not None:
            codigo = m.codigo_muestra
            tipo = m.nombre_tipo_muestra or f"Tipo {m.tipo_muestra_id}"
            orden_id = m.orden_id
            estado_txt = m.estado_actual
            motivo_txt = f" | Motivo: {m.motivo_rechazo}" if m.motivo_rechazo else ""
        elif isinstance(seleccion, dict):
            codigo = str(seleccion.get("codigo", ""))
            tipo = str(seleccion.get("tipo", ""))
            orden_id = int(seleccion.get("orden_id", 0))
            estado_txt = str(seleccion.get("estado", "Recibida"))
            motivo_txt = ""
        else:
            codigo = f"#{muestra_id}"
            tipo = ""
            orden_id = 0
            estado_txt = "Recibida"
            motivo_txt = ""

        self._lbl_info_muestra_titulo.configure(
            text=f"Muestra: {codigo} (ID #{muestra_id} - {tipo})"
        )
        self._lbl_info_muestra_detalle.configure(
            text=f"Orden de derivación #{orden_id} | Estado actual (Patrón State): {estado_txt}{motivo_txt}"
        )

        # Sugerir costo base de la orden si se puede consultar
        costo_sugerido = ""
        try:
            for c in self._consultas_por_id.values():
                for o in c.ordenes:
                    if o.id == orden_id:
                        costo_sugerido = f"{o.costo_base:.2f}"
                        break
        except Exception:
            pass

        self._txt_costo_analisis.delete(0, "end")
        if costo_sugerido:
            self._txt_costo_analisis.insert(0, costo_sugerido)
        else:
            self._txt_costo_analisis.insert(0, "4500.00")

        self._txt_fecha_analisis.delete(0, "end")
        self._txt_fecha_analisis.insert(0, datetime.now().strftime(FORMATO_FECHA_HORA))

    def _al_seleccionar_muestra_analizada(self, seleccion: Any) -> None:
        """Muestra la información técnica del resultado ya emitido."""
        if isinstance(seleccion, dict):
            muestra_id = int(seleccion["id"])
            codigo_muestra = str(seleccion.get("codigo", f"#{muestra_id}"))
        else:
            muestra_id = int(seleccion)
            m = self._muestras_analizadas_por_id.get(muestra_id)
            codigo_muestra = m.codigo_muestra if m else f"#{muestra_id}"

        resultado = self._srv_lab.obtener_resultado_de_muestra(muestra_id)
        if not resultado:
            return

        self._lbl_info_muestra_titulo.configure(
            text=f"Muestra: {codigo_muestra} (ANALIZADA)"
        )
        self._lbl_info_muestra_detalle.configure(
            text=(
                f"Bioquímico: {resultado.bioquimico_nombre} | Fecha: {resultado.fecha_hora_analisis}\n"
                f"Mediciones: {resultado.valores_medidos}\n"
                f"Conclusión: {resultado.conclusion}"
            )
        )

    def _al_cambiar_consulta_combo(self, seleccion: str) -> None:
        """Al seleccionar una consulta médica, actualiza la tarjeta informativa y el comprobante sugerido."""
        consulta_id = self._consultas_por_etiqueta.get(seleccion)
        if consulta_id is None:
            return
        self._consulta_seleccionada_id = consulta_id
        consulta = self._consultas_por_id.get(consulta_id)
        if not consulta:
            return

        mascota = self._srv_clinica.obtener_mascota(consulta.mascota_id)
        nombre_mascota = mascota.nombre if mascota else f"Mascota #{consulta.mascota_id}"
        comprobante_existente = self._srv_lab.obtener_comprobante_por_consulta(consulta_id)

        if comprobante_existente:
            self._lbl_info_consulta_titulo.configure(
                text=f"Consulta #{consulta.id} - YA FACTURADA"
            )
            self._lbl_info_consulta_detalle.configure(
                text=(
                    f"Comprobante: {comprobante_existente.numero_comprobante} | "
                    f"Monto: ${comprobante_existente.monto_total:.2f} ({comprobante_existente.estrategia_tarifa})\n"
                    f"Paciente: {nombre_mascota} | Motivo: {consulta.motivo}"
                )
            )
        else:
            self._lbl_info_consulta_titulo.configure(
                text=f"Consulta #{consulta.id} - Paciente: {nombre_mascota}"
            )
            self._lbl_info_consulta_detalle.configure(
                text=(
                    f"Fecha: {consulta.fecha_hora_inicio} | Arancel clínico base: ${consulta.costo_consulta:.2f}\n"
                    f"Motivo: {consulta.motivo} | Órdenes asociadas: {len(consulta.ordenes)}"
                )
            )

        # Sugerir número de comprobante único
        self._txt_numero_comprobante.delete(0, "end")
        self._txt_numero_comprobante.insert(0, f"FAC-0001-{consulta_id:06d}")

        self._txt_fecha_emision.delete(0, "end")
        self._txt_fecha_emision.insert(0, datetime.now().strftime(FORMATO_FECHA_HORA))

    def _al_cambiar_estrategia_combo(self, seleccion: str) -> None:
        """Actualiza el texto descriptivo de la estrategia seleccionada."""
        desc = DESCRIPCION_ESTRATEGIAS.get(seleccion, "")
        self._lbl_desc_estrategia.configure(text=desc)

    def _al_seleccionar_comprobante(self, seleccion: Any) -> None:
        """Muestra los ítems desglosados del comprobante seleccionado."""
        if isinstance(seleccion, dict):
            comprobante_id = int(seleccion["id"])
        else:
            comprobante_id = int(seleccion)
        self._comprobante_seleccionado_id = comprobante_id
        comp = self._comprobantes_por_id.get(comprobante_id)
        if not comp:
            return

        self._lbl_comp_detalle_seleccionado.configure(
            text=f"Comprobante: {comp.numero_comprobante} ({len(comp.detalles)} ítems)"
        )
        filas_detalles = [
            (
                idx,
                (
                    d.tipo_concepto,
                    d.concepto,
                    f"${d.monto:.2f}",
                ),
            )
            for idx, d in enumerate(comp.detalles, start=1)
        ]
        self._tabla_detalles.cargar_filas(filas_detalles)

    # ==================================================================================
    # Acciones de Negocio: Proceso 7A (Resultados) y 7B (Facturación)
    # ==================================================================================

    def _accion_registrar_resultado(self) -> None:
        """Valida y registra el informe bioquímico de la muestra en estado Recibida."""
        limpiar_resaltado_campos(self._mapa_campos_resultado)

        if self._muestra_seleccionada_id is None:
            mostrar_advertencia(
                "Selección requerida",
                "Por favor, seleccione una muestra en estado 'Recibida' de la tabla de la derecha.",
            )
            return

        bioquimico_etiqueta = self._combo_bioquimico.get()
        bioquimico_id = self._bioquimicos_por_etiqueta.get(bioquimico_etiqueta)
        if bioquimico_id is None:
            mostrar_advertencia("Bioquímico requerido", "Seleccione un profesional de laboratorio firmante.")
            return

        costo_texto = self._txt_costo_analisis.get().strip()
        valores_medidos = self._txt_valores_medidos.get("1.0", "end").strip()
        conclusion = self._txt_conclusion.get("1.0", "end").strip()
        observacion = self._txt_obs_resultado.get().strip()
        fecha_analisis = self._txt_fecha_analisis.get().strip() or None

        try:
            costo_analisis = float(costo_texto) if costo_texto else None
        except ValueError:
            mostrar_advertencia("Costo inválido", "El costo del análisis debe ser un valor numérico.")
            self._txt_costo_analisis.configure(border_color="#EF4444")
            return

        def _operacion() -> ResultadoAnalisis:
            return self._srv_lab.registrar_resultado_analisis(
                muestra_id=self._muestra_seleccionada_id,
                profesional_laboratorio_id=bioquimico_id,
                valores_medidos=valores_medidos,
                conclusion=conclusion,
                costo_analisis=costo_analisis,
                fecha_hora_analisis=fecha_analisis,
                observacion=observacion,
            )

        resultado = ejecutar_accion_segura(_operacion, mapa_campos=self._mapa_campos_resultado)
        if resultado is not None:
            mostrar_exito(
                "Resultado Registrado",
                f"El informe bioquímico fue guardado exitosamente.\n"
                f"La muestra pasó a estado 'Analizada'.\n"
                f"Bioquímico: {resultado.bioquimico_nombre}\n"
                f"Arancel liquidado: ${resultado.costo_analisis:.2f}",
            )
            self._limpiar_formulario_resultado()
            self.refrescar_datos()

    def _obtener_estrategia_seleccionada(self) -> EstrategiaFacturacion:
        """Instancia polimórficamente el objeto EstrategiaFacturacion elegido en la interfaz."""
        nombre_estrategia = self._combo_estrategia.get().strip()
        clase_estrategia = MAPA_ESTRATEGIAS.get(nombre_estrategia, TarifaEstandar)
        return clase_estrategia()

    def _accion_previsualizar_liquidacion(self) -> None:
        """Calcula polimórficamente la liquidación con el Patrón Strategy sin persistir."""
        if self._consulta_seleccionada_id is None:
            mostrar_advertencia("Consulta requerida", "Seleccione una consulta médica a liquidar.")
            return

        estrategia_obj = self._obtener_estrategia_seleccionada()

        def _operacion() -> LiquidacionFactura:
            return self._srv_lab.calcular_liquidacion_consulta(
                consulta_id=self._consulta_seleccionada_id,
                estrategia=estrategia_obj,
            )

        liquidacion = ejecutar_accion_segura(_operacion)
        if liquidacion is not None:
            self._lbl_subtotal_clinica.configure(text=f"Subtotal Clínica: ${liquidacion.subtotal_clinica:.2f}")
            self._lbl_subtotal_lab.configure(text=f"Subtotal Lab: ${liquidacion.subtotal_laboratorio:.2f}")
            self._lbl_total_factura.configure(
                text=f"TOTAL ({liquidacion.nombre_estrategia}): ${liquidacion.total:.2f}"
            )

            # Cargar los ítems en la tabla de detalles para vista previa
            filas_items = [
                (
                    idx,
                    (
                        it.tipo_concepto,
                        it.concepto,
                        f"${it.monto:.2f}",
                    ),
                )
                for idx, it in enumerate(liquidacion.items, start=1)
            ]
            self._lbl_comp_detalle_seleccionado.configure(
                text=f"Previsualización: {liquidacion.nombre_estrategia} ({len(liquidacion.items)} ítems)"
            )
            self._tabla_detalles.cargar_filas(filas_items)

    def _accion_emitir_comprobante(self) -> None:
        """Liquida y persiste de forma atómica el comprobante con el Patrón Strategy."""
        limpiar_resaltado_campos(self._mapa_campos_facturacion)

        if self._consulta_seleccionada_id is None:
            mostrar_advertencia("Consulta requerida", "Seleccione una consulta médica a facturar.")
            return

        numero_comp = self._txt_numero_comprobante.get().strip()
        estrategia_obj = self._obtener_estrategia_seleccionada()
        fecha_emision = self._txt_fecha_emision.get().strip() or None

        def _operacion() -> ComprobanteAtencion:
            return self._srv_lab.emitir_comprobante_atencion(
                consulta_id=self._consulta_seleccionada_id,
                numero_comprobante=numero_comp,
                estrategia=estrategia_obj,
                fecha_hora_emision=fecha_emision,
            )

        comprobante = ejecutar_accion_segura(_operacion, mapa_campos=self._mapa_campos_facturacion)
        if comprobante is not None:
            mostrar_exito(
                "Comprobante Emitido",
                f"Comprobante de atención #{comprobante.numero_comprobante} emitido con éxito.\n"
                f"Estrategia aplicada: {comprobante.estrategia_tarifa}\n"
                f"Monto Total: ${comprobante.monto_total:.2f}\n"
                f"Total de conceptos facturados: {len(comprobante.detalles)}",
            )
            self._limpiar_formulario_facturacion()
            self.refrescar_datos()

    # ==================================================================================
    # Limpieza de Formularios (Botones "Nuevo Resultado" y "Nuevo Comprobante")
    # ==================================================================================

    def _limpiar_formulario_resultado(self) -> None:
        """Limpia el formulario de carga de informes bioquímicos."""
        self._muestra_seleccionada_id = None
        limpiar_resaltado_campos(self._mapa_campos_resultado)
        self._lbl_info_muestra_titulo.configure(text="Muestra: Ninguna seleccionada")
        self._lbl_info_muestra_detalle.configure(
            text="Seleccione una muestra en estado 'Recibida' en la tabla de la derecha para cargar su informe."
        )
        self._txt_costo_analisis.delete(0, "end")
        self._txt_valores_medidos.delete("1.0", "end")
        self._txt_conclusion.delete("1.0", "end")
        self._txt_obs_resultado.delete(0, "end")
        self._txt_fecha_analisis.delete(0, "end")
        self._txt_fecha_analisis.insert(0, datetime.now().strftime(FORMATO_FECHA_HORA))
        self._tabla_recibidas.deseleccionar()
        self._tabla_analizadas.deseleccionar()

    def _limpiar_formulario_facturacion(self) -> None:
        """Limpia el formulario y la previsualización de facturación."""
        limpiar_resaltado_campos(self._mapa_campos_facturacion)
        self._comprobante_seleccionado_id = None
        self._lbl_subtotal_clinica.configure(text="Subtotal Clínica: $0.00")
        self._lbl_subtotal_lab.configure(text="Subtotal Lab: $0.00")
        self._lbl_total_factura.configure(text="TOTAL: $0.00")
        self._txt_numero_comprobante.delete(0, "end")
        self._txt_fecha_emision.delete(0, "end")
        self._txt_fecha_emision.insert(0, datetime.now().strftime(FORMATO_FECHA_HORA))
        self._lbl_comp_detalle_seleccionado.configure(text="Seleccione un comprobante arriba")
        self._tabla_detalles.limpiar()
        self._tabla_comprobantes.deseleccionar()
