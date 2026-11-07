"""
Pruebas Unitarias y de Integración: Interfaz Gráfica — Etapa 3
=============================================================

Verifica:
    1. Regla arquitectónica de capas (AST): Prohibido importar `sqlite3` o
       acoplarse a `src.persistencia` desde `vista_logistica.py` o `vista_laboratorio.py`.
    2. Proceso 4, 5 y 6 en `VistaLogistica`: Empaquetado, Despacho, Recepción con
       verificación de precinto sanitario y recorrido con Patrón ITERATOR
       (`IteradorMuestras` e `IteradorMuestrasFiltradas`).
    3. Proceso 7 en `VistaLaboratorio`:
       - Parte A: Carga de resultados bioquímicos sobre muestras 'Recibida' y bloqueo
         polimórfico de muestras no viables (Patrón STATE).
       - Parte B: Selección e inyección polimórfica de objetos `EstrategiaFacturacion`
         (Patrón STRATEGY: `TarifaEstandar`, `TarifaUrgenciaLaboratorio`, `TarifaConvenioRed`).
    4. Integración extremo a extremo con base de datos en memoria y Patrón OBSERVER.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.dominio.logistica import ConservadoraIsotermica
from src.interfaz.app import formatear_evento_notificacion
from src.interfaz.vistas.vista_laboratorio import DESCRIPCION_ESTRATEGIAS, VistaLaboratorio
from src.interfaz.vistas.vista_logistica import VistaLogistica
from src.patrones.estrategia_facturacion import (
    MAPA_ESTRATEGIAS,
    TarifaConvenioRed,
    TarifaEstandar,
    TarifaUrgenciaLaboratorio,
)
from src.patrones.observador_eventos import SujetoEventos
from src.persistencia.conexion_bd import RUTA_BD_EN_MEMORIA, ConexionBD
from src.persistencia.inicializador_bd import inicializar_base_datos
from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_laboratorio import ServicioLaboratorio
from src.servicios.servicio_logistica import ServicioLogistica

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


class PruebaInterfazEtapa3(unittest.TestCase):
    """Pruebas de arquitectura, patrones GoF y funcionamiento para las vistas de la Etapa 3."""

    def test_regla_arquitectonica_vistas_etapa3_sin_sqlite_ni_daos(self) -> None:
        """Ningún archivo de la Etapa 3 debe importar sqlite3 ni persistencia."""
        archivos = [
            RAIZ_PROYECTO / "src" / "interfaz" / "vistas" / "vista_logistica.py",
            RAIZ_PROYECTO / "src" / "interfaz" / "vistas" / "vista_laboratorio.py",
        ]
        for archivo in archivos:
            self.assertTrue(archivo.exists(), f"El archivo {archivo} no existe.")
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
                        f"La vista no debe acoplarse a src.persistencia ({archivo})",
                    )

    def test_descripciones_estrategias_facturacion_completas(self) -> None:
        """Verifica que las 3 estrategias del Patrón Strategy tengan descripción clara."""
        estrategias_esperadas = ["Tarifa Estándar", "Tarifa Urgencia", "Tarifa Convenio Red"]
        for est in estrategias_esperadas:
            self.assertIn(est, DESCRIPCION_ESTRATEGIAS)
            self.assertIn(est, MAPA_ESTRATEGIAS)
            self.assertTrue(len(DESCRIPCION_ESTRATEGIAS[est]) > 10)

    def test_formateo_eventos_notificacion_laboratorio_y_logistica(self) -> None:
        """Verifica el formateo semántico de los eventos generados en Procesos 4 a 7."""
        # Despacho con clave real de ServicioLogistica ('fecha_hora')
        msg_desp, color_desp = formatear_evento_notificacion(
            "REMITO_DESPACHADO",
            {"numero_remito": "REM-100", "fecha_hora": "2026-03-01 10:00:00"},
        )
        self.assertIn("REM-100", msg_desp)
        self.assertIn("2026-03-01 10:00:00", msg_desp)
        self.assertEqual(color_desp, "#1D4ED8")

        # Rechazo con clave real de ServicioLogistica ('codigos_muestras')
        msg_rech, color_rech = formatear_evento_notificacion(
            "MUESTRAS_RECHAZADAS_EN_RECEPCION",
            {
                "numero_remito": "REM-101",
                "estado_precinto": "Roto",
                "codigos_muestras": ["MUE-A1", "MUE-A2"],
            },
        )
        self.assertIn("REM-101", msg_rech)
        self.assertIn("MUE-A1, MUE-A2", msg_rech)
        self.assertEqual(color_rech, "#DC2626")

        # Resultado de análisis listo
        msg_res, color_res = formatear_evento_notificacion(
            "RESULTADO_ANALISIS_LISTO",
            {"codigo_muestra": "MUE-999", "conclusion": "Análisis normal sin anomalías."},
        )
        self.assertIn("MUE-999", msg_res)
        self.assertIn("Análisis normal", msg_res)
        self.assertEqual(color_res, "#0F766E")

    def test_integracion_real_vistas_etapa3_con_patrones_gof(self) -> None:
        """
        Verifica con base de datos en memoria que VistaLogistica y VistaLaboratorio
        hidraten datos reales e invoquen los patrones Iterator, State, Strategy y Observer.
        """
        ConexionBD.reiniciar_instancia()
        conexion = inicializar_base_datos(ConexionBD.obtener_instancia(RUTA_BD_EN_MEMORIA))
        eventos = SujetoEventos()
        srv_clinica = ServicioClinica(conexion)
        srv_logistica = ServicioLogistica(conexion, eventos)
        srv_lab = ServicioLaboratorio(conexion, eventos)

        # Crear datos de negocio para el flujo completo
        cli = srv_clinica.registrar_cliente("30111222", "Ana", "Gómez", "3514445566")
        mascota = srv_clinica.registrar_mascota(
            nombre="Toby",
            especie_id=1,
            edad=3,
            sexo="Macho",
            cliente_id=cli.id,
            raza="Beagle",
        )
        consulta, _ = srv_clinica.registrar_consulta_medica(
            mascota_id=mascota.id,
            clinica_id=1,
            veterinario_id=1,
            fecha_hora_inicio="2026-03-10 09:00:00",
            motivo="Chequeo general",
            costo_consulta=8000.0,
        )
        orden = srv_clinica.emitir_orden_derivacion(
            consulta_id=consulta.id,
            tipo_estudio_id=1,
            indicaciones="Hemograma completo",
            prioridad="Urgente",
        )
        srv_clinica.extraer_muestra_biologica(
            orden_id=orden.id,
            codigo_muestra="MUE-INT-01",
            tipo_muestra_id=1,
        )

        def _mock_construir_ui_log(instance: VistaLogistica) -> None:
            instance._combo_p4_clinica = MagicMock()
            instance._combo_p4_clinica.get.return_value = "Clínica Veterinaria Norte"
            instance._combo_p4_lab = MagicMock()
            instance._combo_p4_conservadora = MagicMock()
            instance._combo_transportista = MagicMock()
            instance._entrada_p4_remito = MagicMock()
            instance._entrada_p4_remito.get.return_value = ""
            instance._entrada_p4_precinto = MagicMock()
            instance._entrada_p4_precinto.get.return_value = ""
            instance._tabla_remitos = MagicMock()
            instance._tabla_muestras_extraidas = MagicMock()
            instance._tabla_muestras_remito = MagicMock()
            instance._etiqueta_contador_remitos = MagicMock()
            instance._etiqueta_muestras_disponibles = MagicMock()
            instance._etiqueta_detalle_remito = MagicMock()
            instance._chk_solo_viables_iterator = MagicMock()
            instance._chk_solo_viables_iterator.get.return_value = False

        def _mock_construir_ui_lab(instance: VistaLaboratorio) -> None:
            instance._combo_bioquimico = MagicMock()
            instance._combo_consulta = MagicMock()
            instance._combo_estrategia = MagicMock()
            instance._combo_estrategia.get.return_value = "Tarifa Urgencia"
            instance._tabla_recibidas = MagicMock()
            instance._tabla_recibidas.obtener_todas_las_filas.return_value = []
            instance._tabla_analizadas = MagicMock()
            instance._tabla_comprobantes = MagicMock()
            instance._tabla_comprobantes.obtener_todas_las_filas.return_value = []
            instance._tabla_detalles = MagicMock()
            instance._etiqueta_resumen = MagicMock()
            instance._lbl_cant_recibidas = MagicMock()
            instance._lbl_cant_analizadas = MagicMock()
            instance._lbl_cant_comprobantes = MagicMock()
            instance._lbl_info_consulta_titulo = MagicMock()
            instance._lbl_info_consulta_detalle = MagicMock()
            instance._lbl_info_muestra_titulo = MagicMock()
            instance._lbl_info_muestra_detalle = MagicMock()
            instance._txt_numero_comprobante = MagicMock()
            instance._txt_fecha_emision = MagicMock()
            instance._txt_costo_analisis = MagicMock()
            instance._txt_fecha_analisis = MagicMock()
            instance._chk_incluir_bloqueadas = MagicMock()
            instance._chk_incluir_bloqueadas.get.return_value = True

        with patch("customtkinter.CTkFrame.__init__", return_value=None), \
             patch.object(VistaLogistica, "_construir_ui", new=_mock_construir_ui_log), \
             patch.object(VistaLaboratorio, "_construir_ui", new=_mock_construir_ui_lab):
            vista_log = VistaLogistica(
                master=MagicMock(),
                servicio_logistica=srv_logistica,
                servicio_clinica=srv_clinica,
            )
            vista_lab = VistaLaboratorio(
                master=MagicMock(),
                servicio_laboratorio=srv_lab,
                servicio_clinica=srv_clinica,
            )

            # 1. Verificar instanciación polimórfica de Strategy en VistaLaboratorio
            estrategia_urg = vista_lab._obtener_estrategia_seleccionada()
            self.assertIsInstance(estrategia_urg, TarifaUrgenciaLaboratorio)

            vista_lab._combo_estrategia.get.return_value = "Tarifa Convenio Red"
            estrategia_conv = vista_lab._obtener_estrategia_seleccionada()
            self.assertIsInstance(estrategia_conv, TarifaConvenioRed)

            vista_lab._combo_estrategia.get.return_value = "Tarifa Estándar"
            estrategia_est = vista_lab._obtener_estrategia_seleccionada()
            self.assertIsInstance(estrategia_est, TarifaEstandar)

            # 2. Verificar que la muestra precargada (id=1, estado 'Extraida') aparece al activar auditoría State
            self.assertIn(1, vista_lab._muestras_recibidas_por_id)
            vista_lab._al_seleccionar_muestra_recibida("1")
            self.assertEqual(vista_lab._muestra_seleccionada_id, 1)

            # 2.5. Verificar que la tabla de muestras extraídas pendientes visualiza el estado 'Extraida'
            vista_log._recargar_muestras_extraidas_pendientes()
            vista_log._tabla_muestras_extraidas.cargar_filas.assert_called()
            filas_extraidas = vista_log._tabla_muestras_extraidas.cargar_filas.call_args[0][0]
            self.assertEqual(len(filas_extraidas), 1)
            self.assertEqual(filas_extraidas[0][1][4], "Extraida")

            # 3. Empaquetar la muestra #1 y verificar recorrido con Patrón Iterator en VistaLogistica
            remito = srv_logistica.empaquetar_muestras(
                numero_remito="REM-TEST-01",
                clinica_origen_id=1,
                laboratorio_destino_id=1,
                conservadora_id=1,
                numero_serie_precinto="PREC-TEST-01",
                muestras_ids=[1],
            )
            vista_log._cargar_muestras_del_remito(remito)
            vista_log._tabla_muestras_remito.cargar_filas.assert_called()
            filas_todas = vista_log._tabla_muestras_remito.cargar_filas.call_args[0][0]
            self.assertEqual(len(filas_todas), 1)

            # Activar filtro de solo viables (IteradorMuestrasFiltradas)
            vista_log._chk_solo_viables_iterator.get.return_value = True
            vista_log._al_alternar_filtro_viables_iterator()
            filas_viables = vista_log._tabla_muestras_remito.cargar_filas.call_args[0][0]
            self.assertEqual(len(filas_viables), 1)


if __name__ == "__main__":
    unittest.main()
