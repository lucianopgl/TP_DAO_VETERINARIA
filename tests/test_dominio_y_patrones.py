"""
Pruebas Unitarias: Capa de Dominio y Patrones de Diseño GoF (Fase 3 - Paso 2)
=============================================================================

Cubre:
    1. Patrón State: Ciclo de vida inmutable de MuestraBiologica.
       - Transiciones válidas e inválidas.
       - Rechazo obligatorio ante precinto 'Roto' o 'Violado'.
       - Registro inmutable en el historial de trazabilidad.
    2. Patrón Strategy: Cálculo de liquidaciones y aranceles.
       - Tarifa Estándar, Tarifa Urgencia (+30% Lab) y Convenio Red (-15% Clínica).
    3. Patrón Iterator: Recorrido encapsulado en ConservadoraIsotermica.
       - Recorrido estándar y recorrido filtrado de muestras viables.
       - Control estricto de capacidad máxima.
    4. Patrón Observer: Publicación y suscripción a eventos de alerta.
    5. Validaciones de Dominio:
       - Responsable obligatorio en Mascota.
       - Cálculo y detección de superposición de horarios en Consultas.
"""

import unittest
from src.dominio.cliente import Cliente
from src.dominio.mascota import Mascota
from src.dominio.consulta_medica import ConsultaMedica, OrdenDerivacion
from src.dominio.historia_clinica import Tratamiento, VacunaAplicada
from src.dominio.muestra_biologica import MuestraBiologica
from src.dominio.logistica import ConservadoraIsotermica, PrecintoSanitario, RemitoBiologico
from src.dominio.facturacion import ResultadoAnalisis
from src.dominio.excepciones import (
    ErrorCapacidadConservadoraExcedida,
    ErrorDatosInvalidos,
    ErrorMascotaSinResponsable,
    ErrorTransicionEstadoInvalida,
    ErrorValidacionNegocio,
)
from src.patrones.estrategia_facturacion import (
    TarifaConvenioRed,
    TarifaEstandar,
    TarifaUrgenciaLaboratorio,
)
from src.patrones.observador_eventos import ObservadorAuditoria, SujetoEventos


class PruebaPatronState(unittest.TestCase):
    """Verifica el ciclo de vida de la muestra biológica y su trazabilidad."""

    def setUp(self) -> None:
        self.muestra = MuestraBiologica(
            id=1,
            codigo_muestra="MUE-2026-001",
            orden_id=10,
            tipo_muestra_id=1,
            fecha_hora_extraccion="2026-10-19 10:00:00",
            nombre_tipo_muestra="Sangre entera",
        )
        self.remito = RemitoBiologico(
            id=100,
            numero_remito="REM-001",
            clinica_origen_id=1,
            laboratorio_destino_id=1,
            conservadora_id=1,
            fecha_hora_creacion="2026-10-19 10:30:00",
        )

    def test_estado_inicial_es_extraida_con_historial_de_creacion(self):
        self.assertEqual(self.muestra.estado_actual, "Extraida")
        self.assertTrue(self.muestra.esta_viable)
        self.assertEqual(len(self.muestra.historial), 1)
        self.assertEqual(self.muestra.historial[0].estado_nuevo, "Extraida")

    def test_transicion_valida_extraida_a_empaquetada(self):
        self.muestra.empaquetar(self.remito, fecha_hora="2026-10-19 10:35:00")
        self.assertEqual(self.muestra.estado_actual, "Empaquetada")
        self.assertEqual(self.muestra.remito_id, 100)
        self.assertEqual(len(self.muestra.historial), 2)
        self.assertEqual(self.muestra.historial[1].estado_anterior, "Extraida")
        self.assertEqual(self.muestra.historial[1].estado_nuevo, "Empaquetada")

    def test_transicion_invalida_extraida_directo_a_recibida_lanza_error(self):
        with self.assertRaises(ErrorTransicionEstadoInvalida) as ctx:
            self.muestra.recibir("Intacto", fecha_hora="2026-10-19 11:00:00")
        self.assertEqual(ctx.exception.estado_actual, "Extraida")

    def test_ciclo_completo_exitoso_hasta_analizada(self):
        # 1. Empaquetar
        self.muestra.empaquetar(self.remito, fecha_hora="2026-10-19 10:35:00")
        # 2. Despachar
        self.muestra.despachar(fecha_hora="2026-10-19 11:00:00")
        self.assertEqual(self.muestra.estado_actual, "EnTransito")
        # 3. Recibir con precinto Intacto
        self.muestra.recibir("Intacto", fecha_hora="2026-10-19 12:30:00")
        self.assertEqual(self.muestra.estado_actual, "Recibida")
        # 4. Analizar
        resultado = ResultadoAnalisis(
            id=1,
            muestra_id=self.muestra.id,
            profesional_laboratorio_id=1,
            valores_medidos="Glóbulos rojos: 7.2 M/ul, Leucocitos: 11.500/ul",
            conclusion="Valores hematológicos dentro de rangos normales.",
            costo_analisis=18000.0,
            fecha_hora_analisis="2026-10-19 14:00:00",
            bioquimico_nombre="Valeria Ríos",
        )
        self.muestra.analizar(resultado, fecha_hora="2026-10-19 14:00:00")
        self.assertEqual(self.muestra.estado_actual, "Analizada")
        self.assertEqual(len(self.muestra.historial), 5)

    def test_rechazo_obligatorio_ante_precinto_roto(self):
        """Regla crítica del TP: precinto roto -> muestra pasa a Rechazada y no se procesa."""
        self.muestra.empaquetar(self.remito, fecha_hora="2026-10-19 10:35:00")
        self.muestra.despachar(fecha_hora="2026-10-19 11:00:00")
        
        # Recepción con precinto roto
        self.muestra.recibir("Roto", fecha_hora="2026-10-19 12:30:00", observacion="Fisura en el precinto")
        self.assertEqual(self.muestra.estado_actual, "Rechazada")
        self.assertFalse(self.muestra.esta_viable)
        self.assertIn("roto", self.muestra.motivo_rechazo.lower())

        # No se permite analizar una muestra rechazada
        resultado = ResultadoAnalisis(
            id=1,
            muestra_id=self.muestra.id,
            profesional_laboratorio_id=1,
            valores_medidos="Sin datos",
            conclusion="No procesable",
            costo_analisis=0.0,
            fecha_hora_analisis="2026-10-19 14:00:00",
        )
        with self.assertRaises(ErrorTransicionEstadoInvalida):
            self.muestra.analizar(resultado, fecha_hora="2026-10-19 14:00:00")

    def test_rechazo_obligatorio_ante_precinto_violado(self):
        """Regla crítica acordada: precinto violado -> muestra pasa a Rechazada."""
        self.muestra.empaquetar(self.remito, fecha_hora="2026-10-19 10:35:00")
        self.muestra.despachar(fecha_hora="2026-10-19 11:00:00")
        self.muestra.recibir("Violado", fecha_hora="2026-10-19 12:30:00")
        self.assertEqual(self.muestra.estado_actual, "Rechazada")
        self.assertIn("violado", self.muestra.motivo_rechazo.lower())


