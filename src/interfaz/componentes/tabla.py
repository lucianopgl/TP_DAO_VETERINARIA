"""
Componente Reutilizable: Tabla de Datos Estilizada (`TablaDatos`)
=================================================================

Encapsula un control `ttk.Treeview` (del apunte de cátedra 'Interfaz grafica.pdf')
integrado dentro de un contenedor `ctk.CTkFrame` con barras de desplazamiento
vertical y horizontal, filas cebradas (pares/impares) y manejo limpio de eventos
de selección.

Principios aplicados:
    - Alta Cohesión y Responsabilidad Única (SRP): Gestiona exclusivamente la
      visualización tabular y la selección de filas por ID.
    - DRY: Todas las vistas del sistema reutilizan esta clase sin repetir código
      de configuración de estilos `ttk.Style`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from tkinter import ttk
from typing import Any

import customtkinter as ctk


class TablaDatos(ctk.CTkFrame):
    """
    Tabla reutilizable con encabezados configurables, scrollbars y selección simple.

    Cada columna se define mediante una tupla:
        `(id_columna, titulo_encabezado, ancho_pixeles)`
    """

    _estilo_inicializado: bool = False

    def __init__(
        self,
        master: Any,
        columnas: Sequence[tuple[str, str, int]],
        al_seleccionar: Callable[[str], None] | None = None,
        altura_filas: int = 12,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._columnas = list(columnas)
        self._al_seleccionar = al_seleccionar
        self._altura_filas = altura_filas

        self._configurar_estilo_treeview()
        self._construir_ui()

    @classmethod
    def _configurar_estilo_treeview(cls) -> None:
        """Configura por única vez el tema 'clam' y los colores de las tablas."""
        if cls._estilo_inicializado:
            return
        estilo = ttk.Style()
        if "clam" in estilo.theme_names():
            estilo.theme_use("clam")

        estilo.configure(
            "Veterinaria.Treeview",
            background="#FFFFFF",
            foreground="#1E293B",
            fieldbackground="#FFFFFF",
            rowheight=30,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        estilo.configure(
            "Veterinaria.Treeview.Heading",
            background="#1E3A8A",
            foreground="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=(8, 6),
        )
        estilo.map(
            "Veterinaria.Treeview.Heading",
            background=[("active", "#1D4ED8")],
        )
        estilo.map(
            "Veterinaria.Treeview",
            background=[("selected", "#2563EB")],
            foreground=[("selected", "#FFFFFF")],
        )
        cls._estilo_inicializado = True

    def _construir_ui(self) -> None:
        """Construye el Treeview y sus barras de desplazamiento vertical y horizontal."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ids_columnas = [col[0] for col in self._columnas]
        self._tree = ttk.Treeview(
            self,
            columns=ids_columnas,
            show="headings",
            selectmode="browse",
            height=self._altura_filas,
            style="Veterinaria.Treeview",
        )

        for id_col, titulo, ancho in self._columnas:
            self._tree.heading(id_col, text=titulo, anchor="w")
            self._tree.column(id_col, width=ancho, minwidth=max(50, ancho // 2), anchor="w")

        self._tree.tag_configure("fila_par", background="#F8FAFC")
        self._tree.tag_configure("fila_impar", background="#FFFFFF")

        scroll_y = ctk.CTkScrollbar(self, orientation="vertical", command=self._tree.yview)
        scroll_x = ctk.CTkScrollbar(self, orientation="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self._tree.bind("<<TreeviewSelect>>", self._manejar_evento_seleccion)

    def _manejar_evento_seleccion(self, _evento: Any = None) -> None:
        """Notifica al callback registrado cuando el usuario selecciona una fila."""
        if self._al_seleccionar is None:
            return
        id_seleccionado = self.obtener_id_seleccionado()
        if id_seleccionado is not None:
            self._al_seleccionar(id_seleccionado)

    def cargar_filas(self, filas: Sequence[tuple[str | int, Sequence[Any]]]) -> None:
        """
        Reemplaza el contenido de la tabla con los registros recibidos.

        Args:
            filas: Secuencia de tuplas `(id_fila, valores_columnas)`.
        """
        for item_id in self._tree.get_children():
            self._tree.delete(item_id)

        for indice, (id_fila, valores) in enumerate(filas):
            etiqueta = "fila_par" if indice % 2 == 0 else "fila_impar"
            valores_formateados = ["" if v is None else str(v) for v in valores]
            self._tree.insert(
                "",
                "end",
                iid=str(id_fila),
                values=valores_formateados,
                tags=(etiqueta,),
            )

    def obtener_id_seleccionado(self) -> str | None:
        """Devuelve el identificador (`iid`) de la fila seleccionada o `None`."""
        seleccion = self._tree.selection()
        if not seleccion:
            return None
        return str(seleccion[0])

    def limpiar_seleccion(self) -> None:
        """Desmarca cualquier fila actualmente seleccionada en la tabla."""
        seleccion = self._tree.selection()
        if seleccion:
            self._tree.selection_remove(seleccion)

    def cantidad_filas(self) -> int:
        """Devuelve el número total de filas cargadas actualmente en la tabla."""
        return len(self._tree.get_children())
