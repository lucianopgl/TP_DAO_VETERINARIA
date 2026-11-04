"""
Pruebas de Integración: Capa de Servicios de Negocio (Fase 4 - Paso 4.1)
========================================================================

Verifica de punta a punta los 7 Procesos de Negocio Obligatorios y todas las
Validaciones de Negocio orquestadas por:
    - ServicioClinica (Procesos 1, 2 y 3)
    - ServicioLogistica (Procesos 4, 5 y 6)
    - ServicioLaboratorio (Proceso 7)
"""

import unittest

from src.dominio.excepciones import (
    ErrorCapacidadConservadoraExcedida,
    ErrorClinicaNoCoincide,
    ErrorMascotaSinResponsable,
    ErrorSuperposicionTurno,
    ErrorTransicionEstadoInvalida,
    ErrorVacunaObligatoriaFaltante,
)
from src.dominio.historia_clinica import Tratamiento
from src.patrones.estrategia_facturacion import (
    TarifaConvenioRed,
    TarifaUrgenciaLaboratorio,
)
from src.patrones.observador_eventos import ObservadorAuditoria, SujetoEventos
from src.persistencia.conexion_bd import RUTA_BD_EN_MEMORIA, ConexionBD
from src.persistencia.inicializador_bd import inicializar_base_datos
from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_laboratorio import ServicioLaboratorio
from src.servicios.servicio_logistica import ServicioLogistica


