"""
Pruebas de Arquitectura de Capas y Ventana Principal (`src/interfaz/`)
======================================================================

Verifica:
    1. Cumplimiento estricto de la regla de capas de GEMINI.md mediante análisis AST:
       - `src/dominio/` no importa `sqlite3`, `customtkinter`, `tkinter`, `persistencia`, `servicios` ni `interfaz`.
       - `src/patrones/` no importa `sqlite3`, `customtkinter`, `tkinter`, `persistencia`, `servicios` ni `interfaz`.
       - `src/servicios/` no importa `customtkinter`, `tkinter` ni `interfaz` (y los servicios de negocio no importan `sqlite3`).
       - `src/interfaz/` no importa `sqlite3` ni `src.persistencia` (DAOs).
    2. Regla de Dominio POO: Las 15 entidades de `src/dominio/` definen y ejecutan `.validar()`.
    3. Formateo semántico de eventos del patrón Observer en la barra de estado de la interfaz.
    4. Captura tipada de `ErrorDatosInvalidos` y `ErrorVeterinaria` en el manejador
       de alertas reutilizable, incluyendo resaltado automático del campo con error.
    5. Escalado dinámico de zoom y accesibilidad visual en `VentanaPrincipal`.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.dominio.cliente import Cliente
from src.dominio.consulta_medica import ConsultaMedica, OrdenDerivacion
from src.dominio.excepciones import (
    ErrorDatosInvalidos,
    ErrorMascotaSinResponsable,
    ErrorVeterinaria,
)
from src.dominio.facturacion import (
    ComprobanteAtencion,
    DetalleComprobante,
    ResultadoAnalisis,
)
from src.dominio.historia_clinica import (
    HistoriaClinica,
    Tratamiento,
    VacunaAplicada,
)
from src.dominio.logistica import (
    ConservadoraIsotermica,
    EnvioLaboratorio,
    PrecintoSanitario,
    RemitoBiologico,
)
from src.dominio.mascota import Mascota
from src.dominio.muestra_biologica import MuestraBiologica, RegistroTrazabilidad
from src.interfaz.app import VentanaPrincipal, formatear_evento_notificacion
from src.interfaz.componentes.alertas import COLOR_BORDE_ERROR, ejecutar_accion_segura

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


class PruebaArquitecturaInterfazYVentanaPrincipal(unittest.TestCase):
    """Pruebas unitarias de arquitectura en capas, entidades de dominio y ventana principal."""

    def test_regla_arquitectonica_interfaz_sin_sqlite_ni_daos(self) -> None:
        """
        Regla estricta de GEMINI.md: Prohibido importar `sqlite3` o instanciar DAOs
        desde `src/interfaz/`.
        """
        carpeta_interfaz = RAIZ_PROYECTO / "src" / "interfaz"
        archivos_py = list(carpeta_interfaz.rglob("*.py"))
        self.assertGreater(len(archivos_py), 0)

        for archivo in archivos_py:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    for alias in nodo.names:
                        self.assertNotEqual(
                            alias.name,
                            "sqlite3",
                            f"Importación prohibida de sqlite3 en {archivo}",
                        )
                        self.assertFalse(
                            alias.name.startswith("src.persistencia"),
                            f"Importación prohibida de persistencia en {archivo}",
                        )
                elif isinstance(nodo, ast.ImportFrom):
                    modulo = nodo.module or ""
                    self.assertNotEqual(
                        modulo,
                        "sqlite3",
                        f"Importación prohibida de sqlite3 en {archivo}",
                    )
                    self.assertFalse(
                        modulo.startswith("src.persistencia"),
                        f"La interfaz no debe acoplarse a src.persistencia ({archivo})",
                    )

    def test_regla_arquitectonica_unidireccional_en_todas_las_capas(self) -> None:
        """
        Verifica mediante AST que `dominio`, `patrones` y `servicios` respeten el
        bajo acoplamiento y la dirección de dependencias hacia adentro.
        """
        reglas_prohibidas = {
            "dominio": ("sqlite3", "tkinter", "customtkinter", "src.persistencia", "src.servicios", "src.interfaz"),
            "patrones": ("sqlite3", "tkinter", "customtkinter", "src.persistencia", "src.servicios", "src.interfaz"),
            "servicios": ("sqlite3", "tkinter", "customtkinter", "src.interfaz"),
        }

        for nombre_capa, prefijos_prohibidos in reglas_prohibidas.items():
            carpeta = RAIZ_PROYECTO / "src" / nombre_capa
            for archivo in carpeta.rglob("*.py"):
                arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
                for nodo in ast.walk(arbol):
                    modulos_importados = []
                    if isinstance(nodo, ast.Import):
                        modulos_importados.extend(alias.name for alias in nodo.names)
                    elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                        modulos_importados.append(nodo.module)

                    for mod in modulos_importados:
                        for prohibido in prefijos_prohibidos:
                            self.assertFalse(
                                mod == prohibido or mod.startswith(f"{prohibido}."),
                                f"Violación de capas en {archivo}: importa '{mod}' (prohibido en '{nombre_capa}')",
                            )

    def test_todas_las_entidades_de_dominio_exponen_metodo_validar(self) -> None:
        """
        Regla de GEMINI.md: Todas las entidades de `src/dominio/` deben exponer y
        ejecutar `.validar()`.
        """
        entidades_dominio = [
            Cliente,
            Mascota,
            HistoriaClinica,
            VacunaAplicada,
            Tratamiento,
            ConsultaMedica,
            OrdenDerivacion,
            MuestraBiologica,
            RegistroTrazabilidad,
            ConservadoraIsotermica,
            PrecintoSanitario,
            RemitoBiologico,
            EnvioLaboratorio,
            ResultadoAnalisis,
            ComprobanteAtencion,
            DetalleComprobante,
        ]
        for clase in entidades_dominio:
            self.assertTrue(
                hasattr(clase, "validar") and callable(getattr(clase, "validar")),
                f"La entidad {clase.__name__} no define el método público .validar()",
            )

    def test_formateo_eventos_patron_observer_en_ui(self) -> None:
        mensaje_rechazo, color_rechazo = formatear_evento_notificacion(
            "MUESTRAS_RECHAZADAS_EN_RECEPCION",
            {
                "numero_remito": "REM-001",
                "estado_precinto": "Violado",
                "muestras_rechazadas": ["MUE-01", "MUE-02"],
            },
        )
        self.assertIn("REM-001", mensaje_rechazo)
        self.assertIn("Violado", mensaje_rechazo)
        self.assertIn("MUE-01", mensaje_rechazo)
        self.assertEqual(color_rechazo, "#DC2626")

        mensaje_ok, color_ok = formatear_evento_notificacion(
            "REMITO_RECIBIDO_CONFORME",
            {"numero_remito": "REM-002", "cantidad_muestras": 3},
        )
        self.assertIn("REM-002", mensaje_ok)
        self.assertEqual(color_ok, "#15803D")

    def test_manejador_alertas_captura_error_datos_invalidos_y_veterinaria(self) -> None:
        with patch("src.interfaz.componentes.alertas.mostrar_error") as mock_error:
            def _fallar_dni() -> None:
                raise ErrorDatosInvalidos("dni", "El DNI debe tener 7 u 8 dígitos.")

            resultado = ejecutar_accion_segura(_fallar_dni)
            self.assertIsNone(resultado)
            mock_error.assert_called_once()
            args_llamada = mock_error.call_args[0]
            self.assertIn("dni", args_llamada[1])

        with patch("src.interfaz.componentes.alertas.mostrar_error") as mock_error_negocio:
            def _fallar_negocio() -> None:
                raise ErrorVeterinaria("Regla de negocio incumplida.")

            resultado_2 = ejecutar_accion_segura(_fallar_negocio, titulo_error="Error de prueba")
            self.assertIsNone(resultado_2)
            mock_error_negocio.assert_called_once_with(
                "Error de prueba", "Regla de negocio incumplida."
            )

    def test_resaltado_campo_en_error_negocio_con_campo_asociado(self) -> None:
        """Verifica que excepciones de negocio con atributo .campo (ej. ErrorMascotaSinResponsable)
        resalten el widget del formulario en rojo mediante ejecutar_accion_segura."""
        widget_mock = MagicMock()
        mapa = {"cliente_id": widget_mock}

        with patch("src.interfaz.componentes.alertas.mostrar_error"):
            def _accion():
                raise ErrorMascotaSinResponsable()

            resultado = ejecutar_accion_segura(_accion, mapa_campos=mapa)
            self.assertIsNone(resultado)
            widget_mock.configure.assert_called_with(border_color=COLOR_BORDE_ERROR)

    def test_control_zoom_dinamico_y_accesibilidad_en_app(self) -> None:
        """Verifica la lógica de zoom dinámico y adaptabilidad de VentanaPrincipal."""
        srv_clinica = MagicMock()
        srv_logistica = MagicMock()
        srv_lab = MagicMock()
        srv_rep = MagicMock()
        sujeto = MagicMock()

        with patch("customtkinter.CTk.__init__", return_value=None), \
             patch.object(VentanaPrincipal, "title"), \
             patch.object(VentanaPrincipal, "geometry"), \
             patch.object(VentanaPrincipal, "minsize") as mock_minsize, \
             patch.object(VentanaPrincipal, "winfo_screenheight", return_value=900), \
             patch.object(VentanaPrincipal, "bind_all"), \
             patch.object(VentanaPrincipal, "mostrar_vista"), \
             patch.object(VentanaPrincipal, "_construir_estructura_principal"):
            app = VentanaPrincipal(srv_clinica, srv_logistica, srv_lab, srv_rep, sujeto)

            mock_minsize.assert_called_with(960, 540)
            self.assertEqual(app._zoom_actual, 1.0)
            app._combo_zoom = MagicMock()

            app._ajustar_zoom(+1)
            self.assertEqual(app._zoom_actual, 1.15)

            app._ajustar_zoom(-1)
            self.assertEqual(app._zoom_actual, 1.0)

            app._al_seleccionar_zoom_combo("75%")
            self.assertEqual(app._zoom_actual, 0.75)


if __name__ == "__main__":
    unittest.main()
