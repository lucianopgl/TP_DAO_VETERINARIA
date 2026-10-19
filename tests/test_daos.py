"""
Pruebas de Integración y Persistencia: Capa DAO (Fase 3 - Paso 3)
================================================================

Verifica el funcionamiento integral de todos los Objetos de Acceso a Datos (DAO)
trabajando contra una base de datos SQLite en memoria:
    - ClienteDAO
    - MascotaDAO
    - ConsultaDAO
    - MuestraDAO (Trazabilidad e Inmutabilidad)
    - LogisticaDAO (Conservadoras, Precintos, Remitos, Envíos)
    - FacturacionDAO (Resultados de Laboratorio y Comprobantes Cabecera/Detalle)
"""

import unittest
from src.dominio.cliente import Cliente
from src.dominio.mascota import Mascota
from src.dominio.consulta_medica import ConsultaMedica, OrdenDerivacion
from src.dominio.historia_clinica import Tratamiento, VacunaAplicada
from src.dominio.muestra_biologica import MuestraBiologica
from src.dominio.logistica import EnvioLaboratorio, RemitoBiologico
from src.dominio.facturacion import ComprobanteAtencion, DetalleComprobante, ResultadoAnalisis
from src.dominio.excepciones import ErrorIntegridadDatos
from src.persistencia.conexion_bd import RUTA_BD_EN_MEMORIA, ConexionBD
from src.persistencia.inicializador_bd import inicializar_base_datos
from src.persistencia.cliente_dao import ClienteDAO
from src.persistencia.mascota_dao import MascotaDAO
from src.persistencia.consulta_dao import ConsultaDAO
from src.persistencia.muestra_dao import MuestraDAO
from src.persistencia.logistica_dao import LogisticaDAO
from src.persistencia.facturacion_dao import FacturacionDAO


class PruebaDAOsBase(unittest.TestCase):
    """Configura una base en memoria aislada para cada prueba unitaria."""

    def setUp(self) -> None:
        ConexionBD.reiniciar_instancia()
        self.conexion = inicializar_base_datos(ConexionBD.obtener_instancia(RUTA_BD_EN_MEMORIA))
        self.cliente_dao = ClienteDAO(self.conexion)
        self.mascota_dao = MascotaDAO(self.conexion)
        self.consulta_dao = ConsultaDAO(self.conexion)
        self.muestra_dao = MuestraDAO(self.conexion)
        self.logistica_dao = LogisticaDAO(self.conexion)
        self.facturacion_dao = FacturacionDAO(self.conexion)

    def tearDown(self) -> None:
        ConexionBD.reiniciar_instancia()

    def helper_crear_cliente_y_mascota(self) -> tuple[Cliente, Mascota]:
        cliente = Cliente(
            id=None,
            dni="32444555",
            nombre="Carlos",
            apellido="Gómez",
            telefono="351-4445566",
            email="carlos@ejemplo.com",
            direccion="Barrio Alberdi",
        )
        cliente_id = self.cliente_dao.crear(cliente)
        mascota = Mascota(
            id=None,
            nombre="Simba",
            especie_id=1,  # Canino
            edad=4,
            sexo="Macho",
            cliente_id=cliente_id,
            raza="Golden Retriever",
        )
        mascota_id = self.mascota_dao.crear(mascota, fecha_apertura_historia="2026-10-19")
        return cliente, mascota


