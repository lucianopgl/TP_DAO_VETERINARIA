"""
Pruebas Unitarias e Integración: Mejoras de Auditoría (Fase 3 - Refinamiento)
=============================================================================

Verifica las 4 mejoras acordadas durante la auditoría:
    1. Ciclo de vida explícito del RemitoBiologico (despachar, recibir con control de precinto).
    2. Consulta y actualización de Historia Clínica (antecedentes y alergias) en MascotaDAO.
    3. Cálculo inteligente de vacunas obligatorias pendientes / vencidas en MascotaDAO.
    4. Consulta de auditoría de muestras rechazadas con trazabilidad de transporte en MuestraDAO.
"""

import unittest
from datetime import datetime
from src.dominio.cliente import Cliente
from src.dominio.mascota import Mascota
from src.dominio.historia_clinica import VacunaAplicada
from src.dominio.logistica import ConservadoraIsotermica, EnvioLaboratorio, PrecintoSanitario, RemitoBiologico
from src.dominio.muestra_biologica import MuestraBiologica
from src.dominio.consulta_medica import ConsultaMedica, OrdenDerivacion
from src.dominio.excepciones import ErrorValidacionNegocio
from src.persistencia.conexion_bd import RUTA_BD_EN_MEMORIA, ConexionBD
from src.persistencia.inicializador_bd import inicializar_base_datos
from src.persistencia.cliente_dao import ClienteDAO
from src.persistencia.mascota_dao import MascotaDAO
from src.persistencia.consulta_dao import ConsultaDAO
from src.persistencia.muestra_dao import MuestraDAO
from src.persistencia.logistica_dao import LogisticaDAO


