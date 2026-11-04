"""
Capa de Servicios: ServicioLaboratorio
======================================

Coordina el Proceso de Negocio Obligatorio 7:
    7. Registrar resultados de análisis y emitir comprobantes de atención.

Patrones de Diseño que Orquesta:
    - STATE (`EstadoMuestra`): Sólo permite cargar resultados sobre muestras en
      estado 'Recibida', bloqueando cualquier intento sobre muestras 'Rechazada',
      'EnTransito', 'Empaquetada' o 'Extraida' (`ErrorTransicionEstadoInvalida`).
    - STRATEGY (`EstrategiaFacturacion`): Aplica polimórficamente la tarifa elegida
      (`TarifaEstandar`, `TarifaUrgenciaLaboratorio` o `TarifaConvenioRed`) para
      generar la cabecera y los detalles desglosados del comprobante.
    - OBSERVER (`SujetoEventos`): Notifica cuando un resultado bioquímico está listo.
"""

from __future__ import annotations

from datetime import datetime

from src.dominio.consulta_medica import FORMATO_FECHA_HORA
from src.dominio.excepciones import ErrorEntidadNoEncontrada, ErrorValidacionNegocio
from src.dominio.facturacion import (
    ComprobanteAtencion,
    DetalleComprobante,
    ResultadoAnalisis,
)
from src.dominio.muestra_biologica import MuestraBiologica
from src.patrones.estrategia_facturacion import (
    MAPA_ESTRATEGIAS,
    EstrategiaFacturacion,
    LiquidacionFactura,
    TarifaEstandar,
)
from src.patrones.observador_eventos import Observador, SujetoEventos
from src.persistencia.conexion_bd import ConexionBD
from src.persistencia.consulta_dao import ConsultaDAO
from src.persistencia.facturacion_dao import FacturacionDAO
from src.persistencia.muestra_dao import MuestraDAO


