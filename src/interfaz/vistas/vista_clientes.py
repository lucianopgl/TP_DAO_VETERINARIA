"""
Vista Gráfica: Proceso 1 — Administración de Clientes (`VistaClientes`)
=======================================================================

Permite registrar nuevos clientes (responsables legales de mascotas), consultar
el padrón completo, filtrar en tiempo real por DNI/nombre/apellido, modificar
datos de contacto y eliminar registros sin mascotas asociadas.

Principios de Diseño POO aplicados:
    - Alta Cohesión / SRP: Separa la construcción de widgets (`_construir_ui`),
      la respuesta a eventos de usuario (`_al_guardar`, `_al_eliminar`, etc.)
      y la sincronización de datos (`refrescar_datos`).
    - Bajo Acoplamiento / DIP: Recibe únicamente `ServicioClinica` por constructor;
      no conoce detalles de SQLite ni de los DAOs.
"""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from src.dominio.cliente import Cliente
from src.interfaz.componentes.alertas import (
    confirmar_accion,
    ejecutar_accion_segura,
    limpiar_resaltado_campos,
    mostrar_advertencia,
    mostrar_exito,
)
from src.interfaz.componentes.tabla import TablaDatos
from src.servicios.servicio_clinica import ServicioClinica


class VistaClientes(ctk.CTkFrame):
    """Vista interactiva para el Proceso 1: Administrar Clientes."""

    def __init__(self, master: Any, servicio_clinica: ServicioClinica, **kwargs: Any) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._servicio = servicio_clinica
        self._cliente_seleccionado_id: int | None = None
        self._mapa_campos: dict[str, ctk.CTkEntry] = {}

        self._construir_ui()
        self.refrescar_datos()

    # ==================================================================================
    # Construcción de la Interfaz (UI)
    # ==================================================================================

    def _construir_ui(self) -> None:
        """Organiza la vista en dos paneles: formulario ABMC a la izquierda y tabla a la derecha."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=350)
        self.grid_columnconfigure(1, weight=1)

        # Cabecera de la sección
        marco_titulo = ctk.CTkFrame(self, fg_color="transparent")
        marco_titulo.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 6))

        ctk.CTkLabel(
            marco_titulo,
            text="Proceso 1: Administración de Clientes Responsables",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")

        self._etiqueta_contador = ctk.CTkLabel(
            marco_titulo,
            text="0 clientes registrados",
            font=ctk.CTkFont(size=13),
            text_color=("gray35", "gray70"),
        )
        self._etiqueta_contador.pack(side="right", padx=8)

        # Panel izquierdo: Formulario de Alta / Modificación / Baja
        self._construir_panel_formulario()

        # Panel derecho: Buscador, Tabla de Clientes y Barra de Acciones
        self._construir_panel_listado()

    def _construir_panel_formulario(self) -> None:
        """Crea el formulario de entrada de datos del cliente con validaciones visuales."""
        panel = ctk.CTkScrollableFrame(self, corner_radius=10)
        panel.grid(row=1, column=0, sticky="nsew", padx=(10, 6), pady=4)
        panel.grid_columnconfigure(0, weight=1)

        self._titulo_formulario = ctk.CTkLabel(
            panel,
            text="Nuevo Cliente",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._titulo_formulario.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        campos_definicion = [
            ("dni", "DNI (solo dígitos, 7 u 8 números) *", "Ej: 35123456"),
            ("nombre", "Nombre *", "Ej: Juan"),
            ("apellido", "Apellido *", "Ej: Pérez"),
            ("telefono", "Teléfono de Contacto (solo dígitos) *", "Ej: 3514567890"),
            ("email", "Correo Electrónico (opcional)", "Ej: cliente@correo.com"),
            ("direccion", "Domicilio (opcional)", "Ej: Av. Colón 1250, Córdoba"),
        ]

        fila_actual = 1
        for clave, etiqueta_texto, placeholder in campos_definicion:
            ctk.CTkLabel(
                panel,
                text=etiqueta_texto,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).grid(row=fila_actual, column=0, sticky="w", padx=14, pady=(4, 1))
            fila_actual += 1

            entrada = ctk.CTkEntry(
                panel,
                placeholder_text=placeholder,
                height=31,
            )
            entrada.grid(row=fila_actual, column=0, sticky="ew", padx=14, pady=(0, 2))
            entrada.bind("<Return>", lambda _e: self._al_guardar())
            self._mapa_campos[clave] = entrada
            fila_actual += 1

        ctk.CTkLabel(
            panel,
            text="* Campos obligatorios",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray65"),
        ).grid(row=fila_actual, column=0, sticky="w", padx=14, pady=(2, 4))
        fila_actual += 1

        # Botonera del formulario siempre visible
        marco_botones = ctk.CTkFrame(panel, fg_color="transparent")
        marco_botones.grid(row=fila_actual, column=0, sticky="ew", padx=14, pady=(4, 10))
        marco_botones.grid_columnconfigure((0, 1), weight=1)

        self._btn_guardar = ctk.CTkButton(
            marco_botones,
            text="Guardar Cliente",
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._al_guardar,
        )
        self._btn_guardar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        self._btn_limpiar = ctk.CTkButton(
            marco_botones,
            text="Nuevo Cliente",
            fg_color="#475569",
            hover_color="#334155",
            height=32,
            command=self._limpiar_formulario,
        )
        self._btn_limpiar.grid(row=1, column=0, sticky="ew", padx=(0, 4))

        self._btn_eliminar = ctk.CTkButton(
            marco_botones,
            text="Eliminar Cliente",
            fg_color="#DC2626",
            hover_color="#B91C1C",
            height=32,
            command=self._al_eliminar,
        )
        self._btn_eliminar.grid(row=1, column=1, sticky="ew", padx=(4, 0))

    def _construir_panel_listado(self) -> None:
        """Crea el panel derecho con buscador y tabla de clientes."""
        panel = ctk.CTkFrame(self, corner_radius=10)
        panel.grid(row=1, column=1, sticky="nsew", padx=(6, 10), pady=4)
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        # Barra superior de búsqueda
        barra_busqueda = ctk.CTkFrame(panel, fg_color="transparent")
        barra_busqueda.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
        barra_busqueda.grid_columnconfigure(0, weight=1)

        self._entrada_busqueda = ctk.CTkEntry(
            barra_busqueda,
            placeholder_text="Buscar por DNI, nombre o apellido...",
            height=34,
        )
        self._entrada_busqueda.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entrada_busqueda.bind("<KeyRelease>", lambda _e: self._al_buscar())
        self._entrada_busqueda.bind("<Return>", lambda _e: self._al_buscar())

        ctk.CTkButton(
            barra_busqueda,
            text="Limpiar",
            width=90,
            height=34,
            fg_color="#475569",
            hover_color="#334155",
            command=self._al_restablecer_busqueda,
        ).grid(row=0, column=1)

        # Tabla reutilizable
        columnas = [
            ("id", "ID", 55),
            ("dni", "DNI", 100),
            ("apellido", "Apellido", 135),
            ("nombre", "Nombre", 135),
            ("telefono", "Teléfono", 125),
            ("email", "Email", 180),
            ("direccion", "Domicilio", 200),
        ]
        self._tabla = TablaDatos(
            panel,
            columnas=columnas,
            al_seleccionar=self._al_seleccionar_fila,
            altura_filas=14,
        )
        self._tabla.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 6))

        # Pie de ayuda sobre la tabla
        ctk.CTkLabel(
            panel,
            text="Tip: Haga clic sobre cualquier fila de la tabla para cargar al cliente en el formulario, editarlo o eliminarlo.",
            font=ctk.CTkFont(size=11),
            text_color=("gray35", "gray70"),
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))

    # ==================================================================================
    # Manejadores de Eventos y Acciones
    # ==================================================================================

    def _al_guardar(self) -> None:
        """Registra un nuevo cliente o actualiza el cliente seleccionado."""
        dni = self._mapa_campos["dni"].get().strip()
        nombre = self._mapa_campos["nombre"].get().strip()
        apellido = self._mapa_campos["apellido"].get().strip()
        telefono = self._mapa_campos["telefono"].get().strip()
        email = self._mapa_campos["email"].get().strip() or None
        direccion = self._mapa_campos["direccion"].get().strip() or None

        if self._cliente_seleccionado_id is None:
            def _crear() -> Cliente:
                return self._servicio.registrar_cliente(
                    dni=dni,
                    nombre=nombre,
                    apellido=apellido,
                    telefono=telefono,
                    email=email,
                    direccion=direccion,
                )

            creado = ejecutar_accion_segura(
                _crear,
                mapa_campos=self._mapa_campos,
                titulo_error="No se pudo registrar el cliente",
            )
            if creado is not None:
                mostrar_exito(
                    "Cliente registrado",
                    f"Se registró correctamente a {creado.nombre_completo} (DNI {creado.dni}).",
                )
                self._limpiar_formulario()
                self.refrescar_datos()
        else:
            id_actual = self._cliente_seleccionado_id

            def _actualizar() -> Cliente:
                cliente_modificado = Cliente(
                    id=id_actual,
                    dni=dni,
                    nombre=nombre,
                    apellido=apellido,
                    telefono=telefono,
                    email=email,
                    direccion=direccion,
                )
                return self._servicio.actualizar_cliente(cliente_modificado)

            actualizado = ejecutar_accion_segura(
                _actualizar,
                mapa_campos=self._mapa_campos,
                titulo_error="No se pudo actualizar el cliente",
            )
            if actualizado is not None:
                mostrar_exito(
                    "Cliente actualizado",
                    f"Los datos de {actualizado.nombre_completo} fueron actualizados con éxito.",
                )
                self._limpiar_formulario()
                self.refrescar_datos()

    def _al_eliminar(self) -> None:
        """Elimina el cliente actualmente seleccionado tras confirmar con el usuario."""
        id_tabla = self._tabla.obtener_id_seleccionado()
        if self._cliente_seleccionado_id is None and id_tabla is not None:
            self._al_seleccionar_fila(id_tabla)

        if self._cliente_seleccionado_id is None:
            mostrar_advertencia(
                "Seleccione un cliente",
                "Para eliminar un cliente, primero haga clic sobre su fila en la tabla de la derecha.",
            )
            return

        id_eliminar = self._cliente_seleccionado_id
        nombre_mostrar = (
            f"{self._mapa_campos['apellido'].get().strip()}, "
            f"{self._mapa_campos['nombre'].get().strip()}"
        )
        if not confirmar_accion(
            "Confirmar eliminación",
            f"¿Está seguro de que desea eliminar al cliente '{nombre_mostrar}' (ID #{id_eliminar})?\n\n"
            "Nota: Si el cliente posee mascotas asociadas, la base de datos impedirá su baja "
            "para preservar la integridad referencial.",
        ):
            return

        def _borrar() -> bool:
            self._servicio.eliminar_cliente(id_eliminar)
            return True

        resultado = ejecutar_accion_segura(
            _borrar,
            titulo_error="No se pudo eliminar el cliente",
        )
        if resultado:
            mostrar_exito("Cliente eliminado", "El cliente fue eliminado del padrón.")
            self._limpiar_formulario()
            self.refrescar_datos()

    def _al_seleccionar_fila(self, id_fila: str) -> None:
        """Carga en el formulario los datos del cliente seleccionado en la tabla."""
        cliente_id = int(id_fila)
        cliente = ejecutar_accion_segura(
            lambda: self._servicio.obtener_cliente(cliente_id),
            titulo_error="Error al cargar cliente",
        )
        if cliente is None:
            return

        limpiar_resaltado_campos(self._mapa_campos)
        self._cliente_seleccionado_id = cliente.id
        self._titulo_formulario.configure(text=f"Editar Cliente #{cliente.id}")
        self._btn_guardar.configure(text="Actualizar Cliente")

        valores = {
            "dni": cliente.dni,
            "nombre": cliente.nombre,
            "apellido": cliente.apellido,
            "telefono": cliente.telefono,
            "email": cliente.email or "",
            "direccion": cliente.direccion or "",
        }
        for clave, texto in valores.items():
            campo = self._mapa_campos[clave]
            campo.delete(0, "end")
            campo.insert(0, texto)

    def _al_buscar(self) -> None:
        """Filtra la tabla de clientes según el término escrito en el buscador."""
        termino = self._entrada_busqueda.get().strip()
        clientes = self._servicio.buscar_clientes(termino)
        self._poblar_tabla(clientes)

    def _al_restablecer_busqueda(self) -> None:
        """Limpia el cuadro de búsqueda y vuelve a mostrar todos los clientes."""
        self._entrada_busqueda.delete(0, "end")
        self.refrescar_datos()

    def _limpiar_formulario(self) -> None:
        """Restablece el formulario al modo 'Nuevo Cliente'."""
        limpiar_resaltado_campos(self._mapa_campos)
        self._cliente_seleccionado_id = None
        self._titulo_formulario.configure(text="Nuevo Cliente")
        self._btn_guardar.configure(text="Guardar Cliente")

        for campo in self._mapa_campos.values():
            campo.delete(0, "end")

        self._tabla.limpiar_seleccion()

    # ==================================================================================
    # Sincronización y Refresco de Datos
    # ==================================================================================

    def refrescar_datos(self) -> None:
        """Recarga el padrón de clientes desde el servicio de clínica."""
        termino = self._entrada_busqueda.get().strip()
        clientes = (
            self._servicio.buscar_clientes(termino)
            if termino
            else self._servicio.listar_clientes()
        )
        self._poblar_tabla(clientes)

    def _poblar_tabla(self, clientes: list[Cliente]) -> None:
        """Transforma las entidades `Cliente` en tuplas para `TablaDatos`."""
        filas = [
            (
                c.id,
                (
                    c.id,
                    c.dni,
                    c.apellido,
                    c.nombre,
                    c.telefono,
                    c.email or "—",
                    c.direccion or "—",
                ),
            )
            for c in clientes
            if c.id is not None
        ]
        self._tabla.cargar_filas(filas)
        total = len(filas)
        sufijo = "cliente registrado" if total == 1 else "clientes registrados"
        self._etiqueta_contador.configure(text=f"{total} {sufijo}")
