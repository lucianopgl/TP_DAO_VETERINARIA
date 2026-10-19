"""
Paquete raíz del sistema "Veterinaria: Red de Clínicas y Derivación de Laboratorio".

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
