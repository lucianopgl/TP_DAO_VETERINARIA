"""
Vista Gráfica: Reportes Gerenciales, Sanitarios y Exportación CSV (`VistaReportes`)
===================================================================================

Presenta de forma interactiva los 5 reportes no triviales exigidos por el
Trabajo Práctico Integrador (Cátedra DAO - UTN FRC):
    1. Atenciones clínicas y derivaciones realizadas (por clínica y período).
    2. Muestras biológicas rechazadas por fallas en el transporte (precinto Roto/Violado).
    3. Tratamientos aplicados y vacunas obligatorias pendientes por mascota.
    4. Facturación desglosada por clínica, servicios de laboratorio y estrategia (Strategy).
    5. Tiempo promedio de tránsito y procesamiento de muestras biológicas (SLA).

Incluye filtros por rango de fechas y clínica de la red, tarjetas de indicadores
clave (KPIs) y exportación directa a formato CSV estándar UTF-8.

Principios de Diseño POO aplicados:
    - Alta Cohesión / SRP: Responsable exclusivamente de la visualización tabular
      de métricas y la interacción de exportación de informes.
    - Bajo Acoplamiento / DIP: Se comunica únicamente con `ServicioReportes` y
      `ServicioClinica` sin conocer consultas SQL ni `sqlite3`.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Any

import customtkinter as ctk

from src.interfaz.componentes.alertas import (
    COLOR_BORDE_NORMAL,
    ejecutar_accion_segura,
    limpiar_resaltado_campos,
    mostrar_advertencia,
    mostrar_exito,
)
from src.interfaz.componentes.tabla import TablaDatos
from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_reportes import ServicioReportes

OPCION_TODAS_LAS_CLINICAS = "Todas las clínicas de la red"

TAB_ATENCIONES = "1. Atenciones y Derivaciones"
TAB_RECHAZOS = "2. Muestras Rechazadas"
TAB_VACUNAS_TRAT = "3. Tratamientos y Vacunas"
TAB_FACTURACION = "4. Facturación (Strategy)"
TAB_TIEMPOS_SLA = "5. Tiempos de Tránsito y SLA"


class VistaReportes(ctk.CTkFrame):
    """Vista interactiva para los 5 reportes gerenciales/sanitarios y exportación a CSV."""

    def __init__(
        self,
        master: Any,
        servicio_reportes: ServicioReportes,
        servicio_clinica: ServicioClinica,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._srv_reportes = servicio_reportes
        self._srv_clinica = servicio_clinica

        self._clinicas_por_nombre: dict[str, int] = {}
        self._mapa_campos_filtro: dict[str, ctk.CTkBaseClass] = {}
        self._datos_exportables_por_tab: dict[str, list[dict[str, Any]]] = {
            TAB_ATENCIONES: [],
            TAB_RECHAZOS: [],
            TAB_VACUNAS_TRAT: [],
            TAB_FACTURACION: [],
            TAB_TIEMPOS_SLA: [],
        }
        self._tablas_exportables_por_tab: dict[str, list[tuple[str, list[dict[str, Any]], str]]] = {
            TAB_ATENCIONES: [],
            TAB_RECHAZOS: [],
            TAB_VACUNAS_TRAT: [],
            TAB_FACTURACION: [],
            TAB_TIEMPOS_SLA: [],
        }
        self._kpis_por_tab: dict[str, tuple[tuple[str, str], tuple[str, str], tuple[str, str]]] = {}

        self._construir_ui()
        self.refrescar_datos()

    # ==================================================================================
    # Construcción de la Interfaz (UI)
    # ==================================================================================

    def _construir_ui(self) -> None:
        """Organiza la cabecera, barra de filtros, tarjetas KPI y las 5 pestañas de reportes."""
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Fila 0: Cabecera principal
        marco_cabecera = ctk.CTkFrame(self, fg_color="transparent")
        marco_cabecera.grid(row=0, column=0, sticky="ew", padx=10, pady=(2, 4))

        ctk.CTkLabel(
            marco_cabecera,
            text="Reportes Gerenciales, Auditoría Sanitaria y Exportación CSV",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")

        self._etiqueta_estado_reportes = ctk.CTkLabel(
            marco_cabecera,
            text="5 reportes analíticos activos",
            font=ctk.CTkFont(size=13),
            text_color=("gray35", "gray70"),
        )
        self._etiqueta_estado_reportes.pack(side="right", padx=8)

        # Fila 1: Barra de filtros globales y botón de exportación CSV
        self._construir_barra_filtros()

        # Fila 2: Tarjetas de Indicadores Clave (KPIs) dinámicos
        self._construir_panel_kpis()

        # Fila 3: Pestañas de los 5 reportes no triviales
        self._construir_pestanas_reportes()

    def _construir_barra_filtros(self) -> None:
        """Crea la barra superior de filtrado por clínica, rango de fechas y exportación CSV."""
        barra = ctk.CTkFrame(self, corner_radius=10)
        barra.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        barra.grid_columnconfigure(1, weight=2)

        # Fila 0: Parámetros de filtrado
        ctk.CTkLabel(
            barra, text="Clínica:", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, padx=(12, 6), pady=(8, 4), sticky="w")

        self._combo_clinica = ctk.CTkComboBox(
            barra,
            values=[OPCION_TODAS_LAS_CLINICAS],
            height=30,
            state="readonly",
            command=lambda _: self._al_aplicar_filtros(),
        )
        self._combo_clinica.set(OPCION_TODAS_LAS_CLINICAS)
        self._combo_clinica.grid(row=0, column=1, padx=(0, 10), pady=(8, 4), sticky="ew")

        ctk.CTkLabel(
            barra, text="Desde (AAAA-MM-DD):", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=2, padx=(4, 4), pady=(8, 4), sticky="w")

        self._entrada_fecha_desde = ctk.CTkEntry(
            barra, placeholder_text="Ej: 2026-01-01", width=115, height=30
        )
        self._entrada_fecha_desde.grid(row=0, column=3, padx=(0, 10), pady=(8, 4))
        self._entrada_fecha_desde.bind(
            "<Key>", lambda _: self._entrada_fecha_desde.configure(border_color=COLOR_BORDE_NORMAL)
        )
        self._mapa_campos_filtro["fecha_desde"] = self._entrada_fecha_desde

        ctk.CTkLabel(
            barra, text="Hasta (AAAA-MM-DD):", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=4, padx=(4, 4), pady=(8, 4), sticky="w")

        self._entrada_fecha_hasta = ctk.CTkEntry(
            barra, placeholder_text="Ej: 2026-12-31", width=115, height=30
        )
        self._entrada_fecha_hasta.grid(row=0, column=5, padx=(0, 10), pady=(8, 4))
        self._entrada_fecha_hasta.bind(
            "<Key>", lambda _: self._entrada_fecha_hasta.configure(border_color=COLOR_BORDE_NORMAL)
        )
        self._mapa_campos_filtro["fecha_hasta"] = self._entrada_fecha_hasta

        ctk.CTkButton(
            barra,
            text="Actualizar Reportes",
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            height=30,
            width=140,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._al_aplicar_filtros,
        ).grid(row=0, column=6, padx=(0, 6), pady=(8, 4))

        ctk.CTkButton(
            barra,
            text="Limpiar Filtros",
            fg_color="#475569",
            hover_color="#334155",
            height=30,
            width=100,
            command=self._al_limpiar_filtros,
        ).grid(row=0, column=7, padx=(0, 12), pady=(8, 4))

        # Fila 1: Botones explícitos de exportación a CSV
        marco_export = ctk.CTkFrame(barra, fg_color="transparent")
        marco_export.grid(row=1, column=0, columnspan=8, sticky="ew", padx=12, pady=(2, 8))

        ctk.CTkLabel(
            marco_export,
            text="Exportación de Datos (CSV):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray40", "gray70"),
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            marco_export,
            text="Exportar Pestaña Actual (.CSV)",
            fg_color="#15803D",
            hover_color="#166534",
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._al_exportar_pestana_actual_csv,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            marco_export,
            text="Exportar Todos los Reportes (5 Reportes) (.CSV)",
            fg_color="#0284C7",
            hover_color="#0369A1",
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._al_exportar_todos_los_reportes_csv,
        ).pack(side="left", padx=(0, 10))

    def _construir_panel_kpis(self) -> None:
        """Crea las 3 tarjetas de resumen ejecutivo (KPIs) del reporte activo."""
        marco_kpis = ctk.CTkFrame(self, fg_color="transparent")
        marco_kpis.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 4))
        marco_kpis.grid_columnconfigure((0, 1, 2), weight=1)

        self._tarjetas_kpi: list[tuple[ctk.CTkLabel, ctk.CTkLabel]] = []
        colores_borde = [("#DBEAFE", "#1E3A8A"), ("#DCFCE7", "#14532D"), ("#FEF3C7", "#78350F")]

        for idx in range(3):
            tarjeta = ctk.CTkFrame(marco_kpis, corner_radius=8, fg_color=colores_borde[idx])
            tarjeta.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 6, 0), pady=2)
            tarjeta.grid_columnconfigure(0, weight=1)

            lbl_titulo = ctk.CTkLabel(
                tarjeta,
                text="Indicador",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=("#334155", "#CBD5E1"),
                anchor="w",
            )
            lbl_titulo.grid(row=0, column=0, sticky="w", padx=12, pady=(6, 0))

            lbl_valor = ctk.CTkLabel(
                tarjeta,
                text="—",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=("#0F172A", "#F8FAFC"),
                anchor="w",
            )
            lbl_valor.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 6))
            self._tarjetas_kpi.append((lbl_titulo, lbl_valor))

    def _construir_pestanas_reportes(self) -> None:
        """Crea el contenedor de pestañas para cada uno de los 5 reportes."""
        self._tabs = ctk.CTkTabview(
            self,
            corner_radius=10,
            command=self._al_cambiar_pestana_reporte,
        )
        self._tabs.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 8))

        tab1 = self._tabs.add(TAB_ATENCIONES)
        tab2 = self._tabs.add(TAB_RECHAZOS)
        tab3 = self._tabs.add(TAB_VACUNAS_TRAT)
        tab4 = self._tabs.add(TAB_FACTURACION)
        tab5 = self._tabs.add(TAB_TIEMPOS_SLA)

        self._construir_tab_atenciones(tab1)
        self._construir_tab_rechazos(tab2)
        self._construir_tab_vacunas_y_tratamientos(tab3)
        self._construir_tab_facturacion(tab4)
        self._construir_tab_tiempos_sla(tab5)

    def _construir_tab_atenciones(self, tab: ctk.CTkFrame) -> None:
        """Reporte 1: Atenciones clínicas y derivaciones realizadas."""
        tab.grid_rowconfigure(1, weight=2)
        tab.grid_rowconfigure(3, weight=4)
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab,
            text="Resumen Consolidado por Sede Veterinaria:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(2, 2))

        cols_resumen = [
            ("clinica", "Clínica Veterinaria", 240),
            ("consultas", "Total Consultas", 120),
            ("derivaciones", "Órdenes Derivación", 135),
            ("urgentes", "Deriv. Urgentes", 120),
            ("muestras", "Muestras Extraídas", 135),
            ("monto", "Arancel Consultas ($)", 150),
        ]
        self._tabla_r1_resumen = TablaDatos(tab, columnas=cols_resumen, altura_filas=3)
        self._tabla_r1_resumen.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        ctk.CTkLabel(
            tab,
            text="Detalle de Atenciones Clínicas y Derivaciones Emitidas:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=2, column=0, sticky="w", padx=6, pady=(2, 2))

        cols_detalle = [
            ("id", "Consulta #", 75),
            ("fecha", "Fecha / Hora", 140),
            ("clinica", "Clínica", 165),
            ("veterinario", "Veterinario", 155),
            ("mascota", "Paciente (Especie)", 150),
            ("cliente", "Cliente Responsable", 155),
            ("motivo", "Motivo / Diagnóstico", 190),
            ("ordenes", "Órdenes", 70),
            ("estudios", "Estudios Solicitados", 190),
            ("muestras", "Muestras", 75),
            ("costo", "Arancel ($)", 100),
        ]
        self._tabla_r1_detalle = TablaDatos(tab, columnas=cols_detalle, altura_filas=6)
        self._tabla_r1_detalle.grid(row=3, column=0, sticky="nsew", padx=6, pady=(0, 4))

    def _construir_tab_rechazos(self, tab: ctk.CTkFrame) -> None:
        """Reporte 2: Muestras biológicas rechazadas por fallas en el transporte."""
        tab.grid_rowconfigure(1, weight=2)
        tab.grid_rowconfigure(3, weight=4)
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab,
            text="Distribución de Rechazos por Clínica de Origen y Estado del Precinto Sanitario:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(2, 2))

        cols_res_rech = [
            ("criterio", "Dimensión de Auditoría", 180),
            ("categoria", "Clínica / Estado de Precinto", 320),
            ("cantidad", "Muestras Rechazadas", 160),
        ]
        self._tabla_r2_resumen = TablaDatos(tab, columnas=cols_res_rech, altura_filas=3)
        self._tabla_r2_resumen.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        ctk.CTkLabel(
            tab,
            text="Nómina de Muestras Biológicas Rechazadas en Recepción (Trazabilidad de Transporte):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=2, column=0, sticky="w", padx=6, pady=(2, 2))

        cols_det_rech = [
            ("id", "ID", 45),
            ("codigo", "Código Muestra", 130),
            ("tipo", "Tipo Muestra", 125),
            ("remito", "Remito N°", 105),
            ("clinica", "Clínica Origen", 165),
            ("conservadora", "Conservadora", 110),
            ("precinto", "Precinto Serie", 120),
            ("estado_prec", "Estado Precinto", 115),
            ("transportista", "Transportista", 160),
            ("recepcion", "Fecha Recepción", 140),
            ("motivo", "Motivo de Rechazo", 240),
        ]
        self._tabla_r2_detalle = TablaDatos(tab, columnas=cols_det_rech, altura_filas=6)
        self._tabla_r2_detalle.grid(row=3, column=0, sticky="nsew", padx=6, pady=(0, 4))

    def _construir_tab_vacunas_y_tratamientos(self, tab: ctk.CTkFrame) -> None:
        """Reporte 3: Tratamientos aplicados y vacunas obligatorias pendientes."""
        tab.grid_rowconfigure(1, weight=3)
        tab.grid_rowconfigure(3, weight=3)
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab,
            text="Control Epidemiológico: Vacunas Obligatorias Pendientes o Vencidas por Mascota:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#991B1B", "#FCA5A5"),
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(2, 2))

        cols_vac = [
            ("mascota_id", "ID Paciente", 80),
            ("mascota", "Mascota", 130),
            ("especie", "Especie", 95),
            ("cliente", "Cliente Responsable", 175),
            ("telefono", "Teléfono Contacto", 130),
            ("vacuna", "Vacuna Obligatoria", 185),
            ("ultima", "Última Aplicación", 130),
            ("motivo", "Diagnóstico de Vigencia", 240),
        ]
        self._tabla_r3_vacunas = TablaDatos(tab, columnas=cols_vac, altura_filas=4)
        self._tabla_r3_vacunas.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        ctk.CTkLabel(
            tab,
            text="Registro Consolidado de Tratamientos Farmacológicos Prescriptos en Consultas:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=2, column=0, sticky="w", padx=6, pady=(2, 2))

        cols_trat = [
            ("id", "ID", 45),
            ("fecha", "Fecha Consulta", 140),
            ("clinica", "Clínica", 165),
            ("veterinario", "Veterinario", 155),
            ("mascota", "Mascota (Especie)", 145),
            ("medicamento", "Medicamento", 160),
            ("dosis", "Posología / Dosis", 150),
            ("duracion", "Duración", 85),
            ("descripcion", "Indicación Terapéutica", 230),
        ]
        self._tabla_r3_tratamientos = TablaDatos(tab, columnas=cols_trat, altura_filas=4)
        self._tabla_r3_tratamientos.grid(row=3, column=0, sticky="nsew", padx=6, pady=(0, 4))

    def _construir_tab_facturacion(self, tab: ctk.CTkFrame) -> None:
        """Reporte 4: Facturación desglosada por clínica, servicios y estrategia."""
        tab.grid_rowconfigure(1, weight=3)
        tab.grid_rowconfigure(3, weight=3)
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab,
            text="Estado Financiero Desglosado por Clínica Veterinaria:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(2, 2))

        cols_fac_cli = [
            ("clinica", "Clínica Veterinaria", 220),
            ("comprobantes", "Comprobantes", 110),
            ("consultas", "Subtotal Consultas ($)", 150),
            ("laboratorio", "Subtotal Laboratorio ($)", 160),
            ("recargos", "Recargos Urgencia ($)", 150),
            ("bonificaciones", "Bonificaciones Red ($)", 150),
            ("total", "Total Facturado ($)", 150),
        ]
        self._tabla_r4_clinica = TablaDatos(tab, columnas=cols_fac_cli, altura_filas=4)
        self._tabla_r4_clinica.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        ctk.CTkLabel(
            tab,
            text="Rendimiento por Estrategia de Tarifa Aplicada (Patrón Strategy):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=2, column=0, sticky="w", padx=6, pady=(2, 2))

        cols_fac_est = [
            ("estrategia", "Estrategia de Facturación (Patrón Strategy)", 340),
            ("cantidad", "Comprobantes Emitidos", 180),
            ("total", "Monto Total Liquidado ($)", 200),
        ]
        self._tabla_r4_estrategia = TablaDatos(tab, columnas=cols_fac_est, altura_filas=4)
        self._tabla_r4_estrategia.grid(row=3, column=0, sticky="nsew", padx=6, pady=(0, 4))

    def _construir_tab_tiempos_sla(self, tab: ctk.CTkFrame) -> None:
        """Reporte 5: Tiempo promedio de tránsito y procesamiento de muestras."""
        tab.grid_rowconfigure(1, weight=2)
        tab.grid_rowconfigure(3, weight=4)
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab,
            text="Promedios de Desempeño Logístico y Bioquímico (SLA) por Clínica:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(2, 2))

        cols_sla_prom = [
            ("clinica", "Clínica de Origen", 240),
            ("evaluadas", "Muestras Evaluadas", 145),
            ("transito", "Promedio Tránsito en Ruta (hs)", 200),
            ("lab", "Promedio Procesamiento Lab (hs)", 210),
            ("total", "Promedio Ciclo Diagnóstico Total (hs)", 220),
        ]
        self._tabla_r5_promedios = TablaDatos(tab, columnas=cols_sla_prom, altura_filas=3)
        self._tabla_r5_promedios.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        ctk.CTkLabel(
            tab,
            text="Cronología Detallada por Muestra Biológica (Tiempos en Horas):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=2, column=0, sticky="w", padx=6, pady=(2, 2))

        cols_sla_det = [
            ("id", "ID", 45),
            ("codigo", "Código Muestra", 130),
            ("estudio", "Estudio Solicitado", 165),
            ("prioridad", "Prioridad", 85),
            ("clinica", "Clínica Origen", 160),
            ("estado", "Estado (State)", 110),
            ("espera", "Espera Clínica (hs)", 130),
            ("transito", "Tránsito Ruta (hs)", 130),
            ("lab", "Proceso Lab (hs)", 125),
            ("total", "Ciclo Total (hs)", 120),
        ]
        self._tabla_r5_detalle = TablaDatos(tab, columnas=cols_sla_det, altura_filas=6)
        self._tabla_r5_detalle.grid(row=3, column=0, sticky="nsew", padx=6, pady=(0, 4))

    # ==================================================================================
    # Manejadores de Eventos y Exportación
    # ==================================================================================

    def _validar_formato_fecha_opcional(self, texto: str, nombre_campo: str) -> str | None:
        """Delega la validación de fecha ISO y calendario gregoriano en `ServicioReportes` (DRY)."""
        return self._srv_reportes.validar_fecha_iso(texto, nombre_campo)

    def _al_aplicar_filtros(self) -> None:
        """Valida los filtros de fecha/clínica y recalcula los 5 reportes."""
        ejecutar_accion_segura(
            self.refrescar_datos,
            mapa_campos=self._mapa_campos_filtro,
            titulo_error="Filtro de reporte inválido",
        )

    def _al_limpiar_filtros(self) -> None:
        """Restablece los filtros a sus valores globales y recarga los reportes."""
        limpiar_resaltado_campos(self._mapa_campos_filtro)
        self._combo_clinica.set(OPCION_TODAS_LAS_CLINICAS)
        self._entrada_fecha_desde.delete(0, "end")
        self._entrada_fecha_hasta.delete(0, "end")
        self.refrescar_datos()

    def _al_cambiar_pestana_reporte(self) -> None:
        """Actualiza las tarjetas KPI superiores según la pestaña activa."""
        tab_actual = self._tabs.get()
        kpis = self._kpis_por_tab.get(tab_actual)
        if not kpis:
            return
        for idx, (titulo, valor) in enumerate(kpis):
            if idx < len(self._tarjetas_kpi):
                lbl_tit, lbl_val = self._tarjetas_kpi[idx]
                lbl_tit.configure(text=titulo)
                lbl_val.configure(text=valor)

    def _al_exportar_pestana_actual_csv(self) -> None:
        """Exporta a formato CSV todas las tablas de datos de la pestaña activa en pantalla."""
        tab_actual = self._tabs.get()
        tablas = self._tablas_exportables_por_tab.get(tab_actual, [])
        tablas_con_datos = [(nom, filas, suf) for nom, filas, suf in tablas if filas]

        if not tablas_con_datos:
            mostrar_advertencia(
                "Sin registros para exportar",
                f"El reporte '{tab_actual}' no contiene filas con los filtros actuales.",
            )
            return

        nombres_sugeridos = {
            TAB_ATENCIONES: "reporte_1_atenciones_y_derivaciones.csv",
            TAB_RECHAZOS: "reporte_2_muestras_rechazadas_transporte.csv",
            TAB_VACUNAS_TRAT: "reporte_3_tratamientos_y_vacunas.csv",
            TAB_FACTURACION: "reporte_4_facturacion_desglosada.csv",
            TAB_TIEMPOS_SLA: "reporte_5_tiempos_transito_y_sla.csv",
        }
        archivo_sugerido = nombres_sugeridos.get(tab_actual, "reporte_veterinaria.csv")

        ruta_elegida = filedialog.asksaveasfilename(
            title=f"Exportar '{tab_actual}' a CSV",
            defaultextension=".csv",
            initialfile=archivo_sugerido,
            filetypes=[("Archivo CSV (UTF-8)", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if not ruta_elegida:
            return

        ruta_base = Path(ruta_elegida)
        archivos_creados: list[tuple[str, Path, int]] = []

        if len(tablas_con_datos) == 1:
            nom, filas, _ = tablas_con_datos[0]
            ruta_gen = self._srv_reportes.exportar_a_csv(filas, ruta_base)
            archivos_creados.append((nom, ruta_gen, len(filas)))
        else:
            # La tabla principal se guarda con la ruta exacta elegida por el usuario
            nom_ppal, filas_ppal, _ = tablas_con_datos[0]
            ruta_gen_ppal = self._srv_reportes.exportar_a_csv(filas_ppal, ruta_base)
            archivos_creados.append((nom_ppal, ruta_gen_ppal, len(filas_ppal)))

            # Las tablas secundarias se guardan en la misma carpeta con sufijos descriptivos
            stem = ruta_base.stem
            parent = ruta_base.parent
            for nom, filas, suf in tablas_con_datos[1:]:
                nombre_archivo = f"{stem}_{suf}.csv"
                ruta_tabla = parent / nombre_archivo
                ruta_gen = self._srv_reportes.exportar_a_csv(filas, ruta_tabla)
                archivos_creados.append((nom, ruta_gen, len(filas)))

        resumen_archivos = "\n".join(
            f"• {nom}: {cant} registros -> {path.name}"
            for nom, path, cant in archivos_creados
        )
        mostrar_exito(
            "Exportación de Pestaña Completada",
            f"Se exportaron exitosamente las dimensiones de '{tab_actual}':\n\n"
            f"{resumen_archivos}\n\n"
            f"Carpeta: {ruta_base.parent}",
        )

    def _al_exportar_todos_los_reportes_csv(self) -> None:
        """Exporta los 5 reportes analíticos completos a una carpeta seleccionada."""
        ruta_dir = filedialog.askdirectory(
            title="Seleccionar carpeta de destino para el paquete completo de reportes"
        )
        if not ruta_dir:
            return

        clinica_id = self._clinicas_por_nombre.get(self._combo_clinica.get())
        fecha_desde = self._validar_formato_fecha_opcional(
            self._entrada_fecha_desde.get(), "fecha_desde"
        )
        fecha_hasta = self._validar_formato_fecha_opcional(
            self._entrada_fecha_hasta.get(), "fecha_hasta"
        )

        archivos = ejecutar_accion_segura(
            lambda: self._srv_reportes.exportar_paquete_completo_csv(
                directorio_destino=Path(ruta_dir),
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                clinica_id=clinica_id,
            ),
            titulo_error="No se pudo exportar el paquete de reportes",
        )
        if archivos:
            resumen_archivos = "\n".join(
                f"• {nom} -> {path.name}"
                for nom, path in archivos.items()
            )
            mostrar_exito(
                "Paquete Completo Exportado",
                f"Se generaron exitosamente {len(archivos)} archivos CSV con todos los reportes de la red:\n\n"
                f"{resumen_archivos}\n\n"
                f"Carpeta de destino:\n{ruta_dir}",
            )

    # Alias para compatibilidad con código existente o pruebas unitarias
    _al_exportar_csv = _al_exportar_pestana_actual_csv

    # ==================================================================================
    # Carga y Refresco de los 5 Reportes
    # ==================================================================================

    def refrescar_datos(self) -> None:
        """Consulta los catálogos y actualiza los 5 reportes desde `ServicioReportes`."""
        limpiar_resaltado_campos(self._mapa_campos_filtro)

        # 1. Catálogo de clínicas para el filtro
        clinicas = self._srv_clinica.listar_clinicas()
        self._clinicas_por_nombre = {c["nombre"]: int(c["id"]) for c in clinicas}
        opciones_clinicas = [OPCION_TODAS_LAS_CLINICAS] + list(self._clinicas_por_nombre.keys())
        seleccion_previa = self._combo_clinica.get()
        self._combo_clinica.configure(values=opciones_clinicas)
        if seleccion_previa in opciones_clinicas:
            self._combo_clinica.set(seleccion_previa)
        else:
            self._combo_clinica.set(OPCION_TODAS_LAS_CLINICAS)

        clinica_id = self._clinicas_por_nombre.get(self._combo_clinica.get())
        fecha_desde = self._validar_formato_fecha_opcional(
            self._entrada_fecha_desde.get(), "fecha_desde"
        )
        fecha_hasta = self._validar_formato_fecha_opcional(
            self._entrada_fecha_hasta.get(), "fecha_hasta"
        )
        self._srv_reportes.validar_rango_fechas(fecha_desde, fecha_hasta)

        self._cargar_reporte_1_atenciones(fecha_desde, fecha_hasta, clinica_id)
        self._cargar_reporte_2_rechazos(clinica_id)
        self._cargar_reporte_3_vacunas_y_tratamientos(fecha_hasta, clinica_id)
        self._cargar_reporte_4_facturacion(fecha_desde, fecha_hasta, clinica_id)
        self._cargar_reporte_5_tiempos_sla(clinica_id)

        self._al_cambiar_pestana_reporte()

    def _cargar_reporte_1_atenciones(
        self,
        fecha_desde: str | None,
        fecha_hasta: str | None,
        clinica_id: int | None,
    ) -> None:
        datos = self._srv_reportes.reporte_atenciones_y_derivaciones(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            clinica_id=clinica_id,
        )
        resumen = datos["resumen_por_clinica"]
        detalle = datos["detalle_atenciones"]

        filas_res = [
            (
                r["clinica_id"],
                (
                    r["clinica_nombre"],
                    r["total_consultas"],
                    r["total_derivaciones"],
                    r["derivaciones_urgentes"],
                    r["total_muestras_extraidas"],
                    f"${r['monto_consultas']:.2f}",
                ),
            )
            for r in resumen
        ]
        self._tabla_r1_resumen.cargar_filas(filas_res)

        filas_det = [
            (
                d["consulta_id"],
                (
                    f"#{d['consulta_id']}",
                    d["fecha_hora_inicio"],
                    d["clinica_nombre"],
                    d["veterinario_nombre"],
                    f"{d['mascota_nombre']} ({d['especie_nombre']})",
                    d["cliente_nombre"],
                    f"{d['motivo']} — {d['diagnostico']}",
                    d["cantidad_ordenes"],
                    d["estudios_solicitados"],
                    d["cantidad_muestras"],
                    f"${d['costo_consulta']:.2f}",
                ),
            )
            for d in detalle
        ]
        self._tabla_r1_detalle.cargar_filas(filas_det)

        total_cons = sum(r["total_consultas"] for r in resumen)
        total_deriv = sum(r["total_derivaciones"] for r in resumen)
        monto_total = sum(r["monto_consultas"] for r in resumen)

        self._datos_exportables_por_tab[TAB_ATENCIONES] = detalle
        self._tablas_exportables_por_tab[TAB_ATENCIONES] = [
            ("Detalle de Atenciones y Órdenes", detalle, "detalle_consultas"),
            ("Resumen por Clínica", resumen, "resumen_clinica"),
        ]
        self._kpis_por_tab[TAB_ATENCIONES] = (
            ("Consultas Médicas en Período", f"{total_cons} atenciones"),
            ("Órdenes de Derivación Emitidas", f"{total_deriv} órdenes"),
            ("Monto Acumulado en Consultas", f"${monto_total:,.2f}"),
        )

    def _cargar_reporte_2_rechazos(self, clinica_id: int | None = None) -> None:
        datos = self._srv_reportes.reporte_muestras_rechazadas_transporte(clinica_id=clinica_id)
        por_precinto = datos.get("rechazos_por_estado_precinto", {})
        por_clinica = datos.get("rechazos_por_clinica", {})
        detalle = datos.get("detalle_muestras", [])

        filas_res: list[tuple[int, tuple[Any, ...]]] = []
        idx = 1
        for estado_prec, cant in por_precinto.items():
            filas_res.append((idx, ("Por Estado de Precinto", f"Precinto '{estado_prec}'", cant)))
            idx += 1
        for clinica, cant in por_clinica.items():
            filas_res.append((idx, ("Por Clínica de Origen", clinica, cant)))
            idx += 1
        self._tabla_r2_resumen.cargar_filas(filas_res)

        filas_det = [
            (
                d.get("muestra_id"),
                (
                    d.get("muestra_id"),
                    d.get("codigo_muestra") or "—",
                    d.get("tipo_muestra") or "—",
                    d.get("numero_remito") or "—",
                    d.get("clinica_origen") or "—",
                    d.get("conservadora_codigo") or "—",
                    d.get("precinto_serie") or "—",
                    d.get("precinto_estado") or "—",
                    d.get("transportista_nombre") or d.get("transportista") or "—",
                    d.get("fecha_hora_recepcion") or "—",
                    d.get("motivo_rechazo") or "Rechazo sanitario",
                ),
            )
            for d in detalle
        ]
        self._tabla_r2_detalle.cargar_filas(filas_det)

        roto_cnt = por_precinto.get("Roto", 0)
        violado_cnt = por_precinto.get("Violado", 0)
        self._datos_exportables_por_tab[TAB_RECHAZOS] = detalle
        self._tablas_exportables_por_tab[TAB_RECHAZOS] = [
            ("Trazabilidad Muestras Rechazadas", detalle, "muestras_rechazadas"),
        ]
        self._kpis_por_tab[TAB_RECHAZOS] = (
            ("Total Muestras Rechazadas", f"{datos.get('total_rechazadas', len(detalle))} muestras"),
            ("Rechazos por Precinto Roto / Violado", f"Roto: {roto_cnt}  |  Violado: {violado_cnt}"),
            ("Clínicas con Incidencias", f"{len(por_clinica)} sede/s afectada/s"),
        )

    def _cargar_reporte_3_vacunas_y_tratamientos(
        self, fecha_ref: str | None, clinica_id: int | None = None
    ) -> None:
        datos = self._srv_reportes.reporte_tratamientos_y_vacunas_pendientes(
            fecha_referencia=fecha_ref,
            clinica_id=clinica_id,
        )
        vacunas_pend = datos.get("vacunas_pendientes", [])
        tratamientos = datos.get("tratamientos_aplicados", [])

        filas_vac = [
            (
                idx,
                (
                    f"#{v.get('mascota_id')}",
                    v.get("mascota_nombre") or "—",
                    v.get("especie_nombre") or "—",
                    v.get("cliente_nombre") or "—",
                    v.get("cliente_telefono") or "—",
                    v.get("nombre_vacuna") or "—",
                    v.get("ultima_fecha_aplicacion") or "Sin registro",
                    v.get("motivo_pendiente") or "—",
                ),
            )
            for idx, v in enumerate(vacunas_pend, start=1)
        ]
        self._tabla_r3_vacunas.cargar_filas(filas_vac)

        filas_trat = [
            (
                t.get("tratamiento_id"),
                (
                    t.get("tratamiento_id"),
                    t.get("fecha_consulta") or "—",
                    t.get("clinica_nombre") or "—",
                    t.get("veterinario_nombre") or "—",
                    f"{t.get('mascota_nombre', '')} ({t.get('especie_nombre', '')})",
                    t.get("medicamento") or "—",
                    t.get("dosis") or "—",
                    f"{t.get('duracion_dias')} días" if t.get("duracion_dias") else "—",
                    t.get("descripcion") or "—",
                ),
            )
            for t in tratamientos
        ]
        self._tabla_r3_tratamientos.cargar_filas(filas_trat)

        self._datos_exportables_por_tab[TAB_VACUNAS_TRAT] = vacunas_pend or tratamientos
        self._tablas_exportables_por_tab[TAB_VACUNAS_TRAT] = [
            ("Vacunas Obligatorias Pendientes", vacunas_pend, "vacunas_pendientes"),
            ("Tratamientos Farmacológicos Prescriptos", tratamientos, "tratamientos_prescriptos"),
        ]
        self._kpis_por_tab[TAB_VACUNAS_TRAT] = (
            ("Dosis Obligatorias Pendientes/Vencidas", f"{datos.get('total_vacunas_pendientes', len(vacunas_pend))} dosis"),
            (
                "Pacientes con Esquema Incompleto",
                f"{datos.get('total_mascotas_con_vacunas_pendientes', 0)} mascotas",
            ),
            ("Tratamientos Farmacológicos Prescriptos", f"{datos.get('total_tratamientos', len(tratamientos))} tratamientos"),
        )

    def _cargar_reporte_4_facturacion(
        self,
        fecha_desde: str | None,
        fecha_hasta: str | None,
        clinica_id: int | None = None,
    ) -> None:
        datos = self._srv_reportes.reporte_facturacion_desglosada(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            clinica_id=clinica_id,
        )
        por_clinica = datos.get("desglose_por_clinica", [])
        por_estrategia = datos.get("desglose_por_estrategia", [])

        filas_cli = [
            (
                c.get("clinica_id"),
                (
                    c.get("clinica_nombre") or "—",
                    c.get("cantidad_comprobantes", 0),
                    f"${float(c.get('subtotal_consultas', 0.0)):.2f}",
                    f"${float(c.get('subtotal_laboratorio', 0.0)):.2f}",
                    f"${float(c.get('total_recargos', 0.0)):.2f}",
                    f"${float(c.get('total_bonificaciones', 0.0)):.2f}",
                    f"${float(c.get('total_facturado', 0.0)):.2f}",
                ),
            )
            for c in por_clinica
        ]
        self._tabla_r4_clinica.cargar_filas(filas_cli)

        filas_est = [
            (
                idx,
                (
                    e.get("estrategia_tarifa") or "—",
                    e.get("cantidad_comprobantes", 0),
                    f"${float(e.get('total_facturado', 0.0)):.2f}",
                ),
            )
            for idx, e in enumerate(por_estrategia, start=1)
        ]
        self._tabla_r4_estrategia.cargar_filas(filas_est)

        self._datos_exportables_por_tab[TAB_FACTURACION] = por_clinica or por_estrategia
        self._tablas_exportables_por_tab[TAB_FACTURACION] = [
            ("Facturación por Clínica", por_clinica, "facturacion_por_clinica"),
            ("Facturación por Estrategia (Strategy)", por_estrategia, "facturacion_por_estrategia"),
        ]
        self._kpis_por_tab[TAB_FACTURACION] = (
            ("Facturación Total General", f"${float(datos.get('total_general_facturado', 0.0)):,.2f}"),
            ("Ingresos por Estudios Laboratorio", f"${float(datos.get('total_servicios_laboratorio', 0.0)):,.2f}"),
            ("Ingresos por Atención Clínica", f"${float(datos.get('total_servicios_clinica', 0.0)):,.2f}"),
        )

    def _cargar_reporte_5_tiempos_sla(self, clinica_id: int | None = None) -> None:
        datos = self._srv_reportes.reporte_tiempos_transito_y_procesamiento(clinica_id=clinica_id)
        promedios = datos.get("promedios_por_clinica", [])
        detalle = datos.get("detalle_tiempos_muestras", [])

        filas_prom = [
            (
                idx,
                (
                    p.get("clinica_nombre") or "—",
                    p.get("muestras_evaluadas", 0),
                    f"{float(p.get('promedio_horas_transito', 0.0)):.2f} hs",
                    f"{float(p.get('promedio_horas_procesamiento_lab', 0.0)):.2f} hs",
                    f"{float(p.get('promedio_horas_ciclo_total', 0.0)):.2f} hs",
                ),
            )
            for idx, p in enumerate(promedios, start=1)
        ]
        self._tabla_r5_promedios.cargar_filas(filas_prom)

        def _fmt_hs(valor: float | None) -> str:
            return f"{float(valor):.2f} hs" if valor is not None else "En curso"

        filas_det = [
            (
                d.get("muestra_id"),
                (
                    d.get("muestra_id"),
                    d.get("codigo_muestra") or "—",
                    d.get("tipo_estudio") or "—",
                    d.get("prioridad") or "—",
                    d.get("clinica_nombre") or "—",
                    d.get("estado_actual") or "—",
                    _fmt_hs(d.get("horas_espera_clinica")),
                    _fmt_hs(d.get("horas_transito")),
                    _fmt_hs(d.get("horas_procesamiento_lab")),
                    _fmt_hs(d.get("horas_ciclo_total")),
                ),
            )
            for d in detalle
        ]
        self._tabla_r5_detalle.cargar_filas(filas_det)

        self._datos_exportables_por_tab[TAB_TIEMPOS_SLA] = detalle
        self._tablas_exportables_por_tab[TAB_TIEMPOS_SLA] = [
            ("Trazabilidad Horaria por Muestra", detalle, "sla_detalle_muestras"),
            ("Promedios SLA por Clínica", promedios, "sla_promedios"),
        ]
        self._kpis_por_tab[TAB_TIEMPOS_SLA] = (
            (
                "Promedio Global Tránsito en Ruta",
                f"{float(datos.get('promedio_global_horas_transito', 0.0)):.2f} horas",
            ),
            (
                "Promedio Procesamiento Laboratorio",
                f"{float(datos.get('promedio_global_horas_procesamiento_lab', 0.0)):.2f} horas",
            ),
            (
                "Ciclo Diagnóstico Total Promedio",
                f"{float(datos.get('promedio_global_horas_ciclo_total', 0.0)):.2f} horas",
            ),
        )
