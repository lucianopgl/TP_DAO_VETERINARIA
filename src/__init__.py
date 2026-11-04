"""
Paquete raíz del sistema "Veterinaria: Red de Clínicas y Derivación de Laboratorio".

Cátedra: Desarrollo de Aplicaciones con Objetos (DAO) — UTN FRC (2026)
Tema:    Tema 2 — Veterinaria: Red de Clínicas y Derivación de Laboratorio
Grupo:   Grupo 089
Integrantes:
    - 85656 Bertoni Rocio
    - 90074 Simonetti Franco
    - 90175 Ojea Nicolas
    - 94030 Diaz Tomás Agustín
    - 95738 Paglino Luciano Ivo

Organización en capas:

    dominio/       Entidades del negocio, reglas puras y excepciones propias.
    patrones/      Implementaciones explícitas de patrones de diseño (State, Strategy, Iterator...).
    persistencia/  Acceso a datos con SQLite: conexión (Singleton), esquema y objetos DAO.
    servicios/     Coordinación de los procesos de negocio obligatorios y los reportes.
    interfaz/      Interfaz gráfica de usuario construida con CustomTkinter.

Regla de dependencias: cada capa sólo conoce a las capas inferiores.
La interfaz usa servicios; los servicios usan dominio y persistencia;
el dominio no depende de ninguna otra capa.
"""