class ServicioLaboratorio:
    """
    Servicio encargado del procesamiento bioquímico de muestras viables y de la
    facturación desglosada de atenciones clínicas y servicios de laboratorio.
    """

    def __init__(
        self,
        conexion: ConexionBD | None = None,
        sujeto_eventos: SujetoEventos | None = None,
        muestra_dao: MuestraDAO | None = None,
        consulta_dao: ConsultaDAO | None = None,
        facturacion_dao: FacturacionDAO | None = None,
    ) -> None:
        self.conexion = conexion or ConexionBD.obtener_instancia()
        self.muestra_dao = muestra_dao or MuestraDAO(self.conexion)
        self.consulta_dao = consulta_dao or ConsultaDAO(self.conexion)
        self.facturacion_dao = facturacion_dao or FacturacionDAO(self.conexion)
        self.eventos = sujeto_eventos or SujetoEventos()

    def suscribir_observador(self, observador: Observador) -> None:
        """Suscribe un observador a los eventos de resultados y facturación."""
        self.eventos.suscribir(observador)

    # ==================================================================================
    # PROCESO 7 (Parte A): Registrar Resultados de Análisis
    # ==================================================================================

    def registrar_resultado_analisis(
        self,
        muestra_id: int,
        profesional_laboratorio_id: int,
        valores_medidos: str,
        conclusion: str,
        costo_analisis: float | None = None,
        fecha_hora_analisis: str | None = None,
        observacion: str = "",
    ) -> ResultadoAnalisis:
        """
        Registra el informe bioquímico de una muestra y la pasa a estado 'Analizada':
            1. Recupera la muestra y el profesional de laboratorio firmante.
            2. Si no se indica `costo_analisis`, toma el costo base del estudio
               definido en la orden de derivación.
            3. Ejecuta `muestra.analizar(resultado)` (Patrón STATE): si la muestra
               fue rechazada por precinto roto/violado o no fue recibida, lanza
               `ErrorTransicionEstadoInvalida`.
            4. Guarda atómicamente el resultado, el nuevo estado y el historial.
        """
        muestra = self.muestra_dao.obtener_por_id(muestra_id)
        if muestra is None:
            raise ErrorEntidadNoEncontrada("Muestra biológica", muestra_id)

        profesional = self._obtener_profesional_laboratorio(profesional_laboratorio_id)
        nombre_bioquimico = f"{profesional['nombre']} {profesional['apellido']}"

        orden = self.consulta_dao.obtener_orden_por_id(muestra.orden_id)
        if orden is None:
            raise ErrorEntidadNoEncontrada("Orden de derivación", muestra.orden_id)

        arancel_final = (
            float(costo_analisis) if costo_analisis is not None else float(orden.costo_base)
        )
        marca_temporal = fecha_hora_analisis or datetime.now().strftime(FORMATO_FECHA_HORA)

        resultado = ResultadoAnalisis(
            id=None,
            muestra_id=muestra_id,
            profesional_laboratorio_id=profesional_laboratorio_id,
            valores_medidos=valores_medidos,
            conclusion=conclusion,
            costo_analisis=arancel_final,
            fecha_hora_analisis=marca_temporal,
            bioquimico_nombre=nombre_bioquimico,
        )

        # El Patrón STATE valida que la muestra esté en estado 'Recibida'
        estado_previo = muestra.estado_actual
        muestra.analizar(resultado, fecha_hora=marca_temporal, observacion=observacion)
        ultimo_evento = muestra.historial[-1]

        with self.conexion.transaccion():
            resultado_id = self.facturacion_dao.crear_resultado(resultado)
            self.muestra_dao.actualizar_estado(
                muestra_id=muestra_id,
                estado_anterior=estado_previo,
                estado_nuevo=muestra.estado_actual,
                fecha_hora=marca_temporal,
                observacion=ultimo_evento.observacion or "",
            )

        self.eventos.notificar(
            "RESULTADO_ANALISIS_LISTO",
            muestra_id=muestra_id,
            codigo_muestra=muestra.codigo_muestra,
            orden_id=muestra.orden_id,
            consulta_id=orden.consulta_id,
            bioquimico=nombre_bioquimico,
            fecha_hora=marca_temporal,
        )
        return self.facturacion_dao.obtener_resultado_por_muestra(muestra_id)

    # ==================================================================================
    # PROCESO 7 (Parte B): Emitir Comprobantes de Atención (Patrón STRATEGY)
    # ==================================================================================

    @staticmethod
    def resolver_estrategia(
        estrategia: EstrategiaFacturacion | str | None,
    ) -> EstrategiaFacturacion:
        """
        Permite recibir tanto una instancia de `EstrategiaFacturacion` como el
        nombre de la tarifa ('Tarifa Estándar', 'Tarifa Urgencia', 'Tarifa Convenio Red').
        """
        if isinstance(estrategia, EstrategiaFacturacion):
            return estrategia
        if isinstance(estrategia, str):
            clase_estrategia = MAPA_ESTRATEGIAS.get(estrategia.strip())
            if clase_estrategia is None:
                raise ErrorValidacionNegocio(
                    f"No existe la estrategia de facturación '{estrategia}'."
                )
            return clase_estrategia()
        return TarifaEstandar()

    def calcular_liquidacion_consulta(
        self,
        consulta_id: int,
        estrategia: EstrategiaFacturacion | str | None = None,
    ) -> LiquidacionFactura:
        """
        Recopila los cargos de una consulta médica y de todos sus análisis de
        laboratorio completados, y delega el cálculo polimórfico en la estrategia
        seleccionada (Patrón STRATEGY).
        """
        consulta = self.consulta_dao.obtener_por_id(consulta_id)
        if consulta is None:
            raise ErrorEntidadNoEncontrada("Consulta médica", consulta_id)

        estudios_realizados = self.facturacion_dao.listar_costos_estudios_completados_por_consulta(
            consulta_id
        )

        estrategia_obj = self.resolver_estrategia(estrategia)
        return estrategia_obj.liquidar(
            costo_consulta=consulta.costo_consulta,
            costos_laboratorio=estudios_realizados,
            motivo_consulta=consulta.motivo,
        )

    def emitir_comprobante_atencion(
        self,
        consulta_id: int,
        numero_comprobante: str,
        estrategia: EstrategiaFacturacion | str | None = None,
        fecha_hora_emision: str | None = None,
    ) -> ComprobanteAtencion:
        """
        Liquida y persiste de forma atómica el comprobante de atención (cabecera y
        detalles desglosados) utilizando la estrategia de facturación indicada.
        """
        liquidacion = self.calcular_liquidacion_consulta(consulta_id, estrategia)
        marca_temporal = fecha_hora_emision or datetime.now().strftime(FORMATO_FECHA_HORA)

        detalles = [
            DetalleComprobante(
                id=None,
                comprobante_id=None,
                tipo_concepto=item.tipo_concepto,
                concepto=item.concepto,
                monto=item.monto,
            )
            for item in liquidacion.items
        ]
        comprobante = ComprobanteAtencion(
            id=None,
            numero_comprobante=numero_comprobante,
            consulta_id=consulta_id,
            estrategia_tarifa=liquidacion.nombre_estrategia,
            monto_total=liquidacion.total,
            fecha_hora_emision=marca_temporal,
            detalles=detalles,
        )
        comprobante_id = self.facturacion_dao.crear_comprobante(comprobante)
        return self.facturacion_dao.obtener_comprobante_por_id(comprobante_id)

    # ==================================================================================
    # Consultas de Apoyo para Laboratorio y Facturación
    # ==================================================================================

    def listar_muestras_recibidas_pendientes_analisis(self) -> list[MuestraBiologica]:
        """Devuelve todas las muestras en estado 'Recibida' listas para ser analizadas."""
        return self.muestra_dao.listar_por_estado("Recibida")

    def obtener_resultado_de_muestra(self, muestra_id: int) -> ResultadoAnalisis | None:
        """Devuelve el resultado de análisis cargado para una muestra, si existe."""
        return self.facturacion_dao.obtener_resultado_por_muestra(muestra_id)

    def obtener_comprobante_por_consulta(
        self, consulta_id: int
    ) -> ComprobanteAtencion | None:
        """Recupera el comprobante emitido para una consulta médica."""
        return self.facturacion_dao.obtener_comprobante_por_consulta(consulta_id)

    def listar_comprobantes(self) -> list[ComprobanteAtencion]:
        """Lista todos los comprobantes emitidos."""
        return self.facturacion_dao.listar_comprobantes()

    def listar_profesionales_laboratorio(self) -> list[dict]:
        """Devuelve los bioquímicos/profesionales del laboratorio central."""
        return self.facturacion_dao.listar_profesionales_laboratorio()

    def _obtener_profesional_laboratorio(self, profesional_id: int) -> dict:
        profesional = self.facturacion_dao.obtener_profesional_laboratorio_por_id(profesional_id)
        if profesional is None:
            raise ErrorEntidadNoEncontrada("Profesional de laboratorio", profesional_id)
        return profesional
