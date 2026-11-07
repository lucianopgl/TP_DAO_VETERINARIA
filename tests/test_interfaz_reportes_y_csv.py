"""
Pruebas Unitarias y de Integración: Vista de Reportes y Exportación CSV (`src/interfaz/vistas/vista_reportes.py`)
=================================================================================================================

Verifica:
    1. Regla arquitectónica de capas (AST): Prohibido importar `sqlite3` o
       acoplarse a `src.persistencia` desde `vista_reportes.py`.
    2. Hidratación de los 5 reportes no triviales en `VistaReportes` con base
       de datos en memoria.
    3. Validación tipada de filtros de fechas y rangos (`ErrorDatosInvalidos`).
    4. Exportación efectiva a formato CSV de la pestaña actual (incluyendo tabla
       secundaria) y del paquete completo de los 5 reportes.
"""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.dominio.excepciones import ErrorDatosInvalidos
from src.interfaz.vistas.vista_reportes import (
    TAB_ATENCIONES,
    TAB_FACTURACION,
    TAB_RECHAZOS,
    TAB_TIEMPOS_SLA,
    TAB_VACUNAS_TRAT,
    VistaReportes,
)
from src.patrones.observador_eventos import SujetoEventos
from src.persistencia.conexion_bd import RUTA_BD_EN_MEMORIA, ConexionBD
from src.persistencia.inicializador_bd import inicializar_base_datos
from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_laboratorio import ServicioLaboratorio
from src.servicios.servicio_logistica import ServicioLogistica
from src.servicios.servicio_reportes import ServicioReportes

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


