"""
Pruebas de Arquitectura y Etapa 1 de Interfaz Gráfica (`src/interfaz/`)
=======================================================================

Verifica:
    1. Cumplimiento estricto de la regla de capas de GEMINI.md: ningún archivo dentro
       de `src/interfaz/` ni de `src/dominio/` importa `sqlite3` ni clases DAO.
    2. Formateo semántico de eventos del patrón Observer en la interfaz.
    3. Captura tipada de `ErrorDatosInvalidos` y `ErrorVeterinaria` en el manejador
       de alertas reutilizable.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from src.dominio.excepciones import ErrorDatosInvalidos, ErrorVeterinaria
from src.interfaz.app import formatear_evento_notificacion
from src.interfaz.componentes.alertas import ejecutar_accion_segura

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


class PruebaInterfazEtapa1(unittest.TestCase):
    """Pruebas unitarias de arquitectura y componentes base de la Etapa 1."""

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
        from unittest.mock import MagicMock
        from src.dominio.excepciones import ErrorMascotaSinResponsable
        from src.interfaz.componentes.alertas import COLOR_BORDE_ERROR

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
        from src.interfaz.app import VentanaPrincipal
        from unittest.mock import MagicMock, patch

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