class PruebaClienteDAO(PruebaDAOsBase):
    """Pruebas para ClienteDAO."""

    def test_crear_obtener_y_actualizar_cliente(self):
        cliente = Cliente(None, "28999111", "Marta", "Suárez", "351-9988776", "marta@mail.com")
        cid = self.cliente_dao.crear(cliente)
        self.assertIsNotNone(cid)

        recuperado = self.cliente_dao.obtener_por_id(cid)
        self.assertIsNotNone(recuperado)
        self.assertEqual(recuperado.nombre, "Marta")
        self.assertEqual(recuperado.apellido, "Suárez")

        # Actualizar
        recuperado.telefono = "351-1112233"
        self.cliente_dao.actualizar(recuperado)
        actualizado = self.cliente_dao.obtener_por_dni("28999111")
        self.assertEqual(actualizado.telefono, "351-1112233")

    def test_dni_duplicado_lanza_error_integridad(self):
        c1 = Cliente(None, "28999111", "Marta", "Suárez", "351-1")
        self.cliente_dao.crear(c1)
        c2 = Cliente(None, "28999111", "Otra", "Persona", "351-2")
        with self.assertRaises(ErrorIntegridadDatos) as ctx:
            self.cliente_dao.crear(c2)
        self.assertIn("DNI", ctx.exception.mensaje)


class PruebaMascotaDAO(PruebaDAOsBase):
    """Pruebas para MascotaDAO y Vacunas."""

    def test_crear_mascota_crea_historia_clinica_asociada(self):
        _, mascota = self.helper_crear_cliente_y_mascota()
        self.assertIsNotNone(mascota.id)

        # Verificar que la historia clínica existe
        fila_historia = self.conexion.consultar_uno(
            "SELECT id, mascota_id, fecha_apertura FROM historias_clinicas WHERE mascota_id = ?",
            (mascota.id,)
        )
        self.assertIsNotNone(fila_historia)
        self.assertEqual(fila_historia["mascota_id"], mascota.id)

    def test_registrar_y_listar_vacunas(self):
        _, mascota = self.helper_crear_cliente_y_mascota()
        vacuna = VacunaAplicada(
            id=None,
            mascota_id=mascota.id,
            vacuna_id=1,  # Antirrábica
            fecha_aplicacion="2026-10-19",
        )
        vid = self.mascota_dao.registrar_vacuna_aplicada(vacuna)
        self.assertIsNotNone(vid)

        vacunas = self.mascota_dao.listar_vacunas_de_mascota(mascota.id)
        self.assertEqual(len(vacunas), 1)
        self.assertEqual(vacunas[0].nombre_vacuna, "Antirrábica")
        self.assertTrue(vacunas[0].es_obligatoria)


class PruebaConsultaDAO(PruebaDAOsBase):
    """Pruebas para ConsultaDAO, Tratamientos y Órdenes."""

    def test_crear_consulta_con_tratamientos(self):
        _, mascota = self.helper_crear_cliente_y_mascota()
        t1 = Tratamiento(None, 0, "Amoxicilina 500mg", "AmoxiVet", "1 cada 12h", 7)
        consulta = ConsultaMedica(
            id=None,
            mascota_id=mascota.id,
            clinica_id=1,
            veterinario_id=1,
            fecha_hora_inicio="2026-10-19 10:00:00",
            duracion_minutos=30,
            motivo="Infección cutánea",
            diagnostico="Dermatitis bacteriana",
            costo_consulta=20000.0,
            tratamientos=[t1],
        )
        cid = self.consulta_dao.crear(consulta)
        self.assertIsNotNone(cid)

        recuperada = self.consulta_dao.obtener_por_id(cid)
        self.assertEqual(len(recuperada.tratamientos), 1)
        self.assertEqual(recuperada.tratamientos[0].medicamento, "AmoxiVet")

    def test_listar_por_veterinario_para_validacion_de_turnos(self):
        _, mascota = self.helper_crear_cliente_y_mascota()
        c1 = ConsultaMedica(
            id=None, mascota_id=mascota.id, clinica_id=1, veterinario_id=1,
            fecha_hora_inicio="2026-10-19 09:00:00", duracion_minutos=30, motivo="Consulta 1"
        )
        self.consulta_dao.crear(c1)

        consultas_dia = self.consulta_dao.listar_por_veterinario_y_fecha(1, "2026-10-19")
        self.assertEqual(len(consultas_dia), 1)
        self.assertEqual(consultas_dia[0].motivo, "Consulta 1")

    def test_crear_orden_derivacion(self):
        _, mascota = self.helper_crear_cliente_y_mascota()
        c1 = ConsultaMedica(
            id=None, mascota_id=mascota.id, clinica_id=1, veterinario_id=1,
            fecha_hora_inicio="2026-10-19 11:00:00", duracion_minutos=30, motivo="Control"
        )
        cid = self.consulta_dao.crear(c1)

        orden = OrdenDerivacion(
            id=None,
            consulta_id=cid,
            tipo_estudio_id=1,  # Hemograma
            indicaciones="Evaluar serie blanca y plaquetas",
            prioridad="Urgente",
            fecha_hora_emision="2026-10-19 11:20:00",
        )
        oid = self.consulta_dao.crear_orden_derivacion(orden)
        self.assertIsNotNone(oid)

        ordenes = self.consulta_dao.listar_ordenes_por_consulta(cid)
        self.assertEqual(len(ordenes), 1)
        self.assertEqual(ordenes[0].nombre_estudio, "Hemograma completo")
        self.assertEqual(ordenes[0].prioridad, "Urgente")