class PruebaInterfazReportesYExportacionCSV(unittest.TestCase):
    """Pruebas de arquitectura, carga de los 5 reportes y exportación CSV en VistaReportes."""

    def test_vista_reportes_sin_dependencia_sqlite_ni_daos(self) -> None:
        """Verifica mediante AST que vista_reportes.py no importe sqlite3 ni persistencia."""
        archivo = RAIZ_PROYECTO / "src" / "interfaz" / "vistas" / "vista_reportes.py"
        self.assertTrue(archivo.exists(), f"El archivo {archivo} no existe.")
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))

        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    self.assertNotEqual(alias.name, "sqlite3")
                    self.assertFalse(alias.name.startswith("src.persistencia"))
            elif isinstance(nodo, ast.ImportFrom):
                modulo = nodo.module or ""
                self.assertNotEqual(modulo, "sqlite3")
                self.assertFalse(modulo.startswith("src.persistencia"))

    def test_integracion_cinco_reportes_y_exportacion_csv(self) -> None:
        """
        Verifica que VistaReportes cargue los 5 reportes no triviales, actualice KPIs,
        valide filtros de fechas y exporte a archivo CSV.
        """
        ConexionBD.reiniciar_instancia()
        conexion = inicializar_base_datos(ConexionBD.obtener_instancia(RUTA_BD_EN_MEMORIA))
        eventos = SujetoEventos()
        srv_clinica = ServicioClinica(conexion)
        srv_logistica = ServicioLogistica(conexion, eventos)
        srv_lab = ServicioLaboratorio(conexion, eventos)
        srv_reportes = ServicioReportes(conexion)

        # Generar datos en los procesos 1 a 7 para poblar los 5 reportes
        cli = srv_clinica.registrar_cliente("33444555", "Laura", "Martínez", "3519998877")
        mascota = srv_clinica.registrar_mascota(
            nombre="Luna",
            especie_id=1,
            edad=4,
            sexo="Hembra",
            cliente_id=cli.id,
            raza="Caniche",
        )
        consulta, _ = srv_clinica.registrar_consulta_medica(
            mascota_id=mascota.id,
            clinica_id=1,
            veterinario_id=1,
            fecha_hora_inicio="2026-04-01 10:00:00",
            motivo="Control general",
            costo_consulta=12000.0,
        )
        orden = srv_clinica.emitir_orden_derivacion(
            consulta_id=consulta.id,
            tipo_estudio_id=1,
            indicaciones="Chequeo",
            prioridad="Urgente",
        )
        muestra = srv_clinica.extraer_muestra_biologica(
            orden_id=orden.id,
            codigo_muestra="MUE-REP-01",
            tipo_muestra_id=1,
            fecha_hora_extraccion="2026-04-01 10:15:00",
        )
        remito = srv_logistica.empaquetar_muestras(
            numero_remito="REM-REP-01",
            clinica_origen_id=1,
            laboratorio_destino_id=1,
            conservadora_id=1,
            numero_serie_precinto="PREC-REP-01",
            muestras_ids=[muestra.id],
            fecha_hora="2026-04-01 10:30:00",
        )
        srv_logistica.despachar_remito(
            remito_id=remito.id,
            transportista_id=1,
            fecha_hora_despacho="2026-04-01 11:00:00",
        )
        srv_logistica.recibir_remito_en_laboratorio(
            remito_id=remito.id,
            estado_precinto="Intacto",
            fecha_hora_recepcion="2026-04-01 12:30:00",
        )
        srv_lab.registrar_resultado_analisis(
            muestra_id=muestra.id,
            profesional_laboratorio_id=1,
            valores_medidos="Hematocrito 44%",
            conclusion="Parámetros normales",
            costo_analisis=5000.0,
            fecha_hora_analisis="2026-04-01 14:00:00",
        )
        srv_lab.emitir_comprobante_atencion(
            consulta_id=consulta.id,
            numero_comprobante="FAC-REP-001",
            estrategia="Tarifa Urgencia",
            fecha_hora_emision="2026-04-01 15:00:00",
        )

        # Muestra rechazada para poblar Reporte 2
        muestra_rech = srv_clinica.extraer_muestra_biologica(
            orden_id=orden.id,
            codigo_muestra="MUE-REP-RECH",
            tipo_muestra_id=1,
            fecha_hora_extraccion="2026-04-01 10:20:00",
        )
        remito_rech = srv_logistica.empaquetar_muestras(
            numero_remito="REM-REP-02",
            clinica_origen_id=1,
            laboratorio_destino_id=1,
            conservadora_id=1,
            numero_serie_precinto="PREC-REP-02",
            muestras_ids=[muestra_rech.id],
            fecha_hora="2026-04-01 10:40:00",
        )
        srv_logistica.despachar_remito(
            remito_id=remito_rech.id,
            transportista_id=1,
            fecha_hora_despacho="2026-04-01 11:10:00",
        )
        srv_logistica.recibir_remito_en_laboratorio(
            remito_id=remito_rech.id,
            estado_precinto="Roto",
            fecha_hora_recepcion="2026-04-01 12:45:00",
        )

        def _mock_construir_ui(instance: VistaReportes) -> None:
            instance._combo_clinica = MagicMock()
            instance._combo_clinica.get.return_value = "Todas las clínicas de la red"
            instance._entrada_fecha_desde = MagicMock()
            instance._entrada_fecha_desde.get.return_value = ""
            instance._entrada_fecha_hasta = MagicMock()
            instance._entrada_fecha_hasta.get.return_value = ""
            instance._tabs = MagicMock()
            instance._tabs.get.return_value = TAB_ATENCIONES
            instance._tarjetas_kpi = [
                (MagicMock(), MagicMock()),
                (MagicMock(), MagicMock()),
                (MagicMock(), MagicMock()),
            ]
            instance._tabla_r1_resumen = MagicMock()
            instance._tabla_r1_detalle = MagicMock()
            instance._tabla_r2_resumen = MagicMock()
            instance._tabla_r2_detalle = MagicMock()
            instance._tabla_r3_vacunas = MagicMock()
            instance._tabla_r3_tratamientos = MagicMock()
            instance._tabla_r4_clinica = MagicMock()
            instance._tabla_r4_estrategia = MagicMock()
            instance._tabla_r5_promedios = MagicMock()
            instance._tabla_r5_detalle = MagicMock()

        with patch("customtkinter.CTkFrame.__init__", return_value=None), \
             patch.object(VistaReportes, "_construir_ui", new=_mock_construir_ui):
            vista = VistaReportes(
                master=MagicMock(),
                servicio_reportes=srv_reportes,
                servicio_clinica=srv_clinica,
            )

            # Verificar que los 5 reportes hayan poblado sus estructuras exportables y KPIs
            for tab in (
                TAB_ATENCIONES,
                TAB_RECHAZOS,
                TAB_VACUNAS_TRAT,
                TAB_FACTURACION,
                TAB_TIEMPOS_SLA,
            ):
                self.assertIn(tab, vista._kpis_por_tab)
                self.assertEqual(len(vista._kpis_por_tab[tab]), 3)

            self.assertGreaterEqual(len(vista._datos_exportables_por_tab[TAB_ATENCIONES]), 1)
            self.assertGreaterEqual(len(vista._datos_exportables_por_tab[TAB_RECHAZOS]), 1)
            self.assertGreaterEqual(len(vista._datos_exportables_por_tab[TAB_FACTURACION]), 1)
            self.assertGreaterEqual(len(vista._datos_exportables_por_tab[TAB_TIEMPOS_SLA]), 1)

            # Validar formato de fecha inválido y fechas inexistentes en el calendario
            with self.assertRaises(ErrorDatosInvalidos):
                vista._validar_formato_fecha_opcional("2026/04/01", "fecha_desde")
            with self.assertRaises(ErrorDatosInvalidos):
                vista._validar_formato_fecha_opcional("2026-99-99", "fecha_desde")
            with self.assertRaises(ErrorDatosInvalidos):
                vista._validar_formato_fecha_opcional("2026-02-30", "fecha_hasta")

            # Validar que fecha_desde no puede ser mayor que fecha_hasta
            vista._entrada_fecha_desde.get.return_value = "2026-05-01"
            vista._entrada_fecha_hasta.get.return_value = "2026-04-01"
            with self.assertRaises(ErrorDatosInvalidos) as ctx_rango:
                vista.refrescar_datos()
            self.assertEqual(ctx_rango.exception.campo, "fecha_desde")
            self.assertIn("no puede ser posterior", ctx_rango.exception.mensaje.lower())

            # Restaurar fechas válidas
            vista._entrada_fecha_desde.get.return_value = ""
            vista._entrada_fecha_hasta.get.return_value = ""
            vista.refrescar_datos()

            # Verificar exportación de pestaña actual a CSV (ambas tablas generadas)
            with tempfile.TemporaryDirectory() as tmp_dir:
                ruta_csv = Path(tmp_dir) / "salida_reporte.csv"
                with patch(
                    "src.interfaz.vistas.vista_reportes.filedialog.asksaveasfilename",
                    return_value=str(ruta_csv),
                ), patch("src.interfaz.vistas.vista_reportes.mostrar_exito") as mock_exito:
                    vista._al_exportar_pestana_actual_csv()
                    mock_exito.assert_called_once()
                    self.assertTrue(ruta_csv.exists())
                    # La tabla secundaria con el resumen también debe haberse generado
                    ruta_resumen = Path(tmp_dir) / "salida_reporte_resumen_clinica.csv"
                    self.assertTrue(ruta_resumen.exists())
                    contenido = ruta_csv.read_text(encoding="utf-8-sig")
                    self.assertIn("Luna", contenido)

            # Verificar exportación del paquete completo (todos los 5 reportes)
            with tempfile.TemporaryDirectory() as tmp_dir_paquete:
                with patch(
                    "src.interfaz.vistas.vista_reportes.filedialog.askdirectory",
                    return_value=tmp_dir_paquete,
                ), patch("src.interfaz.vistas.vista_reportes.mostrar_exito") as mock_exito_todo:
                    vista._al_exportar_todos_los_reportes_csv()
                    mock_exito_todo.assert_called_once()
                    archivos_creados = list(Path(tmp_dir_paquete).glob("*.csv"))
                    self.assertGreaterEqual(len(archivos_creados), 5)


if __name__ == "__main__":
    unittest.main()
