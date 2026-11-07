"""
Vista Gráfica: Proceso 3 — Consultas Médicas, Agenda, Órdenes y Extracción de Muestras
======================================================================================

Permite:
    1. Registrar consultas médicas verificando disponibilidad horaria del veterinario
       para impedir superposición de turnos (`ErrorSuperposicionTurno`).
    2. Controlar el esquema de vacunación obligatoria de la mascota al momento de la
       atención (`ErrorVacunaObligatoriaFaltante` o aviso preventivo).
    3. Prescribir tratamientos terapéuticos asociados a la consulta.
    4. Emitir órdenes de derivación de laboratorio (prioridad 'Normal' o 'Urgente').
    5. Extraer muestras biológicas para cada orden, iniciando su ciclo de vida State
       en estado 'Extraida' y permitiendo auditar su historial inmutable.

Principios de Diseño POO aplicados:
    - Alta Cohesión / SRP: Divide el flujo clínico en dos áreas coordinadas:
      (A) Atención Médica y Agenda, y (B) Derivación de Laboratorio y Extracción.
    - Bajo Acoplamiento / DIP: Sólo interactúa con `ServicioClinica` y entidades de dominio.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import customtkinter as ctk

from src.dominio.consulta_medica import ConsultaMedica
from src.dominio.excepciones import ErrorDatosInvalidos
from src.dominio.historia_clinica import Tratamiento
from src.dominio.muestra_biologica import MuestraBiologica
from src.interfaz.componentes.alertas import (
    ejecutar_accion_segura,
    limpiar_resaltado_campos,
    mostrar_advertencia,
    mostrar_exito,
)
from src.interfaz.componentes.tabla import TablaDatos
from src.servicios.servicio_clinica import ServicioClinica


class VistaConsultas(ctk.CTkFrame):
    """Vista interactiva para el Proceso 3: Consultas, Derivaciones y Extracción de Muestras."""

    def __init__(self, master: Any, servicio_clinica: ServicioClinica, **kwargs: Any) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._servicio = servicio_clinica
        self._consulta_seleccionada_id: int | None = None
        self._orden_seleccionada_id: int | None = None

        self._mapa_campos_consulta: dict[str, ctk.CTkBaseClass] = {}
        self._mapa_campos_muestra: dict[str, ctk.CTkBaseClass] = {}

        self._mascotas_por_etiqueta: dict[str, int] = {}
        self._etiqueta_por_mascota_id: dict[int, str] = {}
        self._clinicas_por_nombre: dict[str, int] = {}
        self._nombre_por_clinica_id: dict[int, str] = {}
        self._veterinarios_por_etiqueta: dict[str, int] = {}
        self._etiqueta_por_veterinario_id: dict[int, str] = {}
        self._estudios_por_etiqueta: dict[str, int] = {}
        self._tipos_muestra_por_nombre: dict[str, int] = {}

        self._construir_ui()
        self.refrescar_datos()

    # ==================================================================================
    # Construcción de la Interfaz (UI)
    # ==================================================================================

    def _construir_ui(self) -> None:
        """Organiza la vista en formulario de consulta (izquierda) y derivaciones/muestras (derecha)."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_columnconfigure(1, weight=1)

        # Cabecera
        marco_titulo = ctk.CTkFrame(self, fg_color="transparent")
        marco_titulo.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 6))

        ctk.CTkLabel(
            marco_titulo,
            text="Proceso 3: Consultas Médicas, Agenda, Órdenes de Derivación y Muestras",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")

        self._etiqueta_contador = ctk.CTkLabel(
            marco_titulo,
            text="0 consultas registradas",
            font=ctk.CTkFont(size=13),
            text_color=("gray35", "gray70"),
        )
        self._etiqueta_contador.pack(side="right", padx=8)

        self._construir_panel_formulario_consulta()
        self._construir_panel_derecho()

    def _construir_panel_formulario_consulta(self) -> None:
        """Crea el formulario izquierdo para agendar y registrar consultas médicas y tratamientos."""
        panel = ctk.CTkScrollableFrame(self, corner_radius=10)
        panel.grid(row=1, column=0, sticky="nsew", padx=(10, 6), pady=4)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel,
            text="Registrar Nueva Consulta Médica",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(8, 4))

        # 1. Mascota Paciente
        ctk.CTkLabel(
            panel, text="Mascota / Paciente *", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(2, 1))

        self._combo_mascota = ctk.CTkComboBox(
            panel, values=["Sin mascotas registradas"], height=29, state="readonly"
        )
        self._combo_mascota.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 2))
        self._mapa_campos_consulta["mascota_id"] = self._combo_mascota

        # 2. Clínica y Veterinario
        ctk.CTkLabel(
            panel, text="Clínica de la Red *", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=3, column=0, sticky="w", padx=14, pady=(2, 1))

        self._combo_clinica = ctk.CTkComboBox(
            panel, values=["Clínica Veterinaria Centro"], height=29, state="readonly"
        )
        self._combo_clinica.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 2))

        ctk.CTkLabel(
            panel, text="Veterinario Actuante (Control de Agenda) *", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=5, column=0, sticky="w", padx=14, pady=(2, 1))

        self._combo_veterinario = ctk.CTkComboBox(
            panel, values=["Seleccione veterinario"], height=29, state="readonly"
        )
        self._combo_veterinario.grid(row=6, column=0, sticky="ew", padx=14, pady=(0, 2))

        # 3. Fecha/Hora Inicio, Duración y Costo en una fila
        marco_horario = ctk.CTkFrame(panel, fg_color="transparent")
        marco_horario.grid(row=7, column=0, sticky="ew", padx=14, pady=(2, 2))
        marco_horario.grid_columnconfigure(0, weight=2)
        marco_horario.grid_columnconfigure((1, 2), weight=1)

        ctk.CTkLabel(
            marco_horario, text="Inicio (AAAA-MM-DD HH:MM:SS) *", font=ctk.CTkFont(size=11, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=(0, 4))
        ctk.CTkLabel(
            marco_horario, text="Duración (min) *", font=ctk.CTkFont(size=11, weight="bold")
        ).grid(row=0, column=1, sticky="w", padx=4)
        ctk.CTkLabel(
            marco_horario, text="Arancel ($) *", font=ctk.CTkFont(size=11, weight="bold")
        ).grid(row=0, column=2, sticky="w", padx=(4, 0))

        self._entrada_fecha_inicio = ctk.CTkEntry(marco_horario, height=29)
        self._entrada_fecha_inicio.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:00"))
        self._entrada_fecha_inicio.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        self._mapa_campos_consulta["fecha_hora_inicio"] = self._entrada_fecha_inicio

        self._entrada_duracion = ctk.CTkEntry(marco_horario, width=65, height=29)
        self._entrada_duracion.insert(0, "30")
        self._entrada_duracion.grid(row=1, column=1, sticky="ew", padx=4)
        self._mapa_campos_consulta["duracion_minutos"] = self._entrada_duracion

        self._entrada_costo = ctk.CTkEntry(marco_horario, width=85, height=29)
        self._entrada_costo.insert(0, "20000")
        self._entrada_costo.grid(row=1, column=2, sticky="ew", padx=(4, 0))
        self._mapa_campos_consulta["costo_consulta"] = self._entrada_costo

        # 4. Motivo y Diagnóstico
        ctk.CTkLabel(
            panel, text="Motivo de la Consulta *", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=8, column=0, sticky="w", padx=14, pady=(2, 1))

        self._entrada_motivo = ctk.CTkEntry(
            panel, placeholder_text="Ej: Control prequirúrgico / Decaimiento", height=29
        )
        self._entrada_motivo.grid(row=9, column=0, sticky="ew", padx=14, pady=(0, 2))
        self._mapa_campos_consulta["motivo"] = self._entrada_motivo

        ctk.CTkLabel(
            panel, text="Diagnóstico Clínico (opcional)", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=10, column=0, sticky="w", padx=14, pady=(2, 1))

        self._entrada_diagnostico = ctk.CTkEntry(
            panel, placeholder_text="Ej: Sospecha de infección urinaria", height=29
        )
        self._entrada_diagnostico.grid(row=11, column=0, sticky="ew", padx=14, pady=(0, 2))

        # 5. Tratamiento opcional en la consulta
        ctk.CTkLabel(
            panel,
            text="Prescripción de Tratamiento (opcional):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1E3A8A",
        ).grid(row=12, column=0, sticky="w", padx=14, pady=(4, 1))

        self._entrada_trat_desc = ctk.CTkEntry(
            panel, placeholder_text="Descripción terapéutica (ej: Antibioterapia oral)", height=28
        )
        self._entrada_trat_desc.grid(row=13, column=0, sticky="ew", padx=14, pady=(0, 2))
        self._mapa_campos_consulta["descripcion"] = self._entrada_trat_desc

        marco_trat_det = ctk.CTkFrame(panel, fg_color="transparent")
        marco_trat_det.grid(row=14, column=0, sticky="ew", padx=14, pady=(1, 2))
        marco_trat_det.grid_columnconfigure((0, 1), weight=2)
        marco_trat_det.grid_columnconfigure(2, weight=1)

        self._entrada_trat_med = ctk.CTkEntry(
            marco_trat_det, placeholder_text="Medicamento", height=28
        )
        self._entrada_trat_med.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        self._entrada_trat_dosis = ctk.CTkEntry(
            marco_trat_det, placeholder_text="Dosis (ej: 1 c/12h)", height=28
        )
        self._entrada_trat_dosis.grid(row=0, column=1, sticky="ew", padx=3)

        self._entrada_trat_dias = ctk.CTkEntry(
            marco_trat_det, placeholder_text="Días", width=55, height=28
        )
        self._entrada_trat_dias.grid(row=0, column=2, sticky="ew", padx=(3, 0))
        self._mapa_campos_consulta["duracion_dias"] = self._entrada_trat_dias

        # 6. Casilla de bloqueo por vacunas obligatorias faltantes
        self._var_exigir_vacunas = ctk.BooleanVar(value=False)
        self._check_vacunas = ctk.CTkCheckBox(
            panel,
            text="Bloquear atención si faltan vacunas obligatorias",
            variable=self._var_exigir_vacunas,
            font=ctk.CTkFont(size=12),
            checkbox_width=18,
            checkbox_height=18,
        )
        self._check_vacunas.grid(row=15, column=0, sticky="w", padx=14, pady=(4, 4))

        # Botonera de Consulta Médica
        marco_botones_cons = ctk.CTkFrame(panel, fg_color="transparent")
        marco_botones_cons.grid(row=16, column=0, sticky="ew", padx=14, pady=(4, 10))
        marco_botones_cons.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            marco_botones_cons,
            text="Registrar Consulta Médica",
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._al_registrar_consulta,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        ctk.CTkButton(
            marco_botones_cons,
            text="Nueva Consulta",
            fg_color="#475569",
            hover_color="#334155",
            height=31,
            command=self._limpiar_formulario_consulta,
        ).grid(row=1, column=0, columnspan=2, sticky="ew")

    def _construir_panel_derecho(self) -> None:
        """Crea el panel derecho con la tabla de consultas (arriba) y Órdenes/Muestras (abajo)."""
        panel = ctk.CTkFrame(self, fg_color="transparent")
        panel.grid(row=1, column=1, sticky="nsew", padx=(6, 10), pady=4)
        panel.grid_rowconfigure(0, weight=5)
        panel.grid_rowconfigure(1, weight=6)
        panel.grid_columnconfigure(0, weight=1)

        # --- Mitad Superior: Tabla de Consultas Médicas ---
        marco_consultas = ctk.CTkFrame(panel, corner_radius=10)
        marco_consultas.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        marco_consultas.grid_rowconfigure(1, weight=1)
        marco_consultas.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            marco_consultas,
            text="Agenda de Consultas Registradas (seleccione una consulta para emitir Órdenes y extraer Muestras)",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        columnas_cons = [
            ("id", "ID", 45),
            ("inicio", "Inicio", 135),
            ("fin", "Fin", 80),
            ("mascota", "Mascota", 115),
            ("clinica", "Clínica", 165),
            ("veterinario", "Veterinario", 150),
            ("motivo", "Motivo", 170),
            ("costo", "Arancel", 85),
        ]
        self._tabla_consultas = TablaDatos(
            marco_consultas,
            columnas=columnas_cons,
            al_seleccionar=self._al_seleccionar_consulta,
            altura_filas=6,
        )
        self._tabla_consultas.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        # --- Mitad Inferior: Órdenes de Derivación y Extracción de Muestras Biológicas ---
        self._construir_panel_ordenes_y_muestras(panel)

    def _construir_panel_ordenes_y_muestras(self, contenedor: ctk.CTkFrame) -> None:
        """Crea el panel inferior para emitir órdenes de derivación y extraer muestras biológicas."""
        marco_inf = ctk.CTkFrame(contenedor, corner_radius=10)
        marco_inf.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        marco_inf.grid_rowconfigure(1, weight=1)
        marco_inf.grid_columnconfigure(0, weight=1)

        self._etiqueta_consulta_activa = ctk.CTkLabel(
            marco_inf,
            text="Derivación de Laboratorio: Ninguna consulta seleccionada",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._etiqueta_consulta_activa.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

        self._tabs_derivacion = ctk.CTkTabview(marco_inf, height=230)
        self._tabs_derivacion.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))

        tab_ordenes = self._tabs_derivacion.add("1. Órdenes de Derivación")
        tab_muestras = self._tabs_derivacion.add("2. Extracción de Muestras y Trazabilidad (State)")

        # --- Pestaña 1: Órdenes de Derivación ---
        tab_ordenes.grid_rowconfigure(1, weight=1)
        tab_ordenes.grid_columnconfigure(0, weight=1)

        barra_orden = ctk.CTkFrame(tab_ordenes, fg_color="transparent")
        barra_orden.grid(row=0, column=0, sticky="ew", pady=(2, 6))
        barra_orden.grid_columnconfigure(1, weight=2)
        barra_orden.grid_columnconfigure(3, weight=2)

        ctk.CTkLabel(barra_orden, text="Estudio:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, padx=(0, 4)
        )
        self._combo_estudio = ctk.CTkComboBox(
            barra_orden, values=["Hemograma completo"], height=30, state="readonly"
        )
        self._combo_estudio.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkLabel(barra_orden, text="Prioridad:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=2, padx=(0, 4)
        )
        self._combo_prioridad = ctk.CTkComboBox(
            barra_orden, values=["Normal", "Urgente"], width=105, height=30, state="readonly"
        )
        self._combo_prioridad.set("Normal")
        self._combo_prioridad.grid(row=0, column=3, sticky="w", padx=(0, 8))

        self._entrada_indicaciones = ctk.CTkEntry(
            barra_orden, placeholder_text="Indicaciones / Sospecha diagnóstica...", height=30
        )
        self._entrada_indicaciones.grid(row=0, column=4, sticky="ew", padx=(0, 8))
        barra_orden.grid_columnconfigure(4, weight=3)

        ctk.CTkButton(
            barra_orden,
            text="Emitir Orden de Derivación",
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            height=30,
            command=self._al_emitir_orden,
        ).grid(row=0, column=5)

        columnas_ord = [
            ("id", "Orden #", 65),
            ("estudio", "Estudio Solicitado", 200),
            ("prioridad", "Prioridad", 95),
            ("costo_base", "Costo Base", 105),
            ("emision", "Fecha/Hora Emisión", 150),
            ("indicaciones", "Indicaciones Médicas", 230),
        ]
        self._tabla_ordenes = TablaDatos(
            tab_ordenes,
            columnas=columnas_ord,
            al_seleccionar=self._al_seleccionar_orden,
            altura_filas=4,
        )
        self._tabla_ordenes.grid(row=1, column=0, sticky="nsew")

        # --- Pestaña 2: Extracción de Muestras Biológicas ---
        tab_muestras.grid_rowconfigure(1, weight=1)
        tab_muestras.grid_columnconfigure(0, weight=1)

        barra_muestra = ctk.CTkFrame(tab_muestras, fg_color="transparent")
        barra_muestra.grid(row=0, column=0, sticky="ew", pady=(2, 6))
        barra_muestra.grid_columnconfigure(3, weight=1)

        self._etiqueta_orden_activa = ctk.CTkLabel(
            barra_muestra,
            text="Orden: Ninguna",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1E3A8A",
        )
        self._etiqueta_orden_activa.grid(row=0, column=0, padx=(0, 8))

        ctk.CTkLabel(barra_muestra, text="Código Muestra *:", font=ctk.CTkFont(size=12)).grid(
            row=0, column=1, padx=(0, 4)
        )
        self._entrada_codigo_muestra = ctk.CTkEntry(
            barra_muestra, placeholder_text="Ej: MUE-2026-001", width=135, height=30
        )
        self._entrada_codigo_muestra.grid(row=0, column=2, padx=(0, 8))
        self._mapa_campos_muestra["codigo_muestra"] = self._entrada_codigo_muestra

        self._combo_tipo_muestra = ctk.CTkComboBox(
            barra_muestra, values=["Sangre entera"], height=30, state="readonly"
        )
        self._combo_tipo_muestra.grid(row=0, column=3, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            barra_muestra,
            text="Extraer Muestra Biológica",
            fg_color="#15803D",
            hover_color="#166534",
            height=30,
            command=self._al_extraer_muestra,
        ).grid(row=0, column=4)

        columnas_mue = [
            ("id", "ID", 45),
            ("codigo", "Código Muestra", 140),
            ("tipo", "Tipo de Muestra", 150),
            ("extraccion", "Fecha/Hora Extracción", 155),
            ("estado", "Estado Actual (State)", 135),
            ("trazabilidad", "Último Evento de Trazabilidad Inmutable", 240),
        ]
        self._tabla_muestras = TablaDatos(
            tab_muestras,
            columnas=columnas_mue,
            altura_filas=4,
        )
        self._tabla_muestras.grid(row=1, column=0, sticky="nsew")

    # ==================================================================================
    # Manejadores de Eventos
    # ==================================================================================

    def _al_registrar_consulta(self) -> None:
        """Valida los datos del formulario y registra la consulta médica y su tratamiento."""
        etiqueta_mascota = self._combo_mascota.get()
        mascota_id = self._mascotas_por_etiqueta.get(etiqueta_mascota)
        if mascota_id is None:
            mostrar_advertencia(
                "Mascota requerida",
                "Debe registrar y seleccionar una mascota antes de agendar una consulta médica.",
            )
            return

        clinica_id = self._clinicas_por_nombre.get(self._combo_clinica.get(), 1)
        veterinario_id = self._veterinarios_por_etiqueta.get(self._combo_veterinario.get(), 1)
        fecha_inicio = self._entrada_fecha_inicio.get().strip()
        motivo = self._entrada_motivo.get().strip()
        diagnostico = self._entrada_diagnostico.get().strip() or None
        exigir_vacunas = bool(self._var_exigir_vacunas.get())

        def _ejecutar_alta() -> tuple[ConsultaMedica, list[dict]]:
            try:
                duracion = int(self._entrada_duracion.get().strip())
            except ValueError as err:
                raise ErrorDatosInvalidos(
                    "duracion_minutos", "La duración debe ser un número entero de minutos."
                ) from err

            try:
                costo = float(self._entrada_costo.get().strip())
            except ValueError as err:
                raise ErrorDatosInvalidos(
                    "costo_consulta", "El arancel de la consulta debe ser un importe numérico."
                ) from err

            tratamientos: list[Tratamiento] = []
            desc_trat = self._entrada_trat_desc.get().strip()
            if desc_trat:
                dias_txt = self._entrada_trat_dias.get().strip()
                dias_val: int | None = None
                if dias_txt:
                    try:
                        dias_val = int(dias_txt)
                    except ValueError as err:
                        raise ErrorDatosInvalidos(
                            "duracion_dias", "Los días de tratamiento deben ser un número entero."
                        ) from err

                tratamientos.append(
                    Tratamiento(
                        id=None,
                        consulta_id=0,
                        descripcion=desc_trat,
                        medicamento=self._entrada_trat_med.get().strip() or None,
                        dosis=self._entrada_trat_dosis.get().strip() or None,
                        duracion_dias=dias_val,
                    )
                )

            return self._servicio.registrar_consulta_medica(
                mascota_id=mascota_id,
                clinica_id=clinica_id,
                veterinario_id=veterinario_id,
                fecha_hora_inicio=fecha_inicio,
                motivo=motivo,
                duracion_minutos=duracion,
                diagnostico=diagnostico,
                costo_consulta=costo,
                tratamientos=tratamientos,
                exigir_vacunas_al_dia=exigir_vacunas,
            )

        resultado = ejecutar_accion_segura(
            _ejecutar_alta,
            mapa_campos=self._mapa_campos_consulta,
            titulo_error="No se pudo registrar la consulta médica",
        )
        if resultado is None:
            return

        consulta_creada, vacunas_pendientes = resultado
        mensaje = (
            f"Consulta #{consulta_creada.id} registrada exitosamente "
            f"({consulta_creada.fecha_hora_inicio} a {consulta_creada.fecha_hora_fin})."
        )
        if vacunas_pendientes:
            nombres_falt = ", ".join(v["nombre_vacuna"] for v in vacunas_pendientes)
            mensaje += (
                f"\n\nADVERTENCIA SANITARIA: El paciente posee vacunas obligatorias "
                f"pendientes o vencidas: {nombres_falt}."
            )

        mostrar_exito("Consulta Médica Registrada", mensaje)
        self._limpiar_formulario_consulta()
        self.refrescar_datos()
        if consulta_creada.id is not None:
            self._al_seleccionar_consulta(str(consulta_creada.id))

    def _al_seleccionar_consulta(self, id_fila: str) -> None:
        """Selecciona una consulta de la agenda y carga sus órdenes de derivación."""
        self._consulta_seleccionada_id = int(id_fila)
        self._orden_seleccionada_id = None

        consulta = ejecutar_accion_segura(
            lambda: self._servicio.obtener_consulta(self._consulta_seleccionada_id),
            titulo_error="Error al cargar consulta",
        )
        if consulta is None:
            return

        mascota_txt = self._etiqueta_por_mascota_id.get(
            consulta.mascota_id, f"Mascota #{consulta.mascota_id}"
        )
        clinica_txt = self._nombre_por_clinica_id.get(
            consulta.clinica_id, f"Clínica #{consulta.clinica_id}"
        )
        self._etiqueta_consulta_activa.configure(
            text=f"Consulta Activa #{consulta.id} — Paciente: {mascota_txt} — Sede: {clinica_txt}"
        )
        self._cargar_ordenes_de_consulta(consulta)

    def _cargar_ordenes_de_consulta(self, consulta: ConsultaMedica) -> None:
        """Puebla la tabla de órdenes de derivación de la consulta activa."""
        filas_ord = [
            (
                o.id,
                (
                    f"#{o.id}",
                    o.nombre_estudio,
                    o.prioridad,
                    f"$ {o.costo_base:,.2f}",
                    o.fecha_hora_emision,
                    o.indicaciones or "—",
                ),
            )
            for o in consulta.ordenes
            if o.id is not None
        ]
        self._tabla_ordenes.cargar_filas(filas_ord)

        if consulta.ordenes and consulta.ordenes[-1].id is not None:
            ultimo_id = consulta.ordenes[-1].id
            self._al_seleccionar_orden(str(ultimo_id))
        else:
            self._etiqueta_orden_activa.configure(text="Orden: Ninguna")
            self._tabla_muestras.cargar_filas([])

    def _al_emitir_orden(self) -> None:
        """Emite una orden de derivación de laboratorio para la consulta seleccionada."""
        if self._consulta_seleccionada_id is None:
            mostrar_advertencia(
                "Seleccione una consulta",
                "Primero haga clic sobre una consulta médica en la tabla superior.",
            )
            return

        estudio_id = self._estudios_por_etiqueta.get(self._combo_estudio.get())
        if estudio_id is None:
            mostrar_advertencia("Estudio requerido", "Seleccione un estudio del catálogo.")
            return

        prioridad = self._combo_prioridad.get()
        indicaciones = self._entrada_indicaciones.get().strip() or None
        consulta_id = self._consulta_seleccionada_id

        orden = ejecutar_accion_segura(
            lambda: self._servicio.emitir_orden_derivacion(
                consulta_id=consulta_id,
                tipo_estudio_id=estudio_id,
                indicaciones=indicaciones,
                prioridad=prioridad,
            ),
            titulo_error="No se pudo emitir la orden de derivación",
        )
        if orden is not None and orden.id is not None:
            mostrar_exito(
                "Orden de Derivación Emitida",
                f"Se emitió la Orden #{orden.id} ({orden.nombre_estudio} — Prioridad: {orden.prioridad}).\n"
                "Ahora puede extraer la muestra biológica en la pestaña '2. Extracción de Muestras'.",
            )
            self._entrada_indicaciones.delete(0, "end")
            consulta_actualizada = self._servicio.obtener_consulta(consulta_id)
            self._cargar_ordenes_de_consulta(consulta_actualizada)
            self._al_seleccionar_orden(str(orden.id))
            self._tabs_derivacion.set("2. Extracción de Muestras y Trazabilidad (State)")

    def _al_seleccionar_orden(self, id_fila: str) -> None:
        """Selecciona una orden de derivación y muestra las muestras biológicas extraídas."""
        orden_id = int(str(id_fila).lstrip("#"))
        self._orden_seleccionada_id = orden_id
        self._etiqueta_orden_activa.configure(text=f"Orden Activa: #{orden_id}")

        # Sugerir un código de muestra automático si el campo está vacío
        if not self._entrada_codigo_muestra.get().strip():
            marca = datetime.now().strftime("%H%M%S")
            self._entrada_codigo_muestra.insert(0, f"MUE-{orden_id:02d}-{marca}")

        self._cargar_muestras_de_orden(orden_id)

    def _cargar_muestras_de_orden(self, orden_id: int) -> None:
        """Carga las muestras biológicas extraídas para la orden dada."""
        muestras: list[MuestraBiologica] = self._servicio.listar_muestras_por_orden(orden_id)
        filas_mue = []
        for m in muestras:
            if m.id is None:
                continue
            ultimo_evento = (
                f"{m.historial[-1].estado_nuevo} ({m.historial[-1].fecha_hora})"
                if m.historial
                else m.estado_actual
            )
            filas_mue.append(
                (
                    m.id,
                    (
                        m.id,
                        m.codigo_muestra,
                        m.nombre_tipo_muestra,
                        m.fecha_hora_extraccion,
                        m.estado_actual,
                        ultimo_evento,
                    ),
                )
            )
        self._tabla_muestras.cargar_filas(filas_mue)

    def _al_extraer_muestra(self) -> None:
        """Registra la extracción física de una muestra biológica para la orden activa."""
        if self._orden_seleccionada_id is None:
            mostrar_advertencia(
                "Seleccione una orden de derivación",
                "Primero emita o seleccione una Orden de Derivación en la pestaña '1. Órdenes de Derivación'.",
            )
            return

        codigo = self._entrada_codigo_muestra.get().strip()
        tipo_id = self._tipos_muestra_por_nombre.get(self._combo_tipo_muestra.get(), 1)
        orden_id = self._orden_seleccionada_id

        muestra = ejecutar_accion_segura(
            lambda: self._servicio.extraer_muestra_biologica(
                orden_id=orden_id,
                codigo_muestra=codigo,
                tipo_muestra_id=tipo_id,
            ),
            mapa_campos=self._mapa_campos_muestra,
            titulo_error="No se pudo registrar la muestra biológica",
        )
        if muestra is not None:
            mostrar_exito(
                "Muestra Biológica Extraída",
                f"Muestra '{muestra.codigo_muestra}' ({muestra.nombre_tipo_muestra}) registrada en "
                f"estado '{muestra.estado_actual}' con su primer hito de trazabilidad inmutable.",
            )
            self._entrada_codigo_muestra.delete(0, "end")
            self._cargar_muestras_de_orden(orden_id)

    def _limpiar_formulario_consulta(self) -> None:
        """Limpia los campos de texto de la consulta recién creada."""
        limpiar_resaltado_campos(self._mapa_campos_consulta)
        self._entrada_motivo.delete(0, "end")
        self._entrada_diagnostico.delete(0, "end")
        self._entrada_trat_desc.delete(0, "end")
        self._entrada_trat_med.delete(0, "end")
        self._entrada_trat_dosis.delete(0, "end")
        self._entrada_trat_dias.delete(0, "end")

    # ==================================================================================
    # Sincronización y Refresco de Datos
    # ==================================================================================

    def refrescar_datos(self) -> None:
        """Recarga catálogos, mascotas y listado de consultas médicas."""
        # 1. Mascotas
        mascotas = self._servicio.listar_mascotas()
        self._mascotas_por_etiqueta.clear()
        self._etiqueta_por_mascota_id.clear()
        opciones_mascotas: list[str] = []
        for m in mascotas:
            if m.id is not None:
                etiqueta = f"{m.nombre} ({m.nombre_especie or 'Mascota'} — #{m.id})"
                self._mascotas_por_etiqueta[etiqueta] = m.id
                self._etiqueta_por_mascota_id[m.id] = etiqueta
                opciones_mascotas.append(etiqueta)

        if opciones_mascotas:
            prev_m = self._combo_mascota.get()
            self._combo_mascota.configure(values=opciones_mascotas)
            self._combo_mascota.set(prev_m if prev_m in opciones_mascotas else opciones_mascotas[0])
        else:
            self._combo_mascota.configure(values=["Sin mascotas registradas"])
            self._combo_mascota.set("Sin mascotas registradas")

        # 2. Clínicas
        clinicas = self._servicio.listar_clinicas()
        self._clinicas_por_nombre = {c["nombre"]: int(c["id"]) for c in clinicas}
        self._nombre_por_clinica_id = {int(c["id"]): c["nombre"] for c in clinicas}
        nombres_clinicas = list(self._clinicas_por_nombre.keys())
        if nombres_clinicas:
            self._combo_clinica.configure(values=nombres_clinicas)
            if self._combo_clinica.get() not in self._clinicas_por_nombre:
                self._combo_clinica.set(nombres_clinicas[0])

        # 3. Veterinarios
        veterinarios = self._servicio.listar_veterinarios()
        self._veterinarios_por_etiqueta.clear()
        self._etiqueta_por_veterinario_id.clear()
        opciones_vet: list[str] = []
        for v in veterinarios:
            vid = int(v["id"])
            etiqueta = f"{v['apellido']}, {v['nombre']} ({v['matricula']} - {v['especialidad']})"
            self._veterinarios_por_etiqueta[etiqueta] = vid
            self._etiqueta_por_veterinario_id[vid] = f"{v['apellido']}, {v['nombre']} ({v['matricula']})"
            opciones_vet.append(etiqueta)

        if opciones_vet:
            prev_v = self._combo_veterinario.get()
            self._combo_veterinario.configure(values=opciones_vet)
            self._combo_veterinario.set(prev_v if prev_v in opciones_vet else opciones_vet[0])

        # 4. Catálogo de Estudios de Laboratorio
        estudios = self._servicio.listar_tipos_estudio()
        self._estudios_por_etiqueta.clear()
        opciones_est: list[str] = []
        for e in estudios:
            etiqueta = f"{e['nombre']} ($ {float(e['costo_base']):,.0f})"
            self._estudios_por_etiqueta[etiqueta] = int(e["id"])
            opciones_est.append(etiqueta)
        if opciones_est:
            self._combo_estudio.configure(values=opciones_est)
            if self._combo_estudio.get() not in self._estudios_por_etiqueta:
                self._combo_estudio.set(opciones_est[0])

        # 5. Catálogo de Tipos de Muestra
        tipos_muestra = self._servicio.listar_tipos_muestra()
        self._tipos_muestra_por_nombre = {t["nombre"]: int(t["id"]) for t in tipos_muestra}
        nombres_tm = list(self._tipos_muestra_por_nombre.keys())
        if nombres_tm:
            self._combo_tipo_muestra.configure(values=nombres_tm)
            if self._combo_tipo_muestra.get() not in self._tipos_muestra_por_nombre:
                self._combo_tipo_muestra.set(nombres_tm[0])

        # 6. Tabla de Consultas Médicas
        consultas = self._servicio.listar_consultas()
        filas_cons = []
        for c in consultas:
            if c.id is None:
                continue
            filas_cons.append(
                (
                    c.id,
                    (
                        c.id,
                        c.fecha_hora_inicio,
                        c.fecha_hora_fin[11:16],
                        self._etiqueta_por_mascota_id.get(c.mascota_id, f"#{c.mascota_id}"),
                        self._nombre_por_clinica_id.get(c.clinica_id, f"#{c.clinica_id}"),
                        self._etiqueta_por_veterinario_id.get(c.veterinario_id, f"#{c.veterinario_id}"),
                        c.motivo,
                        f"$ {c.costo_consulta:,.2f}",
                    ),
                )
            )
        self._tabla_consultas.cargar_filas(filas_cons)
        total = len(filas_cons)
        sufijo = "consulta registrada" if total == 1 else "consultas registradas"
        self._etiqueta_contador.configure(text=f"{total} {sufijo}")