class PruebaMuestraDAO(PruebaDAOsBase):
    """Pruebas críticas de MuestraDAO: Trazabilidad Atómica e Inmutable."""

    def test_crear_muestra_inserta_en_muestras_e_historial_atomicamente(self):
        _, mascota = self.helper_crear_cliente_y_mascota()
        c1 = ConsultaMedica(
            None, mascota.id, 1, 1, "2026-10-19 10:00:00", motivo="Control prequirúrgico", duracion_minutos=30
        )
        cid = self.consulta_dao.crear(c1)
        orden = OrdenDerivacion(None, cid, 1, fecha_hora_emision="2026-10-19 10:15:00", indicaciones="Rutina", prioridad="Normal")
        oid = self.consulta_dao.crear_orden_derivacion(orden)

        muestra = MuestraBiologica(
            id=None,
            codigo_muestra="MUE-SANGRE-01",
            orden_id=oid,
            tipo_muestra_id=1,
            fecha_hora_extraccion="2026-10-19 10:20:00",
        )
        mid = self.muestra_dao.crear(muestra)
        self.assertIsNotNone(mid)

        recuperada = self.muestra_dao.obtener_por_id(mid)
        self.assertIsNotNone(recuperada)
        self.assertEqual(recuperada.estado_actual, "Extraida")
        self.assertEqual(len(recuperada.historial), 1)
        self.assertEqual(recuperada.historial[0].estado_nuevo, "Extraida")

    def test_actualizar_estado_es_atomico_y_mantiene_trazabilidad(self):
        _, mascota = self.helper_crear_cliente_y_mascota()
        c1 = ConsultaMedica(None, mascota.id, 1, 1, "2026-10-19 10:00:00", motivo="Extracción", duracion_minutos=30)
        cid = self.consulta_dao.crear(c1)
        orden = OrdenDerivacion(None, cid, 1, fecha_hora_emision="2026-10-19 10:10:00", indicaciones="Rutina", prioridad="Normal")
        oid = self.consulta_dao.crear_orden_derivacion(orden)
        muestra = MuestraBiologica(None, "MUE-TEST-02", oid, 1, "2026-10-19 10:15:00")
        mid = self.muestra_dao.crear(muestra)

        # Crear Remito previo (requerido para estado Empaquetada)
        remito = RemitoBiologico(None, "REM-0099", 1, 1, 1, "2026-10-19 10:20:00")
        rid = self.logistica_dao.crear_remito(remito)

        # Transición Extraída -> Empaquetada
        self.muestra_dao.actualizar_estado(
            muestra_id=mid,
            estado_anterior="Extraida",
            estado_nuevo="Empaquetada",
            fecha_hora="2026-10-19 10:25:00",
            observacion="Colocada en conservadora",
            remito_id=rid,
        )

        actualizada = self.muestra_dao.obtener_por_id(mid)
        self.assertEqual(actualizada.estado_actual, "Empaquetada")
        self.assertEqual(len(actualizada.historial), 2)
        self.assertEqual(actualizada.historial[1].estado_anterior, "Extraida")
        self.assertEqual(actualizada.historial[1].estado_nuevo, "Empaquetada")


