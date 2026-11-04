"""
Vista Gráfica: Proceso 2 — Administración de Mascotas, Historia Clínica 1:1 y Vacunas
=====================================================================================

Permite:
    1. Registrar, modificar, listar y eliminar mascotas asociándolas a un cliente
       responsable obligatorio (`ErrorMascotaSinResponsable`).
    2. Consultar y actualizar la Historia Clínica 1 a 1 de cada paciente (fecha de
       apertura, antecedentes médicos, alergias y tratamientos históricos).
    3. Controlar el esquema de vacunación obligatoria según la especie y registrar
       nuevas dosis de vacunas aplicadas.

Principios de Diseño POO aplicados:
    - Alta Cohesión / SRP: Métodos separados para formulario de mascota, listado
      general y pestaña de Historia Clínica / Vacunación.
    - Bajo Acoplamiento / DIP: Se comunica únicamente con `ServicioClinica`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import customtkinter as ctk

from src.dominio.excepciones import ErrorDatosInvalidos
from src.dominio.mascota import Mascota
from src.interfaz.componentes.alertas import (
    confirmar_accion,
    ejecutar_accion_segura,
    limpiar_resaltado_campos,
    mostrar_advertencia,
    mostrar_exito,
)
from src.interfaz.componentes.tabla import TablaDatos
from src.servicios.servicio_clinica import ServicioClinica

OPCION_SIN_RESPONSABLE = "— Seleccione un cliente responsable —"


class VistaMascotas(ctk.CTkFrame):
    """Vista interactiva para el Proceso 2: Mascotas, Historia Clínica 1:1 y Vacunación."""

    def __init__(self, master: Any, servicio_clinica: ServicioClinica, **kwargs: Any) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._servicio = servicio_clinica
        self._mascota_seleccionada_id: int | None = None

        self._mapa_campos: dict[str, ctk.CTkBaseClass] = {}
        self._clientes_por_etiqueta: dict[str, int] = {}
        self._etiqueta_por_cliente_id: dict[int, str] = {}
        self._especies_por_nombre: dict[str, int] = {}
        self._nombre_por_especie_id: dict[int, str] = {}
        self._vacunas_por_etiqueta: dict[str, int] = {}

        self._construir_ui()
        self.refrescar_datos()

    # ==================================================================================
    # Construcción de la Interfaz (UI)
    # ==================================================================================

    def _construir_ui(self) -> None:
        """Divide la pantalla en panel de formulario izquierdo y panel maestro-detalle derecho."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=355)
        self.grid_columnconfigure(1, weight=1)

        # Cabecera
        marco_titulo = ctk.CTkFrame(self, fg_color="transparent")
        marco_titulo.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 6))

        ctk.CTkLabel(
            marco_titulo,
            text="Proceso 2: Mascotas, Historia Clínica (1 a 1) y Esquema de Vacunación",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")

        self._etiqueta_contador = ctk.CTkLabel(
            marco_titulo,
            text="0 mascotas registradas",
            font=ctk.CTkFont(size=13),
            text_color=("gray35", "gray70"),
        )
        self._etiqueta_contador.pack(side="right", padx=8)

        self._construir_panel_formulario()
        self._construir_panel_derecho()

    def _construir_panel_formulario(self) -> None:
        """Construye el formulario izquierdo para alta, edición y baja de mascotas."""
        panel = ctk.CTkFrame(self, corner_radius=10)
        panel.grid(row=1, column=0, sticky="nsew", padx=(10, 6), pady=4)
        panel.grid_columnconfigure(0, weight=1)

        self._titulo_formulario = ctk.CTkLabel(
            panel,
            text="Nueva Mascota",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._titulo_formulario.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        # 1. Cliente responsable (Obligatorio)
        ctk.CTkLabel(
            panel,
            text="Cliente Responsable (Obligatorio) *",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(4, 1))

        self._combo_cliente = ctk.CTkComboBox(
            panel,
            values=[OPCION_SIN_RESPONSABLE],
            height=31,
            state="readonly",
        )
        self._combo_cliente.set(OPCION_SIN_RESPONSABLE)
        self._combo_cliente.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 3))
        self._mapa_campos["cliente_id"] = self._combo_cliente

        # 2. Nombre de la mascota
        ctk.CTkLabel(
            panel,
            text="Nombre de la Mascota *",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=3, column=0, sticky="w", padx=14, pady=(4, 1))

        self._entrada_nombre = ctk.CTkEntry(
            panel, placeholder_text="Ej: Firulais", height=31
        )
        self._entrada_nombre.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 3))
        self._mapa_campos["nombre"] = self._entrada_nombre

        # 3. Especie y Sexo en la misma fila
        marco_esp_sexo = ctk.CTkFrame(panel, fg_color="transparent")
        marco_esp_sexo.grid(row=5, column=0, sticky="ew", padx=14, pady=(4, 3))
        marco_esp_sexo.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            marco_esp_sexo,
            text="Especie *",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 4))

        ctk.CTkLabel(
            marco_esp_sexo,
            text="Sexo *",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, sticky="w", padx=(4, 0))

        self._combo_especie = ctk.CTkComboBox(
            marco_esp_sexo, values=["Canino"], height=31, state="readonly"
        )
        self._combo_especie.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(1, 0))
        self._mapa_campos["especie_id"] = self._combo_especie

        self._combo_sexo = ctk.CTkComboBox(
            marco_esp_sexo, values=["Macho", "Hembra"], height=31, state="readonly"
        )
        self._combo_sexo.set("Macho")
        self._combo_sexo.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(1, 0))
        self._mapa_campos["sexo"] = self._combo_sexo

        # 4. Edad y Raza en la misma fila
        marco_edad_raza = ctk.CTkFrame(panel, fg_color="transparent")
        marco_edad_raza.grid(row=6, column=0, sticky="ew", padx=14, pady=(4, 3))
        marco_edad_raza.grid_columnconfigure(0, weight=0, minsize=105)
        marco_edad_raza.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            marco_edad_raza,
            text="Edad (años) *",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 4))

        ctk.CTkLabel(
            marco_edad_raza,
            text="Raza (opcional)",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, sticky="w", padx=(4, 0))

        self._entrada_edad = ctk.CTkEntry(
            marco_edad_raza, placeholder_text="Ej: 3", height=31, width=100
        )
        self._entrada_edad.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(1, 0))
        self._mapa_campos["edad"] = self._entrada_edad

        self._entrada_raza = ctk.CTkEntry(
            marco_edad_raza, placeholder_text="Ej: Mestizo / Labrador", height=31
        )
        self._entrada_raza.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(1, 0))
        self._mapa_campos["raza"] = self._entrada_raza

        # 5. Datos iniciales de Historia Clínica (para el alta 1 a 1)
        ctk.CTkLabel(
            panel,
            text="Antecedentes Clínicos Iniciales (Historia 1:1)",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=7, column=0, sticky="w", padx=14, pady=(6, 1))

        self._entrada_antecedentes_alta = ctk.CTkEntry(
            panel, placeholder_text="Ej: Sin cirugías previas", height=31
        )
        self._entrada_antecedentes_alta.grid(row=8, column=0, sticky="ew", padx=14, pady=(0, 3))

        ctk.CTkLabel(
            panel,
            text="Alergias Conocidas",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=9, column=0, sticky="w", padx=14, pady=(4, 1))

        self._entrada_alergias_alta = ctk.CTkEntry(
            panel, placeholder_text="Ej: Ninguna / Penicilina", height=31
        )
        self._entrada_alergias_alta.grid(row=10, column=0, sticky="ew", padx=14, pady=(0, 4))

        # Botonera del formulario
        marco_botones = ctk.CTkFrame(panel, fg_color="transparent")
        marco_botones.grid(row=11, column=0, sticky="ew", padx=14, pady=(8, 10))
        marco_botones.grid_columnconfigure((0, 1), weight=1)

        self._btn_guardar = ctk.CTkButton(
            marco_botones,
            text="Registrar Mascota + H. Clínica",
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._al_guardar_mascota,
        )
        self._btn_guardar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        ctk.CTkButton(
            marco_botones,
            text="Nueva Mascota",
            fg_color="#475569",
            hover_color="#334155",
            height=32,
            command=self._limpiar_formulario,
        ).grid(row=1, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(
            marco_botones,
            text="Eliminar Mascota",
            fg_color="#DC2626",
            hover_color="#B91C1C",
            height=32,
            command=self._al_eliminar_mascota,
        ).grid(row=1, column=1, sticky="ew", padx=(4, 0))

    def _construir_panel_derecho(self) -> None:
        """Crea el panel derecho dividido en tabla de mascotas (arriba) e Historia Clínica/Vacunas (abajo)."""
        panel = ctk.CTkFrame(self, fg_color="transparent")
        panel.grid(row=1, column=1, sticky="nsew", padx=(6, 10), pady=4)
        panel.grid_rowconfigure(0, weight=4)
        panel.grid_rowconfigure(1, weight=7)
        panel.grid_columnconfigure(0, weight=1)

        # Mitad superior: Tabla de Mascotas registradas
        marco_tabla = ctk.CTkFrame(panel, corner_radius=10)
        marco_tabla.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        marco_tabla.grid_rowconfigure(1, weight=1)
        marco_tabla.grid_columnconfigure(0, weight=1)

        barra_sup = ctk.CTkFrame(marco_tabla, fg_color="transparent")
        barra_sup.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))
        barra_sup.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            barra_sup,
            text="Padrón de Mascotas (seleccione una fila para ver su Historia Clínica y Vacunas)",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        columnas_mascotas = [
            ("id", "ID", 50),
            ("nombre", "Mascota", 125),
            ("especie", "Especie", 95),
            ("raza", "Raza", 130),
            ("edad", "Edad", 70),
            ("sexo", "Sexo", 80),
            ("responsable", "Cliente Responsable", 220),
        ]
        self._tabla_mascotas = TablaDatos(
            marco_tabla,
            columnas=columnas_mascotas,
            al_seleccionar=self._al_seleccionar_mascota,
            altura_filas=5,
        )
        self._tabla_mascotas.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        # Mitad inferior: Carpeta de Historia Clínica 1 a 1 y Esquema de Vacunación
        self._construir_panel_historia_y_vacunas(panel)

    def _construir_panel_historia_y_vacunas(self, contenedor: ctk.CTkFrame) -> None:
        """Construye el visor interactivo de Historia Clínica 1:1 y Vacunas."""
        marco_hc = ctk.CTkFrame(contenedor, corner_radius=10)
        marco_hc.grid(row=1, column=0, sticky="nsew", pady=(2, 0))
        marco_hc.grid_rowconfigure(2, weight=1)
        marco_hc.grid_columnconfigure(0, weight=1)

        # Fila 0: Título de la Historia Clínica 1 a 1
        self._etiqueta_paciente_hc = ctk.CTkLabel(
            marco_hc,
            text="Historia Clínica 1 a 1: Ninguna mascota seleccionada",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        self._etiqueta_paciente_hc.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 2))

        # Fila 1: Banner dedicado y multilínea para el estado del Esquema de Vacunas Obligatorias
        self._marco_banner_vacunas = ctk.CTkFrame(
            marco_hc, corner_radius=6, fg_color="#F1F5F9"
        )
        self._marco_banner_vacunas.grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 4))
        self._marco_banner_vacunas.grid_columnconfigure(0, weight=1)

        self._etiqueta_estado_vacunas = ctk.CTkLabel(
            self._marco_banner_vacunas,
            text="Seleccione una mascota en la tabla superior para verificar su esquema sanitario.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#475569",
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self._etiqueta_estado_vacunas.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # Fila 2: Pestañas internas con amplitud suficiente para mostrar controles y tablas completas
        self._tabs_hc = ctk.CTkTabview(marco_hc, height=250)
        self._tabs_hc.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 10))

        tab_vacunas = self._tabs_hc.add("Esquema de Vacunación")
        tab_antecedentes = self._tabs_hc.add("Antecedentes, Alergias y Tratamientos")

        # --- Tab 1: Vacunación ---
        tab_vacunas.grid_rowconfigure(1, weight=1)
        tab_vacunas.grid_columnconfigure(0, weight=1)

        barra_aplicar = ctk.CTkFrame(tab_vacunas, fg_color="transparent")
        barra_aplicar.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 6))
        barra_aplicar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            barra_aplicar,
            text="Vacuna:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 6))

        self._combo_vacuna = ctk.CTkComboBox(
            barra_aplicar,
            values=["Seleccione una mascota primero"],
            width=260,
            height=30,
            state="readonly",
        )
        self._combo_vacuna.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        ctk.CTkLabel(
            barra_aplicar,
            text="Fecha (AAAA-MM-DD):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=2, padx=(0, 6))

        self._entrada_fecha_vacuna = ctk.CTkEntry(
            barra_aplicar, width=115, height=30
        )
        self._entrada_fecha_vacuna.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self._entrada_fecha_vacuna.grid(row=0, column=3, padx=(0, 10))

        ctk.CTkButton(
            barra_aplicar,
            text="Registrar Dosis Aplicada",
            fg_color="#15803D",
            hover_color="#166534",
            width=175,
            height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._al_aplicar_vacuna,
        ).grid(row=0, column=4)

        columnas_vac = [
            ("id", "ID", 50),
            ("vacuna", "Vacuna Aplicada", 230),
            ("obligatoria", "Carácter Legal", 135),
            ("fecha", "Fecha de Aplicación", 145),
            ("consulta", "Origen de Aplicación", 180),
        ]
        self._tabla_vacunas = TablaDatos(
            tab_vacunas, columnas=columnas_vac, altura_filas=5
        )
        self._tabla_vacunas.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))

        # --- Tab 2: Antecedentes, Alergias y Tratamientos ---
        tab_antecedentes.grid_rowconfigure(1, weight=1)
        tab_antecedentes.grid_columnconfigure((0, 1), weight=1)

        barra_ant = ctk.CTkFrame(tab_antecedentes, fg_color="transparent")
        barra_ant.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(2, 6))
        barra_ant.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(barra_ant, text="Antecedentes:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, padx=(0, 4)
        )
        self._entrada_hc_antecedentes = ctk.CTkEntry(barra_ant, height=30)
        self._entrada_hc_antecedentes.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        ctk.CTkLabel(barra_ant, text="Alergias:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=2, padx=(0, 4)
        )
        self._entrada_hc_alergias = ctk.CTkEntry(barra_ant, height=30)
        self._entrada_hc_alergias.grid(row=0, column=3, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            barra_ant,
            text="Guardar Cambios H.C.",
            height=30,
            command=self._al_actualizar_historia_clinica,
        ).grid(row=0, column=4)

        columnas_trat = [
            ("id", "ID", 45),
            ("consulta_id", "Consulta #", 85),
            ("medicamento", "Medicamento", 150),
            ("dosis", "Posología / Dosis", 150),
            ("duracion", "Duración", 90),
            ("descripcion", "Indicación Terapéutica", 240),
        ]
        self._tabla_tratamientos_hc = TablaDatos(
            tab_antecedentes, columnas=columnas_trat, altura_filas=4
        )
        self._tabla_tratamientos_hc.grid(row=1, column=0, columnspan=2, sticky="nsew")

    # ==================================================================================
    # Manejadores de Eventos
    # ==================================================================================

    def _obtener_edad_validada(self) -> int:
        """Convierte la edad ingresada a entero o lanza ErrorDatosInvalidos."""
        texto_edad = self._entrada_edad.get().strip()
        if not texto_edad:
            raise ErrorDatosInvalidos("edad", "La edad de la mascota es obligatoria.")
        try:
            return int(texto_edad)
        except ValueError as err:
            raise ErrorDatosInvalidos(
                "edad", "La edad de la mascota debe ser un número entero de años cumplidos."
            ) from err

    def _al_guardar_mascota(self) -> None:
        """Registra una nueva mascota (y su Historia Clínica 1:1) o actualiza la seleccionada."""
        etiqueta_cliente = self._combo_cliente.get()
        cliente_id = self._clientes_por_etiqueta.get(etiqueta_cliente, 0)
        nombre = self._entrada_nombre.get().strip()
        nombre_especie = self._combo_especie.get()
        especie_id = self._especies_por_nombre.get(nombre_especie, 1)
        sexo = self._combo_sexo.get()
        raza = self._entrada_raza.get().strip() or None
        antecedentes = self._entrada_antecedentes_alta.get().strip() or None
        alergias = self._entrada_alergias_alta.get().strip() or None

        if self._mascota_seleccionada_id is None:
            def _crear() -> Mascota:
                edad = self._obtener_edad_validada()
                return self._servicio.registrar_mascota(
                    nombre=nombre,
                    especie_id=especie_id,
                    edad=edad,
                    sexo=sexo,
                    cliente_id=cliente_id,
                    raza=raza,
                    antecedentes=antecedentes,
                    alergias=alergias,
                )

            creada = ejecutar_accion_segura(
                _crear,
                mapa_campos=self._mapa_campos,
                titulo_error="No se pudo registrar la mascota",
            )
            if creada is not None and creada.id is not None:
                mostrar_exito(
                    "Mascota e Historia Clínica registradas",
                    f"Se registró a '{creada.nombre}' y se abrió su Historia Clínica 1 a 1.",
                )
                id_nueva = creada.id
                self._limpiar_formulario()
                self.refrescar_datos()
                self._al_seleccionar_mascota(str(id_nueva))
        else:
            id_actual = self._mascota_seleccionada_id

            def _actualizar() -> Mascota:
                edad = self._obtener_edad_validada()
                mascota_mod = Mascota(
                    id=id_actual,
                    nombre=nombre,
                    especie_id=especie_id,
                    edad=edad,
                    sexo=sexo,
                    cliente_id=cliente_id,
                    raza=raza,
                )
                actualizada = self._servicio.actualizar_mascota(mascota_mod)
                self._servicio.actualizar_historia_clinica(id_actual, antecedentes, alergias)
                return actualizada

            actualizada = ejecutar_accion_segura(
                _actualizar,
                mapa_campos=self._mapa_campos,
                titulo_error="No se pudo actualizar la mascota",
            )
            if actualizada is not None:
                mostrar_exito(
                    "Mascota actualizada",
                    f"Se actualizaron los datos de '{actualizada.nombre}'.",
                )
                self.refrescar_datos()
                self._cargar_panel_historia_y_vacunas(id_actual)

    def _al_eliminar_mascota(self) -> None:
        """Elimina la mascota seleccionada si no registra consultas médicas."""
        id_tabla = self._tabla_mascotas.obtener_id_seleccionado()
        if self._mascota_seleccionada_id is None and id_tabla is not None:
            self._al_seleccionar_mascota(id_tabla)

        if self._mascota_seleccionada_id is None:
            mostrar_advertencia(
                "Seleccione una mascota",
                "Primero haga clic sobre una mascota en la tabla superior para eliminarla.",
            )
            return

        id_eliminar = self._mascota_seleccionada_id
        nombre = self._entrada_nombre.get().strip() or f"#{id_eliminar}"
        if not confirmar_accion(
            "Confirmar eliminación",
            f"¿Desea eliminar la mascota '{nombre}' (ID #{id_eliminar}) y su Historia Clínica?",
        ):
            return

        resultado = ejecutar_accion_segura(
            lambda: (self._servicio.eliminar_mascota(id_eliminar), True)[1],
            titulo_error="No se pudo eliminar la mascota",
        )
        if resultado:
            mostrar_exito("Mascota eliminada", "El registro fue eliminado correctamente.")
            self._limpiar_formulario()
            self.refrescar_datos()

    def _al_seleccionar_mascota(self, id_fila: str) -> None:
        """Carga los datos de la mascota en el formulario y despliega su Historia Clínica y vacunas."""
        mascota_id = int(id_fila)
        mascota = ejecutar_accion_segura(
            lambda: self._servicio.obtener_mascota(mascota_id),
            titulo_error="Error al obtener mascota",
        )
        if mascota is None:
            return

        limpiar_resaltado_campos(self._mapa_campos)
        self._mascota_seleccionada_id = mascota.id
        self._titulo_formulario.configure(text=f"Editar Mascota #{mascota.id}")
        self._btn_guardar.configure(text="Actualizar Mascota")

        etiqueta_cli = self._etiqueta_por_cliente_id.get(
            mascota.cliente_id, OPCION_SIN_RESPONSABLE
        )
        self._combo_cliente.set(etiqueta_cli)

        nombre_esp = self._nombre_por_especie_id.get(mascota.especie_id, "Canino")
        self._combo_especie.set(nombre_esp)
        self._combo_sexo.set(mascota.sexo)

        self._entrada_nombre.delete(0, "end")
        self._entrada_nombre.insert(0, mascota.nombre)

        self._entrada_edad.delete(0, "end")
        self._entrada_edad.insert(0, str(mascota.edad))

        self._entrada_raza.delete(0, "end")
        self._entrada_raza.insert(0, mascota.raza or "")

        self._cargar_panel_historia_y_vacunas(mascota_id)

    def _cargar_panel_historia_y_vacunas(self, mascota_id: int) -> None:
        """Actualiza el panel inferior con la Historia Clínica 1:1 y el esquema de vacunas."""
        mascota = self._servicio.obtener_mascota(mascota_id)
        historia = self._servicio.obtener_historia_clinica_completa(mascota_id)
        pendientes = self._servicio.controlar_esquema_vacunacion(
            mascota_id, exigir_al_dia=False
        )

        self._etiqueta_paciente_hc.configure(
            text=f"Historia Clínica #{historia.id} — Paciente: {mascota.nombre} "
            f"({mascota.nombre_especie}) — Apertura: {historia.fecha_apertura}"
        )

        # Sincronizar campos de antecedentes y alergias en ambos lugares
        for entry in (self._entrada_antecedentes_alta, self._entrada_hc_antecedentes):
            entry.delete(0, "end")
            entry.insert(0, historia.antecedentes or "")
        for entry in (self._entrada_alergias_alta, self._entrada_hc_alergias):
            entry.delete(0, "end")
            entry.insert(0, historia.alergias or "")

        # Indicador visual de vacunas obligatorias en su propio banner
        if not pendientes:
            self._marco_banner_vacunas.configure(fg_color="#DCFCE7")
            self._etiqueta_estado_vacunas.configure(
                text="Esquema Sanitario Obligatorio: AL DÍA (todas las vacunas obligatorias vigentes).",
                text_color="#166534",
            )
        else:
            faltantes_txt = "  |  ".join(
                f"{p['nombre_vacuna']}: {p['motivo_pendiente']}" for p in pendientes
            )
            self._marco_banner_vacunas.configure(fg_color="#FEE2E2")
            self._etiqueta_estado_vacunas.configure(
                text=f"Vacunas Obligatorias Pendientes:  {faltantes_txt}",
                text_color="#991B1B",
            )

        # Poblar selector de vacunas del catálogo de la especie de la mascota
        catalogo_vac = self._servicio.listar_catalogo_vacunas(especie_id=mascota.especie_id)
        self._vacunas_por_etiqueta.clear()
        opciones_vac: list[str] = []
        for v in catalogo_vac:
            tipo_txt = "Obligatoria" if v["es_obligatoria"] else "Optativa"
            etiqueta = f"{v['nombre']} [{tipo_txt}]"
            self._vacunas_por_etiqueta[etiqueta] = int(v["id"])
            opciones_vac.append(etiqueta)

        if opciones_vac:
            self._combo_vacuna.configure(values=opciones_vac)
            self._combo_vacuna.set(opciones_vac[0])
        else:
            self._combo_vacuna.configure(values=["Sin vacunas catalogadas para esta especie"])
            self._combo_vacuna.set("Sin vacunas catalogadas para esta especie")

        # Poblar tabla de vacunas aplicadas
        filas_vac = [
            (
                va.id or idx,
                (
                    va.id,
                    va.nombre_vacuna,
                    "Obligatoria" if va.es_obligatoria else "Optativa",
                    va.fecha_aplicacion,
                    f"Consulta #{va.consulta_id}" if va.consulta_id else "Aplicación directa",
                ),
            )
            for idx, va in enumerate(historia.vacunas, start=1)
        ]
        self._tabla_vacunas.cargar_filas(filas_vac)

        # Poblar tabla de tratamientos históricos
        filas_trat = [
            (
                t.id or idx,
                (
                    t.id,
                    f"#{t.consulta_id}",
                    t.medicamento or "—",
                    t.dosis or "—",
                    f"{t.duracion_dias} días" if t.duracion_dias else "—",
                    t.descripcion,
                ),
            )
            for idx, t in enumerate(historia.tratamientos, start=1)
        ]
        self._tabla_tratamientos_hc.cargar_filas(filas_trat)

    def _al_aplicar_vacuna(self) -> None:
        """Registra una dosis de vacuna para la mascota seleccionada."""
        if self._mascota_seleccionada_id is None:
            mostrar_advertencia(
                "Seleccione una mascota",
                "Primero seleccione una mascota en la tabla superior para registrar una vacuna.",
            )
            return

        etiqueta_vac = self._combo_vacuna.get()
        vacuna_id = self._vacunas_por_etiqueta.get(etiqueta_vac)
        if vacuna_id is None:
            mostrar_advertencia("Vacuna no disponible", "No hay una vacuna válida seleccionada.")
            return

        fecha = self._entrada_fecha_vacuna.get().strip()
        mascota_id = self._mascota_seleccionada_id

        aplicada = ejecutar_accion_segura(
            lambda: self._servicio.aplicar_vacuna(
                mascota_id=mascota_id,
                vacuna_id=vacuna_id,
                fecha_aplicacion=fecha,
            ),
            titulo_error="No se pudo registrar la vacuna",
        )
        if aplicada is not None:
            mostrar_exito("Vacuna registrada", f"Se registró la aplicación de {etiqueta_vac}.")
            self._cargar_panel_historia_y_vacunas(mascota_id)

    def _al_actualizar_historia_clinica(self) -> None:
        """Guarda cambios de antecedentes y alergias desde la pestaña de Historia Clínica."""
        if self._mascota_seleccionada_id is None:
            mostrar_advertencia(
                "Seleccione una mascota",
                "Primero seleccione una mascota de la tabla superior.",
            )
            return

        mascota_id = self._mascota_seleccionada_id
        ant = self._entrada_hc_antecedentes.get().strip() or None
        aler = self._entrada_hc_alergias.get().strip() or None

        historia = ejecutar_accion_segura(
            lambda: self._servicio.actualizar_historia_clinica(mascota_id, ant, aler),
            titulo_error="No se pudo actualizar la Historia Clínica",
        )
        if historia is not None:
            mostrar_exito("Historia Clínica actualizada", "Se guardaron los antecedentes y alergias.")
            self._cargar_panel_historia_y_vacunas(mascota_id)

    def _limpiar_formulario(self) -> None:
        """Restablece el formulario al modo 'Nueva Mascota'."""
        limpiar_resaltado_campos(self._mapa_campos)
        self._mascota_seleccionada_id = None
        self._titulo_formulario.configure(text="Nueva Mascota")
        self._btn_guardar.configure(text="Registrar Mascota + H. Clínica")

        self._combo_cliente.set(OPCION_SIN_RESPONSABLE)
        self._entrada_nombre.delete(0, "end")
        self._entrada_edad.delete(0, "end")
        self._entrada_raza.delete(0, "end")
        self._entrada_antecedentes_alta.delete(0, "end")
        self._entrada_alergias_alta.delete(0, "end")
        self._tabla_mascotas.limpiar_seleccion()

    # ==================================================================================
    # Sincronización y Refresco de Datos
    # ==================================================================================

    def refrescar_datos(self) -> None:
        """Recarga el catálogo de especies, el padrón de clientes y la tabla de mascotas."""
        # 1. Especies
        especies = self._servicio.listar_especies()
        self._especies_por_nombre = {e["nombre"]: int(e["id"]) for e in especies}
        self._nombre_por_especie_id = {int(e["id"]): e["nombre"] for e in especies}
        nombres_especies = list(self._especies_por_nombre.keys())
        if nombres_especies:
            self._combo_especie.configure(values=nombres_especies)
            if self._combo_especie.get() not in self._especies_por_nombre:
                self._combo_especie.set(nombres_especies[0])

        # 2. Clientes responsables
        clientes = self._servicio.listar_clientes()
        self._clientes_por_etiqueta.clear()
        self._etiqueta_por_cliente_id.clear()
        opciones_clientes = [OPCION_SIN_RESPONSABLE]
        for c in clientes:
            if c.id is not None:
                etiqueta = f"{c.apellido}, {c.nombre} (DNI {c.dni})"
                self._clientes_por_etiqueta[etiqueta] = c.id
                self._etiqueta_por_cliente_id[c.id] = etiqueta
                opciones_clientes.append(etiqueta)

        seleccion_previa = self._combo_cliente.get()
        self._combo_cliente.configure(values=opciones_clientes)
        if seleccion_previa in opciones_clientes:
            self._combo_cliente.set(seleccion_previa)
        else:
            self._combo_cliente.set(OPCION_SIN_RESPONSABLE)

        # 3. Tabla de mascotas
        mascotas = self._servicio.listar_mascotas()
        filas = []
        for m in mascotas:
            if m.id is None:
                continue
            responsable_txt = self._etiqueta_por_cliente_id.get(
                m.cliente_id, f"Cliente ID #{m.cliente_id}"
            )
            filas.append(
                (
                    m.id,
                    (
                        m.id,
                        m.nombre,
                        m.nombre_especie or "—",
                        m.raza or "—",
                        f"{m.edad} años",
                        m.sexo,
                        responsable_txt,
                    ),
                )
            )
        self._tabla_mascotas.cargar_filas(filas)
        total = len(filas)
        sufijo = "mascota registrada" if total == 1 else "mascotas registradas"
        self._etiqueta_contador.configure(text=f"{total} {sufijo}")