class PruebaPatronStrategy(unittest.TestCase):
    """Verifica el cálculo de liquidación según la estrategia de aranceles seleccionada."""

    def setUp(self) -> None:
        self.costo_consulta = 20000.0
        self.estudios = [
            ("Hemograma completo", 18000.0),
            ("Perfil bioquímico", 32000.0),
        ]
        # Total base: 20.000 (clínica) + 50.000 (lab) = 70.000

    def test_tarifa_estandar(self):
        estrategia = TarifaEstandar()
        liq = estrategia.liquidar(self.costo_consulta, self.estudios)
        self.assertEqual(liq.subtotal_clinica, 20000.0)
        self.assertEqual(liq.subtotal_laboratorio, 50000.0)
        self.assertEqual(liq.total, 70000.0)
        self.assertEqual(len(liq.items), 3)

    def test_tarifa_urgencia_laboratorio_aplica_recargo_al_lab(self):
        # 30% sobre 50.000 = 15.000 de recargo. Lab final = 65.000. Total = 85.000.
        estrategia = TarifaUrgenciaLaboratorio(porcentaje_recargo=30.0)
        liq = estrategia.liquidar(self.costo_consulta, self.estudios)
        self.assertEqual(liq.subtotal_clinica, 20000.0)
        self.assertEqual(liq.subtotal_laboratorio, 65000.0)
        self.assertEqual(liq.total, 85000.0)
        recargos = [i for i in liq.items if i.tipo_concepto == "Recargo"]
        self.assertEqual(len(recargos), 1)
        self.assertEqual(recargos[0].monto, 15000.0)

    def test_tarifa_convenio_red_aplica_bonificacion_a_la_clinica(self):
        # 15% sobre 20.000 = 3.000 de descuento. Clínica final = 17.000. Total = 67.000.
        estrategia = TarifaConvenioRed(porcentaje_descuento=15.0)
        liq = estrategia.liquidar(self.costo_consulta, self.estudios)
        self.assertEqual(liq.subtotal_clinica, 17000.0)
        self.assertEqual(liq.subtotal_laboratorio, 50000.0)
        self.assertEqual(liq.total, 67000.0)
        bonificaciones = [i for i in liq.items if i.tipo_concepto == "Bonificacion"]
        self.assertEqual(len(bonificaciones), 1)
        self.assertEqual(bonificaciones[0].monto, -3000.0)


