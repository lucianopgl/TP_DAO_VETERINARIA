"""
Capa de Servicios: ServicioLogistica
====================================

Coordina los Procesos de Negocio Obligatorios 4, 5 y 6 (Núcleo de Trazabilidad):
    4. Empaquetar muestras biológicas en conservadoras isotérmicas generando un
       remito biológico y un precinto sanitario.
    5. Registrar la cadena de envío desde la clínica hacia el laboratorio central.
    6. Registrar la recepción en el laboratorio, verificando el estado del precinto
       para garantizar la viabilidad de la muestra.

Patrones de Diseño que Orquesta:
    - STATE (`EstadoMuestra`): Cada muestra valida y ejecuta sus transiciones
      (`Extraida` -> `Empaquetada` -> `EnTransito` -> `Recibida` | `Rechazada`).
    - ITERATOR (`ConservadoraIsotermica`): Recorrido encapsulado de las muestras
      alojadas en la conservadora y filtrado de muestras viables.
    - OBSERVER (`SujetoEventos`): Emisión de alertas automáticas cuando un precinto
      arriba roto o violado y las muestras resultan rechazadas.
    - UNIDAD DE TRABAJO (`ConexionBD.transaccion`): Garantiza atomicidad total entre
      muestras, historiales inmutables, remito, precinto, conservadora y envío.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from src.dominio.consulta_medica import FORMATO_FECHA_HORA
from src.dominio.excepciones import (
    ErrorClinicaNoCoincide,
    ErrorEntidadNoEncontrada,
    ErrorValidacionNegocio,
)
from src.dominio.logistica import (
    ConservadoraIsotermica,
    EnvioLaboratorio,
    PrecintoSanitario,
    RemitoBiologico,
)
from src.dominio.muestra_biologica import MuestraBiologica
from src.patrones.observador_eventos import Observador, SujetoEventos
from src.persistencia.conexion_bd import ConexionBD
from src.persistencia.logistica_dao import LogisticaDAO
from src.persistencia.muestra_dao import MuestraDAO


class ServicioLogistica:
    """
    Servicio encargado de la cadena de frío, custodia sanitaria y transporte
    de muestras biológicas desde las clínicas hasta el laboratorio central.
    """

    def __init__(
        self,
        conexion: ConexionBD | None = None,
        sujeto_eventos: SujetoEventos | None = None,
        logistica_dao: LogisticaDAO | None = None,
        muestra_dao: MuestraDAO | None = None,
    ) -> None:
        self.conexion = conexion or ConexionBD.obtener_instancia()
        self.logistica_dao = logistica_dao or LogisticaDAO(self.conexion)
        self.muestra_dao = muestra_dao or MuestraDAO(self.conexion)
        self.eventos = sujeto_eventos or SujetoEventos()

    def suscribir_observador(self, observador: Observador) -> None:
        """Suscribe un observador a los eventos logísticos y sanitarios (Patrón Observer)."""
        self.eventos.suscribir(observador)

    # ==================================================================================
    # PROCESO 4: Empaquetar Muestras en Conservadora con Remito y Precinto
    # ==================================================================================

    def obtener_clinica_origen_de_muestra(self, muestra_id: int) -> int:
        """
        Obtiene el ID de la clínica en la que se extrajo la muestra delegando
        la consulta relacional en `MuestraDAO`.
        """
        clinica_id = self.muestra_dao.obtener_clinica_origen(muestra_id)
        if clinica_id is None:
            raise ErrorEntidadNoEncontrada("Muestra biológica", muestra_id)
        return clinica_id

    def empaquetar_muestras(
        self,
        numero_remito: str,
        clinica_origen_id: int,
        laboratorio_destino_id: int,
        conservadora_id: int,
        numero_serie_precinto: str,
        muestras_ids: Iterable[int],
        fecha_hora: str | None = None,
        observacion: str = "",
    ) -> RemitoBiologico:
        """
        Ejecuta de forma atómica el Proceso 4 completo:
            1. Verifica que la conservadora isotérmica exista y esté disponible.
            2. Recupera cada muestra, verifica que provenga de la misma `clinica_origen_id`
               y la aloja en la conservadora (controlando su capacidad máxima física).
            3. Crea el remito biológico ('EnPreparacion') y el precinto sanitario ('Intacto').
            4. Recorre la conservadora mediante el Patrón ITERATOR y empaqueta cada muestra
               mediante el Patrón STATE ('Extraida' -> 'Empaquetada').
            5. Sella el remito con el precinto ('EnPreparacion' -> 'Precintado') y ocupa
               la conservadora.
        """
        lista_ids = list(dict.fromkeys(muestras_ids))
        if not lista_ids:
            raise ErrorValidacionNegocio(
                "Debe seleccionar al menos una muestra biológica para empaquetar."
            )

        conservadora = self.logistica_dao.obtener_conservadora_por_id(conservadora_id)
        if conservadora is None:
            raise ErrorEntidadNoEncontrada("Conservadora isotérmica", conservadora_id)
        if not conservadora.disponible:
            raise ErrorValidacionNegocio(
                f"La conservadora '{conservadora.codigo}' no se encuentra disponible."
            )

        # Cargamos las muestras en la conservadora verificando clínica de origen y capacidad
        for mid in lista_ids:
            muestra = self.muestra_dao.obtener_por_id(mid)
            if muestra is None:
                raise ErrorEntidadNoEncontrada("Muestra biológica", mid)
            clinica_muestra = self.obtener_clinica_origen_de_muestra(mid)
            if clinica_muestra != clinica_origen_id:
                raise ErrorClinicaNoCoincide()
            # agregar_muestra lanza ErrorCapacidadConservadoraExcedida si supera el tope
            conservadora.agregar_muestra(muestra)

        marca_temporal = fecha_hora or datetime.now().strftime(FORMATO_FECHA_HORA)

        with self.conexion.transaccion():
            # 1. Crear precinto sanitario intacto
            precinto_id = self.logistica_dao.crear_precinto(
                numero_serie=numero_serie_precinto, estado="Intacto"
            )
            precinto = self.logistica_dao.obtener_precinto_por_id(precinto_id)

            # 2. Crear remito biológico inicialmente en preparación
            remito = RemitoBiologico(
                id=None,
                numero_remito=numero_remito,
                clinica_origen_id=clinica_origen_id,
                laboratorio_destino_id=laboratorio_destino_id,
                conservadora_id=conservadora_id,
                fecha_hora_creacion=marca_temporal,
                estado="EnPreparacion",
                conservadora=conservadora,
                muestras=list(conservadora),
            )
            remito_id = self.logistica_dao.crear_remito(remito)

            # 3. Recorrer la conservadora con el Patrón ITERATOR y transicionar cada muestra (STATE)
            for muestra in conservadora:
                estado_previo = muestra.estado_actual
                muestra.empaquetar(remito, fecha_hora=marca_temporal, observacion=observacion)
                ultimo_evento = muestra.historial[-1]
                self.muestra_dao.actualizar_estado(
                    muestra_id=muestra.id,
                    estado_anterior=estado_previo,
                    estado_nuevo=muestra.estado_actual,
                    fecha_hora=marca_temporal,
                    observacion=ultimo_evento.observacion or "",
                    remito_id=remito_id,
                )

            # 4. Sellar el remito con el precinto sanitario intacto
            estado_remito_previo = remito.estado
            remito.precintar(precinto)
            self.logistica_dao.actualizar_estado_remito(
                remito_id=remito_id,
                estado_anterior=estado_remito_previo,
                estado_nuevo=remito.estado,
                fecha_hora=marca_temporal,
                observacion=f"Precintado con sello N° {precinto.numero_serie}.",
                precinto_id=precinto_id,
            )

            # 5. Marcar la conservadora como ocupada
            self.logistica_dao.actualizar_disponibilidad_conservadora(
                conservadora_id=conservadora_id, disponible=False
            )

        return self.obtener_remito_completo(remito_id)

    # ==================================================================================
    # PROCESO 5: Registrar Cadena de Envío hacia el Laboratorio Central
    # ==================================================================================

    def despachar_remito(
        self,
        remito_id: int,
        transportista_id: int,
        fecha_hora_despacho: str | None = None,
        observacion: str = "",
    ) -> EnvioLaboratorio:
        """
        Registra la salida del remito desde la clínica hacia el laboratorio central:
            1. Valida que el remito esté 'Precintado' y lo pasa a 'EnTransito'.
            2. Transiciona todas las muestras del remito de 'Empaquetada' a 'EnTransito'
               mediante el Patrón STATE.
            3. Registra el `EnvioLaboratorio` con el transportista asignado.
        """
        remito = self.obtener_remito_completo(remito_id)
        marca_temporal = fecha_hora_despacho or datetime.now().strftime(FORMATO_FECHA_HORA)

        estado_remito_previo = remito.estado
        remito.despachar()

        with self.conexion.transaccion():
            # 1. Actualizar estado del remito e historial
            self.logistica_dao.actualizar_estado_remito(
                remito_id=remito_id,
                estado_anterior=estado_remito_previo,
                estado_nuevo=remito.estado,
                fecha_hora=marca_temporal,
                observacion=observacion or "Despachado hacia laboratorio central.",
            )

            # 2. Transicionar todas las muestras contenidas (Patrón STATE)
            for muestra in remito.muestras:
                estado_previo = muestra.estado_actual
                muestra.despachar(fecha_hora=marca_temporal, observacion=observacion)
                ultimo_evento = muestra.historial[-1]
                self.muestra_dao.actualizar_estado(
                    muestra_id=muestra.id,
                    estado_anterior=estado_previo,
                    estado_nuevo=muestra.estado_actual,
                    fecha_hora=marca_temporal,
                    observacion=ultimo_evento.observacion or "",
                )

            # 3. Crear registro de envío
            envio = EnvioLaboratorio(
                id=None,
                remito_id=remito_id,
                transportista_id=transportista_id,
                fecha_hora_despacho=marca_temporal,
            )
            self.logistica_dao.crear_envio(envio)

        self.eventos.notificar(
            "REMITO_DESPACHADO",
            remito_id=remito_id,
            numero_remito=remito.numero_remito,
            cantidad_muestras=len(remito.muestras),
            fecha_hora=marca_temporal,
        )
        return self.logistica_dao.obtener_envio_por_remito(remito_id)

    # ==================================================================================
    # PROCESO 6: Recepción en Laboratorio y Verificación de Precinto Sanitario
    # ==================================================================================

    def recibir_remito_en_laboratorio(
        self,
        remito_id: int,
        estado_precinto: str,
        fecha_hora_recepcion: str | None = None,
        observaciones: str = "",
    ) -> RemitoBiologico:
        """
        Registra la recepción del envío en el laboratorio central y verifica el precinto:
            - Si `estado_precinto` es 'Intacto':
                El remito pasa a 'Recibido' y todas sus muestras pasan a 'Recibida'.
            - Si `estado_precinto` es 'Roto' o 'Violado' (Validación obligatoria del TP):
                El remito pasa a 'Rechazado', todas sus muestras pasan a 'Rechazada'
                documentando el motivo en la trazabilidad inmutable (impidiendo su
                análisis posterior) y se notifica a los observadores.
            - Libera la conservadora isotérmica para futuros envíos.
        """
        remito = self.obtener_remito_completo(remito_id)
        envio = self.logistica_dao.obtener_envio_por_remito(remito_id)
        if envio is None:
            raise ErrorValidacionNegocio(
                f"El remito '{remito.numero_remito}' no registra un envío en tránsito."
            )

        marca_temporal = fecha_hora_recepcion or datetime.now().strftime(FORMATO_FECHA_HORA)
        if marca_temporal < envio.fecha_hora_despacho:
            raise ErrorValidacionNegocio(
                "La fecha y hora de recepción no puede ser anterior a la de despacho."
            )

        estado_remito_previo = remito.estado
        estado_precinto_limpio = PrecintoSanitario.normalizar_estado(estado_precinto)
        remito.recibir(estado_precinto_limpio)

        muestras_rechazadas: list[str] = []

        with self.conexion.transaccion():
            # 1. Actualizar estado del precinto sanitario
            if remito.precinto_id is not None:
                self.logistica_dao.actualizar_estado_precinto(
                    remito.precinto_id, estado_precinto_limpio
                )

            # 2. Registrar llegada del envío
            self.logistica_dao.registrar_recepcion_envio(
                remito_id=remito_id,
                fecha_hora_recepcion=marca_temporal,
                observaciones=observaciones,
            )

            # 3. Actualizar estado del remito biológico
            self.logistica_dao.actualizar_estado_remito(
                remito_id=remito_id,
                estado_anterior=estado_remito_previo,
                estado_nuevo=remito.estado,
                fecha_hora=marca_temporal,
                observacion=(
                    f"Recepción en laboratorio con precinto '{estado_precinto_limpio}'. "
                    f"{observaciones}"
                ).strip(),
            )

            # 4. Evaluar cada muestra con el Patrón STATE (Recibida vs Rechazada)
            for muestra in remito.muestras:
                estado_previo = muestra.estado_actual
                muestra.recibir(
                    estado_precinto=estado_precinto_limpio,
                    fecha_hora=marca_temporal,
                    observacion=observaciones,
                )
                ultimo_evento = muestra.historial[-1]
                self.muestra_dao.actualizar_estado(
                    muestra_id=muestra.id,
                    estado_anterior=estado_previo,
                    estado_nuevo=muestra.estado_actual,
                    fecha_hora=marca_temporal,
                    observacion=ultimo_evento.observacion or "",
                    motivo_rechazo=muestra.motivo_rechazo,
                )
                if not muestra.esta_viable:
                    muestras_rechazadas.append(muestra.codigo_muestra)

            # 5. Liberar conservadora isotérmica
            self.logistica_dao.actualizar_disponibilidad_conservadora(
                conservadora_id=remito.conservadora_id, disponible=True
            )

        # Notificación desacoplada mediante Patrón OBSERVER
        if muestras_rechazadas:
            self.eventos.notificar(
                "MUESTRAS_RECHAZADAS_EN_RECEPCION",
                remito_id=remito_id,
                numero_remito=remito.numero_remito,
                estado_precinto=estado_precinto_limpio,
                codigos_muestras=muestras_rechazadas,
                fecha_hora=marca_temporal,
            )
        else:
            self.eventos.notificar(
                "REMITO_RECIBIDO_CONFORME",
                remito_id=remito_id,
                numero_remito=remito.numero_remito,
                fecha_hora=marca_temporal,
            )

        return self.obtener_remito_completo(remito_id)

    # ==================================================================================
    # Consultas de Apoyo Logístico
    # ==================================================================================

    def obtener_remito_completo(self, remito_id: int) -> RemitoBiologico:
        """
        Recupera un remito biológico hidratado con su conservadora, su precinto
        y todas las muestras alojadas (cargadas también dentro de la conservadora).
        """
        remito = self.logistica_dao.obtener_remito_por_id(remito_id)
        if remito is None:
            raise ErrorEntidadNoEncontrada("Remito biológico", remito_id)

        remito.conservadora = self.logistica_dao.obtener_conservadora_por_id(
            remito.conservadora_id
        )
        if remito.precinto_id is not None:
            remito.precinto = self.logistica_dao.obtener_precinto_por_id(remito.precinto_id)

        muestras = self.muestra_dao.listar_por_remito(remito_id)
        remito.muestras = muestras
        if remito.conservadora is not None:
            remito.conservadora.vaciar()
            for m in muestras:
                remito.conservadora.agregar_muestra(m)

        return remito

    def listar_muestras_extraidas_pendientes(
        self, clinica_id: int | None = None
    ) -> list[MuestraBiologica]:
        """
        Lista las muestras en estado 'Extraida' listas para ser empaquetadas.
        Si se indica `clinica_id`, filtra directamente en la capa DAO.
        """
        return self.muestra_dao.listar_extraidas_por_clinica(clinica_id)

    def listar_conservadoras_disponibles(self) -> list[ConservadoraIsotermica]:
        """Lista las conservadoras isotérmicas disponibles para usar."""
        return self.logistica_dao.listar_conservadoras_disponibles()

    def listar_remitos_por_estado(self, estado: str) -> list[RemitoBiologico]:
        """Lista los remitos biológicos en un estado determinado."""
        return self.logistica_dao.listar_remitos_por_estado(estado)

    def listar_todos_los_remitos(self) -> list[RemitoBiologico]:
        """Lista todos los remitos biológicos registrados con sus relaciones hidratadas."""
        remitos_base = self.logistica_dao.listar_todos_los_remitos()
        return [self.obtener_remito_completo(r.id) for r in remitos_base if r.id is not None]

    def listar_laboratorios(self) -> list[dict]:
        """Devuelve los laboratorios centrales registrados."""
        return self.logistica_dao.listar_laboratorios()

    def listar_transportistas(self) -> list[dict]:
        """Devuelve las empresas/choferes transportistas habilitados."""
        return self.logistica_dao.listar_transportistas()