class PruebaLogisticaYFacturacionDAO(PruebaDAOsBase):
    """Pruebas para LogisticaDAO y FacturacionDAO."""

    def test_circuito_logistico_conservadora_precinto_y_remito(self):
        # 1. Conservadoras
        conservadoras = self.logistica_dao.listar_conservadoras_disponibles()
        self.assertGreater(len(conservadoras), 0)
        c_id = conservadoras[0].id

        # 2. Precinto
        pid = self.logistica_dao.crear_precinto("PREC-998877", estado="Intacto")
        precinto = self.logistica_dao.obtener_precinto_por_id(pid)
        self.assertEqual(precinto.estado, "Intacto")

        # 3. Remito
        remito = RemitoBiologico(None, "REM-2026-001", 1, 1, c_id, "2026-10-19 10:00:00")
        rid = self.logistica_dao.crear_remito(remito)
        self.assertIsNotNone(rid)

        # 4. Asignar precinto y avanzar remito a Precintado
        self.logistica_dao.actualizar_estado_remito(
            rid, "EnPreparacion", "Precintado", "2026-10-19 10:30:00",
            observacion="Cerrado herméticamente", precinto_id=pid
        )
        remito_guardado = self.logistica_dao.obtener_remito_por_id(rid)
        self.assertEqual(remito_guardado.estado, "Precintado")
        self.assertEqual(remito_guardado.precinto_id, pid)

        # 5. Envío
        envio = EnvioLaboratorio(None, rid, 1, "2026-10-19 11:00:00")
        eid = self.logistica_dao.crear_envio(envio)
        self.assertIsNotNone(eid)

        self.logistica_dao.registrar_recepcion_envio(
            rid, "2026-10-19 12:30:00", "Recepción conforme con precinto intacto."
        )
        envio_rec = self.logistica_dao.obtener_envio_por_remito(rid)
        self.assertEqual(envio_rec.fecha_hora_recepcion, "2026-10-19 12:30:00")

    def test_facturacion_cabecera_y_detalles_desagregados(self):
        _, mascota = self.helper_crear_cliente_y_mascota()
        c1 = ConsultaMedica(None, mascota.id, 1, 1, "2026-10-19 10:00:00", motivo="Atención", duracion_minutos=30)
        cid = self.consulta_dao.crear(c1)

        d1 = DetalleComprobante(None, None, "Consulta", "Consulta médica veterinaria", 20000.0)
        d2 = DetalleComprobante(None, None, "Laboratorio", "Hemograma completo", 18000.0)
        d3 = DetalleComprobante(None, None, "Recargo", "Recargo Urgencia Lab (30%)", 5400.0)
        comprobante = ComprobanteAtencion(
            id=None,
            numero_comprobante="FAC-0001-0000001",
            consulta_id=cid,
            estrategia_tarifa="Tarifa Urgencia",
            monto_total=43400.0,
            fecha_hora_emision="2026-10-19 12:00:00",
            detalles=[d1, d2, d3],
        )
        fac_id = self.facturacion_dao.crear_comprobante(comprobante)
        self.assertIsNotNone(fac_id)

        recuperado = self.facturacion_dao.obtener_comprobante_por_consulta(cid)
        self.assertIsNotNone(recuperado)
        self.assertEqual(recuperado.monto_total, 43400.0)
        self.assertEqual(len(recuperado.detalles), 3)
        self.assertEqual(recuperado.detalles[2].tipo_concepto, "Recargo")


if __name__ == "__main__":
    unittest.main()