class PruebaServiciosNegocio(unittest.TestCase):
    """Suite de integración para los servicios de clínica, logística y laboratorio."""

    def setUp(self) -> None:
        ConexionBD.reiniciar_instancia()
        self.conexion = inicializar_base_datos(
            ConexionBD.obtener_instancia(RUTA_BD_EN_MEMORIA)
        )
        self.eventos = SujetoEventos()
        self.auditor = ObservadorAuditoria()
        self.eventos.suscribir(self.auditor)

        self.srv_clinica = ServicioClinica(self.conexion)
        self.srv_logistica = ServicioLogistica(self.conexion, self.eventos)
        self.srv_laboratorio = ServicioLaboratorio(self.conexion, self.eventos)

    def tearDown(self) -> None:
        ConexionBD.reiniciar_instancia()

    def _crear_escenario_base(self):
        """Crea cliente, mascota canina con vacunas al día, consulta, orden y muestra."""
        cliente = self.srv_clinica.registrar_cliente(
            dni="35123456",
            nombre="Luciano",
            apellido="Paglino",
            telefono="3515551234",
            email="luciano@ejemplo.com",
            direccion="Córdoba Capital",
        )
        mascota = self.srv_clinica.registrar_mascota(
            nombre="Rocco",
            especie_id=1,  # Canino
            edad=3,
            sexo="Macho",
            cliente_id=cliente.id,
            raza="Labrador",
            fecha_apertura_historia="2026-10-19",
            antecedentes="Sin cirugías",
            alergias="Ninguna",
        )
        return cliente, mascota

    # ----------------------------------------------------------------------------------
    # Procesos 1, 2 y 3 + Validaciones de Clínica
    # ----------------------------------------------------------------------------------

    def test_validacion_mascota_sin_responsable_rechazada_en_servicio(self):
        with self.assertRaises(ErrorMascotaSinResponsable):
            self.srv_clinica.registrar_mascota(
                nombre="Solitario",
                especie_id=1,
                edad=2,
                sexo="Macho",
                cliente_id=0,
            )

    def test_validacion_superposicion_de_turnos_por_rango_horario(self):
        _, mascota = self._crear_escenario_base()

        # Consulta de 10:00 a 10:30 con veterinario 1
        self.srv_clinica.registrar_consulta_medica(
            mascota_id=mascota.id,
            clinica_id=1,
            veterinario_id=1,
            fecha_hora_inicio="2026-10-19 10:00:00",
            duracion_minutos=30,
            motivo="Consulta inicial",
            costo_consulta=20000.0,
        )

        # Intentar agendar al mismo veterinario a las 10:15 (se solapa con 10:00-10:30)
        with self.assertRaises(ErrorSuperposicionTurno):
            self.srv_clinica.registrar_consulta_medica(
                mascota_id=mascota.id,
                clinica_id=1,
                veterinario_id=1,
                fecha_hora_inicio="2026-10-19 10:15:00",
                duracion_minutos=20,
                motivo="Turno superpuesto",
            )

        # A las 10:30 exactas sí está disponible
        consulta_ok, _ = self.srv_clinica.registrar_consulta_medica(
            mascota_id=mascota.id,
            clinica_id=1,
            veterinario_id=1,
            fecha_hora_inicio="2026-10-19 10:30:00",
            duracion_minutos=30,
            motivo="Turno consecutivo válido",
        )
        self.assertIsNotNone(consulta_ok.id)

    def test_control_esquema_vacunas_obligatorias_en_consulta(self):
        _, mascota = self._crear_escenario_base()

        # Si se exige esquema al día sin vacunas aplicadas, lanza ErrorVacunaObligatoriaFaltante
        with self.assertRaises(ErrorVacunaObligatoriaFaltante):
            self.srv_clinica.registrar_consulta_medica(
                mascota_id=mascota.id,
                clinica_id=1,
                veterinario_id=1,
                fecha_hora_inicio="2026-10-19 09:00:00",
                motivo="Control anual estricto",
                exigir_vacunas_al_dia=True,
            )

        # Aplicando las dos vacunas obligatorias caninas (id 1 y 2) durante la consulta
        consulta, pendientes = self.srv_clinica.registrar_consulta_medica(
            mascota_id=mascota.id,
            clinica_id=1,
            veterinario_id=1,
            fecha_hora_inicio="2026-10-19 09:00:00",
            motivo="Vacunación completa y control",
            tratamientos=[Tratamiento(None, 0, "Desparasitación interna", "TotalFull", "1 comp", 3)],
            vacunas_aplicadas_ids=[1, 2],
            exigir_vacunas_al_dia=True,
        )
        self.assertEqual(len(pendientes), 0)
        historia = self.srv_clinica.obtener_historia_clinica_completa(mascota.id)
        self.assertEqual(len(historia.vacunas), 2)
        self.assertEqual(len(historia.tratamientos), 1)

        # Intentar volver a aplicar la misma vacuna en la misma fecha lanza ErrorValidacionNegocio
        from src.dominio.excepciones import ErrorValidacionNegocio
        with self.assertRaises(ErrorValidacionNegocio):
            self.srv_clinica.aplicar_vacuna(
                mascota_id=mascota.id,
                vacuna_id=1,
                fecha_aplicacion="2026-10-19",
            )

    # ----------------------------------------------------------------------------------
    # Procesos 4, 5, 6 y 7: Circuito Completo Exitoso
    # ----------------------------------------------------------------------------------

    def test_circuito_completo_derivacion_transporte_analisis_y_facturacion(self):
        _, mascota = self._crear_escenario_base()
        consulta, _ = self.srv_clinica.registrar_consulta_medica(
            mascota_id=mascota.id,
            clinica_id=1,
            veterinario_id=1,
            fecha_hora_inicio="2026-10-19 10:00:00",
            motivo="Control prequirúrgico",
            costo_consulta=20000.0,
        )
        orden = self.srv_clinica.emitir_orden_derivacion(
            consulta_id=consulta.id,
            tipo_estudio_id=1,  # Hemograma completo ($18.000)
            indicaciones="Evaluar plaquetas",
            prioridad="Urgente",
            fecha_hora_emision="2026-10-19 10:15:00",
        )
        muestra = self.srv_clinica.extraer_muestra_biologica(
            orden_id=orden.id,
            codigo_muestra="MUE-SRV-001",
            tipo_muestra_id=1,
            fecha_hora_extraccion="2026-10-19 10:20:00",
        )
        self.assertEqual(muestra.estado_actual, "Extraida")

        # Proceso 4: Empaquetar en conservadora 1 con remito y precinto
        remito = self.srv_logistica.empaquetar_muestras(
            numero_remito="REM-SRV-001",
            clinica_origen_id=1,
            laboratorio_destino_id=1,
            conservadora_id=1,
            numero_serie_precinto="PREC-SRV-001",
            muestras_ids=[muestra.id],
            fecha_hora="2026-10-19 10:30:00",
        )
        self.assertEqual(remito.estado, "Precintado")
        self.assertFalse(remito.conservadora.disponible)
        self.assertEqual(remito.muestras[0].estado_actual, "Empaquetada")

        # Proceso 5: Despachar hacia laboratorio central
        envio = self.srv_logistica.despachar_remito(
            remito_id=remito.id,
            transportista_id=1,
            fecha_hora_despacho="2026-10-19 11:00:00",
        )
        self.assertEqual(envio.fecha_hora_despacho, "2026-10-19 11:00:00")
        muestra_en_transito = self.srv_clinica.muestra_dao.obtener_por_id(muestra.id)
        self.assertEqual(muestra_en_transito.estado_actual, "EnTransito")

        # Proceso 6: Recepción en laboratorio con precinto INTACTO
        remito_recibido = self.srv_logistica.recibir_remito_en_laboratorio(
            remito_id=remito.id,
            estado_precinto="Intacto",
            fecha_hora_recepcion="2026-10-19 12:00:00",
            observaciones="Cadena de frío a 4°C intacta.",
        )
        self.assertEqual(remito_recibido.estado, "Recibido")
        self.assertTrue(remito_recibido.conservadora.disponible)
        self.assertEqual(remito_recibido.muestras[0].estado_actual, "Recibida")

        # Proceso 7A: Registrar resultado bioquímico
        resultado = self.srv_laboratorio.registrar_resultado_analisis(
            muestra_id=muestra.id,
            profesional_laboratorio_id=1,
            valores_medidos="Hematocrito 42%, Leucocitos 9.500/uL",
            conclusion="Apto quirúrgico.",
            fecha_hora_analisis="2026-10-19 13:30:00",
        )
        self.assertEqual(resultado.costo_analisis, 18000.0)
        muestra_analizada = self.srv_clinica.muestra_dao.obtener_por_id(muestra.id)
        self.assertEqual(muestra_analizada.estado_actual, "Analizada")
        self.assertEqual(len(muestra_analizada.historial), 5)

        # Proceso 7B: Emitir comprobante aplicando Tarifa Urgencia (+30% sobre lab)
        comprobante = self.srv_laboratorio.emitir_comprobante_atencion(
            consulta_id=consulta.id,
            numero_comprobante="FAC-SRV-0001",
            estrategia=TarifaUrgenciaLaboratorio(30.0),
            fecha_hora_emision="2026-10-19 14:00:00",
        )
        # 20.000 (consulta) + 18.000 (lab) + 5.400 (recargo 30%) = 43.400
        self.assertEqual(comprobante.monto_total, 43400.0)
        self.assertEqual(len(comprobante.detalles), 3)

    # ----------------------------------------------------------------------------------
    # Validaciones de Rechazo Logístico y Consistencia
    # ----------------------------------------------------------------------------------

    def test_rechazo_automatico_si_precinto_llega_roto_e_imposibilidad_de_analizar(self):
        _, mascota = self._crear_escenario_base()
        consulta, _ = self.srv_clinica.registrar_consulta_medica(
            mascota_id=mascota.id,
            clinica_id=1,
            veterinario_id=1,
            fecha_hora_inicio="2026-10-19 10:00:00",
            motivo="Urgencia",
        )
        orden = self.srv_clinica.emitir_orden_derivacion(
            consulta_id=consulta.id,
            tipo_estudio_id=2,
            fecha_hora_emision="2026-10-19 10:10:00",
        )
        muestra = self.srv_clinica.extraer_muestra_biologica(
            orden_id=orden.id,
            codigo_muestra="MUE-ROTA-01",
            tipo_muestra_id=1,
            fecha_hora_extraccion="2026-10-19 10:15:00",
        )
        remito = self.srv_logistica.empaquetar_muestras(
            numero_remito="REM-ROTO-01",
            clinica_origen_id=1,
            laboratorio_destino_id=1,
            conservadora_id=1,
            numero_serie_precinto="PREC-ROTO-99",
            muestras_ids=[muestra.id],
            fecha_hora="2026-10-19 10:25:00",
        )
        self.srv_logistica.despachar_remito(
            remito_id=remito.id,
            transportista_id=1,
            fecha_hora_despacho="2026-10-19 10:40:00",
        )

        # Arribo al laboratorio con precinto ROTO
        remito_rechazado = self.srv_logistica.recibir_remito_en_laboratorio(
            remito_id=remito.id,
            estado_precinto="Roto",
            fecha_hora_recepcion="2026-10-19 11:30:00",
            observaciones="Precinto cortado durante el traslado",
        )
        self.assertEqual(remito_rechazado.estado, "Rechazado")
        self.assertEqual(remito_rechazado.muestras[0].estado_actual, "Rechazada")

        # Verificar que el patrón Observer notificó el rechazo
        eventos_rechazo = [
            e for e in self.auditor.registro_eventos
            if e["evento"] == "MUESTRAS_RECHAZADAS_EN_RECEPCION"
        ]
        self.assertEqual(len(eventos_rechazo), 1)

        # Intentar analizar una muestra rechazada está bloqueado por el patrón State
        with self.assertRaises(ErrorTransicionEstadoInvalida):
            self.srv_laboratorio.registrar_resultado_analisis(
                muestra_id=muestra.id,
                profesional_laboratorio_id=1,
                valores_medidos="Intento ilegal",
                conclusion="No debería guardarse",
            )

    def test_no_permite_empaquetar_muestra_de_otra_clinica(self):
        _, mascota = self._crear_escenario_base()
        # Consulta realizada en clínica 2
        consulta, _ = self.srv_clinica.registrar_consulta_medica(
            mascota_id=mascota.id,
            clinica_id=2,
            veterinario_id=1,
            fecha_hora_inicio="2026-10-19 10:00:00",
            motivo="Consulta en sede Nueva Córdoba",
        )
        orden = self.srv_clinica.emitir_orden_derivacion(
            consulta_id=consulta.id,
            tipo_estudio_id=1,
            fecha_hora_emision="2026-10-19 10:15:00",
        )
        muestra = self.srv_clinica.extraer_muestra_biologica(
            orden_id=orden.id,
            codigo_muestra="MUE-CLIN2",
            tipo_muestra_id=1,
            fecha_hora_extraccion="2026-10-19 10:20:00",
        )

        # Intentar empaquetarla en un remito de la clínica 1 lanza ErrorClinicaNoCoincide
        with self.assertRaises(ErrorClinicaNoCoincide):
            self.srv_logistica.empaquetar_muestras(
                numero_remito="REM-CRUZADO",
                clinica_origen_id=1,
                laboratorio_destino_id=1,
                conservadora_id=1,
                numero_serie_precinto="PREC-CRUZADO",
                muestras_ids=[muestra.id],
            )


if __name__ == "__main__":
    unittest.main()