class PruebaMejorasAuditoria(unittest.TestCase):
    """Batería de pruebas para las funcionalidades incorporadas en la auditoría."""

    def setUp(self) -> None:
        ConexionBD.reiniciar_instancia()
        self.conexion = inicializar_base_datos(ConexionBD.obtener_instancia(RUTA_BD_EN_MEMORIA))
        self.cliente_dao = ClienteDAO(self.conexion)
        self.mascota_dao = MascotaDAO(self.conexion)
        self.consulta_dao = ConsultaDAO(self.conexion)
        self.muestra_dao = MuestraDAO(self.conexion)
        self.logistica_dao = LogisticaDAO(self.conexion)

    def tearDown(self) -> None:
        ConexionBD.reiniciar_instancia()

    # ----------------------------------------------------------------------------------
    # 1. Ciclo de Vida de RemitoBiologico
    # ----------------------------------------------------------------------------------

    def test_ciclo_de_vida_remito_exitoso_y_transiciones_invalidas(self):
        muestra = MuestraBiologica(1, "M-01", 1, 1, "2026-10-19 10:00:00")
        precinto = PrecintoSanitario(1, "PREC-001", "Intacto")
        remito = RemitoBiologico(
            id=1,
            numero_remito="REM-100",
            clinica_origen_id=1,
            laboratorio_destino_id=1,
            conservadora_id=1,
            fecha_hora_creacion="2026-10-19 10:00:00",
            muestras=[muestra],
        )
        self.assertEqual(remito.estado, "EnPreparacion")

        # No se puede despachar sin estar precintado
        with self.assertRaises(ErrorValidacionNegocio):
            remito.despachar()

        # Precintar
        remito.precintar(precinto)
        self.assertEqual(remito.estado, "Precintado")

        # Despachar
        remito.despachar()
        self.assertEqual(remito.estado, "EnTransito")

        # Recibir con precinto intacto
        remito.recibir("Intacto")
        self.assertEqual(remito.estado, "Recibido")

    def test_remito_recibido_con_precinto_roto_pasa_a_rechazado(self):
        muestra = MuestraBiologica(1, "M-01", 1, 1, "2026-10-19 10:00:00")
        precinto = PrecintoSanitario(1, "PREC-002", "Intacto")
        remito = RemitoBiologico(
            id=2, numero_remito="REM-200", clinica_origen_id=1,
            laboratorio_destino_id=1, conservadora_id=1,
            fecha_hora_creacion="2026-10-19 10:00:00", muestras=[muestra]
        )
        remito.precintar(precinto)
        remito.despachar()

        # Al recibir con precinto roto
        remito.recibir("Roto")
        self.assertEqual(remito.estado, "Rechazado")

    # ----------------------------------------------------------------------------------
    # 2. Historia Clínica en MascotaDAO
    # ----------------------------------------------------------------------------------

    def test_obtener_y_actualizar_historia_clinica(self):
        cid = self.cliente_dao.crear(Cliente(None, "30111222", "Juan", "Pérez", "351-1111111"))
        mid = self.mascota_dao.crear(Mascota(None, "Bobby", 1, 3, "Macho", cid))

        historia = self.mascota_dao.obtener_historia_clinica(mid)
        self.assertIsNotNone(historia)
        self.assertIsNone(historia.antecedentes)

        # Actualizar antecedentes y alergias
        self.mascota_dao.actualizar_historia_clinica(
            mid, antecedentes="Fractura de fémur en 2025", alergias="Alérgico a cefalexina"
        )
        actualizada = self.mascota_dao.obtener_historia_clinica(mid)
        self.assertEqual(actualizada.antecedentes, "Fractura de fémur en 2025")
        self.assertEqual(actualizada.alergias, "Alérgico a cefalexina")

    # ----------------------------------------------------------------------------------
    # 3. Cálculo de Vacunas Pendientes
    # ----------------------------------------------------------------------------------

    def test_calculo_de_vacunas_pendientes_nunca_aplicada_y_vencida(self):
        cid = self.cliente_dao.crear(Cliente(None, "30111222", "Juan", "Pérez", "351-1111111"))
        # Perro (especie 1: Canino tiene obligatorias Antirrábica [id 1] y Séxtuple [id 2])
        mid = self.mascota_dao.crear(Mascota(None, "Bobby", 1, 3, "Macho", cid))

        # Al inicio, ninguna está aplicada -> ambas pendientes
        pendientes = self.mascota_dao.obtener_vacunas_pendientes(mid, fecha_referencia="2026-10-19")
        self.assertEqual(len(pendientes), 2)
        motivos = [p["motivo_pendiente"] for p in pendientes]
        self.assertTrue(all(m == "Nunca aplicada" for m in motivos))

        # Le aplicamos Antirrábica al día de hoy
        self.mascota_dao.registrar_vacuna_aplicada(
            VacunaAplicada(None, mid, 1, fecha_aplicacion="2026-10-19")
        )
        # Y le aplicamos Séxtuple con fecha de hace 2 años (vencida)
        self.mascota_dao.registrar_vacuna_aplicada(
            VacunaAplicada(None, mid, 2, fecha_aplicacion="2024-05-10")
        )

        pendientes_despues = self.mascota_dao.obtener_vacunas_pendientes(mid, fecha_referencia="2026-10-19")
        # Antirrábica está al día -> sólo Séxtuple debe figurar como pendiente (vencida)
        self.assertEqual(len(pendientes_despues), 1)
        self.assertEqual(pendientes_despues[0]["nombre_vacuna"], "Séxtuple canina")
        self.assertIn("vencido", pendientes_despues[0]["motivo_pendiente"].lower())

    # ----------------------------------------------------------------------------------
    # 4. Trazabilidad Completa de Muestras Rechazadas
    # ----------------------------------------------------------------------------------

    def test_consulta_de_muestras_rechazadas_con_transporte(self):
        # Armar circuito
        cid = self.cliente_dao.crear(Cliente(None, "30111222", "Juan", "Pérez", "351-1111111"))
        mid = self.mascota_dao.crear(Mascota(None, "Bobby", 1, 3, "Macho", cid))
        cons_id = self.consulta_dao.crear(
            ConsultaMedica(None, mid, 1, 1, "2026-10-19 10:00:00", motivo="Extracción")
        )
        oid = self.consulta_dao.crear_orden_derivacion(
            OrdenDerivacion(None, cons_id, 1, fecha_hora_emision="2026-10-19 10:15:00")
        )
        muestra_id = self.muestra_dao.crear(
            MuestraBiologica(None, "MUE-RECH-99", oid, 1, "2026-10-19 10:20:00")
        )
        pid = self.logistica_dao.crear_precinto("PREC-ROTO-01", estado="Roto")
        rid = self.logistica_dao.crear_remito(
            RemitoBiologico(None, "REM-RECH-01", 1, 1, 1, "2026-10-19 10:30:00", precinto_id=pid)
        )
        self.logistica_dao.crear_envio(
            EnvioLaboratorio(None, rid, 1, "2026-10-19 11:00:00", "2026-10-19 12:30:00", "Precinto roto al arribo")
        )

        # Transición de la muestra a Rechazada
        self.muestra_dao.actualizar_estado(
            muestra_id=muestra_id,
            estado_anterior="EnTransito",
            estado_nuevo="Rechazada",
            fecha_hora="2026-10-19 12:30:00",
            observacion="Precinto sanitario violentado en tránsito",
            motivo_rechazo="Precinto roto",
            remito_id=rid,
        )

        # Consultar el reporte
        rechazadas = self.muestra_dao.listar_muestras_rechazadas_con_transporte()
        self.assertGreaterEqual(len(rechazadas), 1)
        item = next(r for r in rechazadas if r["codigo_muestra"] == "MUE-RECH-99")
        self.assertEqual(item["numero_remito"], "REM-RECH-01")
        self.assertEqual(item["precinto_serie"], "PREC-ROTO-01")
        self.assertEqual(item["precinto_estado"], "Roto")
        self.assertIsNotNone(item["transportista_nombre"])
        self.assertIn("Clínica Veterinaria Centro", item["clinica_origen"])


if __name__ == "__main__":
    unittest.main()