class PruebaPatronIteratorYConservadora(unittest.TestCase):
    """Verifica el recorrido encapsulado de muestras en la conservadora isotérmica."""

    def setUp(self) -> None:
        self.conservadora = ConservadoraIsotermica(
            id=1, codigo="CONS-TEST", capacidad_maxima=2, temperatura_min=2.0, temperatura_max=8.0
        )
        self.m1 = MuestraBiologica(1, "M-01", 1, 1, "2026-10-19 10:00:00")
        self.m2 = MuestraBiologica(2, "M-02", 1, 1, "2026-10-19 10:05:00")

    def test_iterador_recorre_todas_las_muestras_cargadas(self):
        self.conservadora.agregar_muestra(self.m1)
        self.conservadora.agregar_muestra(self.m2)

        muestras_recorridas = [m for m in self.conservadora]
        self.assertEqual(muestras_recorridas, [self.m1, self.m2])

    def test_capacidad_maxima_lanzada_al_intentar_superar_limite(self):
        self.conservadora.agregar_muestra(self.m1)
        self.conservadora.agregar_muestra(self.m2)
        m3 = MuestraBiologica(3, "M-03", 1, 1, "2026-10-19 10:10:00")

        with self.assertRaises(ErrorCapacidadConservadoraExcedida) as ctx:
            self.conservadora.agregar_muestra(m3)
        self.assertEqual(ctx.exception.capacidad_maxima, 2)

    def test_iterador_filtrado_solo_entrega_muestras_viables(self):
        self.conservadora.agregar_muestra(self.m1)
        self.conservadora.agregar_muestra(self.m2)

        # Rechazamos artificialmente la muestra 2
        remito = RemitoBiologico(1, "R-1", 1, 1, 1, "2026-10-19 10:00:00")
        self.m2.empaquetar(remito, "2026-10-19 10:10:00")
        self.m2.despachar("2026-10-19 10:20:00")
        self.m2.recibir("Roto", "2026-10-19 11:00:00")

        viables = [m for m in self.conservadora.iterar_viables()]
        self.assertEqual(viables, [self.m1])


class PruebaPatronObserver(unittest.TestCase):
    """Verifica el mecanismo de notificación y suscripción sin acoplamiento."""

    def test_notificacion_a_observadores(self):
        sujeto = SujetoEventos()
        auditor = ObservadorAuditoria()
        sujeto.suscribir(auditor)

        sujeto.notificar("MUESTRA_RECHAZADA", codigo="M-99", motivo="Precinto roto")
        self.assertEqual(len(auditor.registro_eventos), 1)
        self.assertEqual(auditor.registro_eventos[0]["evento"], "MUESTRA_RECHAZADA")
        self.assertEqual(auditor.registro_eventos[0]["datos"]["codigo"], "M-99")

        sujeto.desuscribir(auditor)
        sujeto.notificar("OTRO_EVENTO")
        self.assertEqual(len(auditor.registro_eventos), 1)


class PruebaValidacionesDominio(unittest.TestCase):
    """Verifica validaciones de Cliente, Mascota y Consulta."""

    def test_mascota_sin_cliente_lanza_error_obligatorio(self):
        with self.assertRaises(ErrorMascotaSinResponsable):
            Mascota(id=None, nombre="Rocky", especie_id=1, edad=3, sexo="Macho", cliente_id=0)

    def test_mascota_con_edad_negativa_lanza_error(self):
        with self.assertRaises(ErrorDatosInvalidos) as ctx:
            Mascota(id=None, nombre="Rocky", especie_id=1, edad=-1, sexo="Macho", cliente_id=1)
        self.assertEqual(ctx.exception.campo, "edad")

    def test_superposicion_horaria_de_consultas(self):
        # Consulta de 10:00 a 10:30 (30 minutos)
        c1 = ConsultaMedica(
            id=1, mascota_id=1, clinica_id=1, veterinario_id=1,
            fecha_hora_inicio="2026-10-19 10:00:00", duracion_minutos=30, motivo="Control"
        )
        self.assertEqual(c1.fecha_hora_fin, "2026-10-19 10:30:00")

        # Turno a las 10:15 por 20 minutos (se superpone)
        self.assertTrue(c1.se_superpone_con("2026-10-19 10:15:00", 20))

        # Turno a las 09:40 por 30 minutos (termina a las 10:10, se superpone)
        self.assertTrue(c1.se_superpone_con("2026-10-19 09:40:00", 30))

        # Turno a las 10:30 por 30 minutos (empieza justo cuando termina: NO se superpone)
        self.assertFalse(c1.se_superpone_con("2026-10-19 10:30:00", 30))

        # Turno a las 09:00 por 30 minutos (termina a las 09:30: NO se superpone)
        self.assertFalse(c1.se_superpone_con("2026-10-19 09:00:00", 30))


if __name__ == "__main__":
    unittest.main()
