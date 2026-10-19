"""
Entidad de Dominio: Cliente
===========================

Representa al propietario o responsable legal de una o más mascotas atendidas
en la red de clínicas veterinarias.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from src.dominio.excepciones import ErrorDatosInvalidos


@dataclass
class Cliente:
    """
    Entidad de dominio que modela a un cliente/responsable.

    Atributos:
        id: Identificador numérico único de la base de datos (None si es nuevo).
        dni: Documento nacional de identidad (7 u 8 dígitos numéricos).
        nombre: Nombre del cliente.
        apellido: Apellido del cliente.
        telefono: Teléfono principal de contacto.
        email: Correo electrónico opcional de contacto.
        direccion: Domicilio de residencia.
    """
    id: int | None
    dni: str
    nombre: str
    apellido: str
    telefono: str
    email: str | None = None
    direccion: str | None = None

    def __post_init__(self) -> None:
        self.validar()

    def validar(self) -> None:
        """Valida las reglas de formato del cliente a nivel de dominio."""
        dni_limpio = self.dni.strip() if self.dni else ""
        if not dni_limpio.isdigit() or not (7 <= len(dni_limpio) <= 8):
            raise ErrorDatosInvalidos("dni", "El DNI debe contener solo números (entre 7 y 8 dígitos).")
        self.dni = dni_limpio

        if not self.nombre or not self.nombre.strip():
            raise ErrorDatosInvalidos("nombre", "El nombre del cliente no puede estar vacío.")
        self.nombre = self.nombre.strip()

        if not self.apellido or not self.apellido.strip():
            raise ErrorDatosInvalidos("apellido", "El apellido del cliente no puede estar vacío.")
        self.apellido = self.apellido.strip()

        if not self.telefono or not self.telefono.strip():
            raise ErrorDatosInvalidos("telefono", "El teléfono de contacto es obligatorio.")
        self.telefono = self.telefono.strip()

        if self.email:
            email_limpio = self.email.strip()
            if email_limpio and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_limpio):
                raise ErrorDatosInvalidos("email", "El correo electrónico no tiene un formato válido.")
            self.email = email_limpio or None

        if self.direccion:
            self.direccion = self.direccion.strip() or None

    @property
    def nombre_completo(self) -> str:
        """Devuelve el apellido y nombre formateados para presentación."""
        return f"{self.apellido}, {self.nombre}"

    def __str__(self) -> str:
        return f"{self.nombre_completo} (DNI: {self.dni})"
