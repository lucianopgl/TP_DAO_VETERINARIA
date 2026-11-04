"""
Pruebas del Servicio de Reportes (Fase 4 - Paso 4.2)
====================================================

Verifica la exactitud estadística, el filtrado y la exportación CSV de los
5 reportes gerenciales y sanitarios no triviales:
    1. Atenciones clínicas y derivaciones realizadas.
    2. Muestras biológicas rechazadas por fallas en el transporte.
    3. Tratamientos aplicados y vacunas pendientes.
    4. Facturación desglosada por clínica y servicios de laboratorio.
    5. Tiempo promedio de tránsito y procesamiento de muestras.
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.dominio.historia_clinica import Tratamiento
from src.patrones.estrategia_facturacion import TarifaUrgenciaLaboratorio
from src.persistencia.conexion_bd import RUTA_BD_EN_MEMORIA, ConexionBD
from src.persistencia.inicializador_bd import inicializar_base_datos
from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_laboratorio import ServicioLaboratorio
from src.servicios.servicio_logistica import ServicioLogistica
from src.servicios.servicio_reportes import ServicioReportes


class PruebaServicioReportes(unittest.TestCase):
    """Batería de pruebas para los 5 reportes del sistema y exportación CSV."""

    def setUp(self) -> None:
        ConexionBD.reiniciar_instancia()
        self.conexion = inicializar_base_datos(
            ConexionBD.obtener_instancia(RUTA_BD_EN_MEMORIA)
        )
        self.srv_clinica = ServicioClinica(self.conexion)
        self.srv_logistica = ServicioLogistica(self.conexion)
        self.srv_laboratorio = ServicioLaboratorio(self.conexion)
        self.srv_reportes = ServicioReportes(self.conexion)

        # Poblar escenario completo para alimentar los 5 reportes
        self._poblar_escenario_pruebas()

    def tearDown(self) -> None:
        ConexionBD.reiniciar_instancia()

    def _poblar_escenario_pruebas(self) -> None:
        """
        Construye un escenario controlado con:
            - 1 cliente y 2 mascotas (1 perro con vacunas al día; 1 gato sin vacunas).
            - 1 consulta en Clínica 1 (Centro) con 1 tratamiento y 2 derivaciones.
            - 1 remito con precinto Intacto (cuya muestra se analiza en 2h de tránsito y 3h de lab).
            - 1 remito con precinto Roto (cuya muestra queda Rechazada).
            - 1 comprobante emitido con Tarifa Urgencia (+30% sobre lab).
        """
        self.cliente = self.srv_clinica.registrar_cliente(
            dni="31222333",
            nombre="Laura",
            apellido="Méndez",
            telefono="3515551122",
            email="laura@mail.com",
        )
        # Mascota 1: Canino (requiere Antirrábica [1] y Séxtuple [2])
        self.perro = self.srv_clinica.registrar_mascota(
            nombre="Thor",
            especie_id=1,
            edad=4,
            sexo="Macho",
            cliente_id=self.cliente.id,
            raza="Ovejero",
            fecha_apertura_historia="2026-10-01",
        )
        # Aplicamos ambas vacunas a Thor para dejar su esquema al día
        self.srv_clinica.aplicar_vacuna(
            mascota_id=self.perro.id, vacuna_id=1, fecha_aplicacion="2026-10-01"
        )
        self.srv_clinica.aplicar_vacuna(
            mascota_id=self.perro.id, vacuna_id=2, fecha_aplicacion="2026-10-01"
        )

        # Mascota 2: Felino (requiere Antirrábica felina [4] y Triple felina [5] -> las dejamos pendientes)
        self.gato = self.srv_clinica.registrar_mascota(
            nombre="Luna",
            especie_id=2,
            edad=2,
            sexo="Hembra",
            cliente_id=self.cliente.id,
            raza="Siamés",
            fecha_apertura_historia="2026-10-01",
        )

        # Consulta 1 para Thor con 1 tratamiento y 2 órdenes (1 Urgente, 1 Normal)
        t1 = Tratamiento(None, 0, "Analgésico antiinflamatorio", "Meloxicam", "1 comp/24h", 5)
        self.consulta_1, _ = self.srv_clinica.registrar_consulta_medica(
            mascota_id=self.perro.id,
            clinica_id=1,
            veterinario_id=1,
            fecha_hora_inicio="2026-10-19 09:00:00",
            duracion_minutos=30,
            motivo="Chequeo general y dolor articular",
            diagnostico="Artrosis leve",
            costo_consulta=20000.0,
            tratamientos=[t1],
            exigir_vacunas_al_dia=True,
        )

        orden_1 = self.srv_clinica.emitir_orden_derivacion(
            consulta_id=self.consulta_1.id,
            tipo_estudio_id=1,
            indicaciones="Hemograma control",
            prioridad="Urgente",
            fecha_hora_emision="2026-10-19 09:15:00",
        )
        orden_2 = self.srv_clinica.emitir_orden_derivacion(
            consulta_id=self.consulta_1.id,
            tipo_estudio_id=2,
            indicaciones="Perfil renal",
            prioridad="Normal",
            fecha_hora_emision="2026-10-19 09:20:00",
        )

        # Muestra 1 (extraída 10:00, despachada 11:00 [1h espera], recibida 13:00 [2h tránsito], analizada 16:00 [3h lab])
        self.muestra_ok = self.srv_clinica.extraer_muestra_biologica(
            orden_id=orden_1.id,
            codigo_muestra="MUE-REP-OK",
            tipo_muestra_id=1,
            fecha_hora_extraccion="2026-10-19 10:00:00",
        )
        remito_ok = self.srv_logistica.empaquetar_muestras(
            numero_remito="REM-REP-01",
            clinica_origen_id=1,
            laboratorio_destino_id=1,
            conservadora_id=1,
            numero_serie_precinto="PREC-REP-OK",
            muestras_ids=[self.muestra_ok.id],
            fecha_hora="2026-10-19 10:30:00",
        )
        self.srv_logistica.despachar_remito(
            remito_id=remito_ok.id,
            transportista_id=1,
            fecha_hora_despacho="2026-10-19 11:00:00",
        )
        self.srv_logistica.recibir_remito_en_laboratorio(
            remito_id=remito_ok.id,
            estado_precinto="Intacto",
            fecha_hora_recepcion="2026-10-19 13:00:00",
        )
        self.srv_laboratorio.registrar_resultado_analisis(
            muestra_id=self.muestra_ok.id,
            profesional_laboratorio_id=1,
            valores_medidos="Hematocrito 45%",
            conclusion="Normal",
            costo_analisis=18000.0,
            fecha_hora_analisis="2026-10-19 16:00:00",
        )

        # Muestra 2 (rechazada por precinto Roto)
        self.muestra_rech = self.srv_clinica.extraer_muestra_biologica(
            orden_id=orden_2.id,
            codigo_muestra="MUE-REP-RECH",
            tipo_muestra_id=1,
            fecha_hora_extraccion="2026-10-19 10:05:00",
        )
        remito_rech = self.srv_logistica.empaquetar_muestras(
            numero_remito="REM-REP-02",
            clinica_origen_id=1,
            laboratorio_destino_id=1,
            conservadora_id=2,
            numero_serie_precinto="PREC-REP-ROTO",
            muestras_ids=[self.muestra_rech.id],
            fecha_hora="2026-10-19 10:40:00",
        )
        self.srv_logistica.despachar_remito(
            remito_id=remito_rech.id,
            transportista_id=1,
            fecha_hora_despacho="2026-10-19 11:00:00",
        )
        self.srv_logistica.recibir_remito_en_laboratorio(
            remito_id=remito_rech.id,
            estado_precinto="Roto",
            fecha_hora_recepcion="2026-10-19 12:30:00",
            observaciones="Faja de seguridad cortada",
        )

        # Facturación de la consulta 1 con Tarifa Urgencia (+30% sobre lab)
        self.srv_laboratorio.emitir_comprobante_atencion(
            consulta_id=self.consulta_1.id,
            numero_comprobante="FAC-REP-0001",
            estrategia=TarifaUrgenciaLaboratorio(porcentaje_recargo=30.0),
            fecha_hora_emision="2026-10-19 17:00:00",
        )

    def test_reporte_1_atenciones_y_derivaciones(self):
        rep = self.srv_reportes.reporte_atenciones_y_derivaciones(
            fecha_desde="2026-10-01", fecha_hasta="2026-10-31", clinica_id=1
        )
        self.assertEqual(len(rep["resumen_por_clinica"]), 1)
        resumen = rep["resumen_por_clinica"][0]
        self.assertEqual(resumen["total_consultas"], 1)
        self.assertEqual(resumen["total_derivaciones"], 2)
        self.assertEqual(resumen["derivaciones_urgentes"], 1)
        self.assertEqual(resumen["total_muestras_extraidas"], 2)

        self.assertEqual(len(rep["detalle_atenciones"]), 1)
        det = rep["detalle_atenciones"][0]
        self.assertEqual(det["mascota_nombre"], "Thor")
        self.assertEqual(det["cantidad_ordenes"], 2)

    def test_reporte_2_muestras_rechazadas_transporte(self):
        rep = self.srv_reportes.reporte_muestras_rechazadas_transporte()
        self.assertEqual(rep["total_rechazadas"], 1)
        self.assertEqual(rep["rechazos_por_estado_precinto"].get("Roto"), 1)
        self.assertEqual(rep["detalle_muestras"][0]["codigo_muestra"], "MUE-REP-RECH")
        self.assertEqual(rep["detalle_muestras"][0]["precinto_serie"], "PREC-REP-ROTO")

    def test_reporte_3_tratamientos_y_vacunas_pendientes(self):
        rep = self.srv_reportes.reporte_tratamientos_y_vacunas_pendientes(
            fecha_referencia="2026-10-19"
        )
        self.assertEqual(rep["total_tratamientos"], 1)
        self.assertEqual(rep["tratamientos_aplicados"][0]["medicamento"], "Meloxicam")

        # Luna (Gato) no tiene ninguna vacuna aplicada -> 2 obligatorias pendientes (Antirrábica felina y Triple felina)
        self.assertEqual(rep["total_mascotas_con_vacunas_pendientes"], 1)
        self.assertEqual(rep["total_vacunas_pendientes"], 2)
        nombres_mascota = {v["mascota_nombre"] for v in rep["vacunas_pendientes"]}
        self.assertEqual(nombres_mascota, {"Luna"})

    def test_reporte_4_facturacion_desglosada(self):
        rep = self.srv_reportes.reporte_facturacion_desglosada()
        # Consulta: 20.000 + Lab (solo la analizada): 18.000 + Recargo 30% (5.400) = 43.400
        self.assertEqual(rep["total_general_facturado"], 43400.0)
        self.assertEqual(rep["total_servicios_laboratorio"], 18000.0)
        self.assertEqual(rep["total_servicios_clinica"], 20000.0)
        self.assertEqual(len(rep["desglose_por_clinica"]), 1)
        self.assertEqual(rep["desglose_por_clinica"][0]["total_recargos"], 5400.0)
        self.assertEqual(len(rep["desglose_por_estrategia"]), 1)

    def test_reporte_5_tiempos_transito_y_procesamiento(self):
        rep = self.srv_reportes.reporte_tiempos_transito_y_procesamiento()
        # Muestra 1: Tránsito 2.0h (11:00 a 13:00), Lab 3.0h (13:00 a 16:00), Ciclo Total 6.0h (10:00 a 16:00)
        # Muestra 2: Tránsito 1.5h (11:00 a 12:30), sin análisis (Rechazada)
        # Promedio tránsito = (2.0 + 1.5) / 2 = 1.75h
        self.assertAlmostEqual(rep["promedio_global_horas_transito"], 1.75, places=2)
        self.assertAlmostEqual(rep["promedio_global_horas_procesamiento_lab"], 3.0, places=2)
        self.assertAlmostEqual(rep["promedio_global_horas_ciclo_total"], 6.0, places=2)
        self.assertEqual(rep["cantidad_muestras_en_transito_o_recibidas"], 2)

    def test_exportar_reporte_a_csv(self):
        rep = self.srv_reportes.reporte_muestras_rechazadas_transporte()
        with tempfile.TemporaryDirectory() as tmp_dir:
            ruta_csv = Path(tmp_dir) / "muestras_rechazadas.csv"
            archivo = ServicioReportes.exportar_a_csv(
                rep["detalle_muestras"], ruta_csv
            )
            self.assertTrue(archivo.exists())
            with archivo.open(mode="r", encoding="utf-8-sig") as f:
                lector = list(csv.DictReader(f))
            self.assertEqual(len(lector), 1)
            self.assertEqual(lector[0]["codigo_muestra"], "MUE-REP-RECH")


if __name__ == "__main__":
    unittest.main()
