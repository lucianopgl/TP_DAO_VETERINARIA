"""
Capa de Servicios: ServicioClinica
==================================

Coordina los Procesos de Negocio Obligatorios 1, 2 y 3:
    1. Administrar clientes (ABMC y búsquedas).
    2. Administrar mascotas y sus historias clínicas (1 a 1, antecedentes, alergias y vacunas).
    3. Registrar consultas médicas, prescribir tratamientos, emitir órdenes de derivación
       de laboratorio y extraer muestras biológicas.

Validaciones de Negocio Garantizadas:
    - Toda mascota debe tener un responsable asociado (`ErrorMascotaSinResponsable`).
    - Evitar superposición de turnos en la agenda médica (`ErrorSuperposicionTurno`)
      evaluando matemáticamente el rango horario [inicio, inicio + duración).
    - Controlar el esquema de vacunas obligatorias al registrar atenciones
      (`ErrorVacunaObligatoriaFaltante` / alerta de vacunas pendientes o vencidas).
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from src.dominio.cliente import Cliente
from src.dominio.consulta_medica import FORMATO_FECHA_HORA, ConsultaMedica, OrdenDerivacion
from src.dominio.excepciones import (
    ErrorEntidadNoEncontrada,
    ErrorMascotaSinResponsable,
    ErrorSuperposicionTurno,
    ErrorVacunaObligatoriaFaltante,
)
from src.dominio.historia_clinica import HistoriaClinica, Tratamiento, VacunaAplicada
from src.dominio.mascota import Mascota
from src.dominio.muestra_biologica import MuestraBiologica
from src.persistencia.cliente_dao import ClienteDAO
from src.persistencia.conexion_bd import ConexionBD
from src.persistencia.consulta_dao import ConsultaDAO
from src.persistencia.mascota_dao import MascotaDAO
from src.persistencia.muestra_dao import MuestraDAO


class ServicioClinica:
    """
    Servicio de aplicación para la gestión clínica de pacientes, agenda médica
    y derivación inicial de muestras.
    """

    def __init__(
        self,
        conexion: ConexionBD | None = None,
        cliente_dao: ClienteDAO | None = None,
        mascota_dao: MascotaDAO | None = None,
        consulta_dao: ConsultaDAO | None = None,
        muestra_dao: MuestraDAO | None = None,
    ) -> None:
        self.conexion = conexion or ConexionBD.obtener_instancia()
        self.cliente_dao = cliente_dao or ClienteDAO(self.conexion)
        self.mascota_dao = mascota_dao or MascotaDAO(self.conexion)
        self.consulta_dao = consulta_dao or ConsultaDAO(self.conexion)
        self.muestra_dao = muestra_dao or MuestraDAO(self.conexion)

    # ==================================================================================
    # PROCESO 1: Administrar Clientes
    # ==================================================================================

    def registrar_cliente(
        self,
        dni: str,
        nombre: str,
        apellido: str,
        telefono: str,
        email: str | None = None,
        direccion: str | None = None,
    ) -> Cliente:
        """Valida y da de alta un nuevo cliente responsable."""
        cliente = Cliente(
            id=None,
            dni=dni,
            nombre=nombre,
            apellido=apellido,
            telefono=telefono,
            email=email,
            direccion=direccion,
        )
        self.cliente_dao.crear(cliente)
        return cliente

    def actualizar_cliente(self, cliente: Cliente) -> Cliente:
        """Actualiza los datos de un cliente existente verificando que exista."""
        if cliente.id is None or self.cliente_dao.obtener_por_id(cliente.id) is None:
            raise ErrorEntidadNoEncontrada("Cliente", cliente.id)
        self.cliente_dao.actualizar(cliente)
        return cliente

    def eliminar_cliente(self, cliente_id: int) -> None:
        """Elimina un cliente por ID si no posee mascotas asociadas."""
        if self.cliente_dao.obtener_por_id(cliente_id) is None:
            raise ErrorEntidadNoEncontrada("Cliente", cliente_id)
        self.cliente_dao.eliminar(cliente_id)

    def obtener_cliente(self, cliente_id: int) -> Cliente:
        """Obtiene un cliente por su ID o lanza ErrorEntidadNoEncontrada."""
        cliente = self.cliente_dao.obtener_por_id(cliente_id)
        if cliente is None:
            raise ErrorEntidadNoEncontrada("Cliente", cliente_id)
        return cliente

    def obtener_cliente_por_dni(self, dni: str) -> Cliente | None:
        """Busca un cliente por su DNI único."""
        return self.cliente_dao.obtener_por_dni(dni)

    def listar_clientes(self) -> list[Cliente]:
        """Devuelve el padrón completo de clientes ordenados por apellido y nombre."""
        return self.cliente_dao.listar_todos()

    def buscar_clientes(self, termino: str) -> list[Cliente]:
        """Busca clientes por DNI, nombre o apellido."""
        if not termino or not termino.strip():
            return self.listar_clientes()
        return self.cliente_dao.buscar(termino)

    # ==================================================================================
    # PROCESO 2: Administrar Mascotas e Historias Clínicas
    # ==================================================================================

    def registrar_mascota(
        self,
        nombre: str,
        especie_id: int,
        edad: int,
        sexo: str,
        cliente_id: int,
        raza: str | None = None,
        fecha_apertura_historia: str | None = None,
        antecedentes: str | None = None,
        alergias: str | None = None,
    ) -> Mascota:
        """
        Registra una nueva mascota y abre atómicamente su Historia Clínica (1 a 1).

        Validación de negocio:
            - Toda mascota debe tener un cliente responsable válido asociado.
        """
        if not cliente_id:
            raise ErrorMascotaSinResponsable()
        if self.cliente_dao.obtener_por_id(cliente_id) is None:
            raise ErrorEntidadNoEncontrada("Cliente responsable", cliente_id)

        mascota = Mascota(
            id=None,
            nombre=nombre,
            especie_id=especie_id,
            edad=edad,
            sexo=sexo,
            cliente_id=cliente_id,
            raza=raza,
        )
        fecha_apertura = fecha_apertura_historia or datetime.now().strftime("%Y-%m-%d")

        with self.conexion.transaccion():
            mascota_id = self.mascota_dao.crear(mascota, fecha_apertura_historia=fecha_apertura)
            if antecedentes or alergias:
                self.mascota_dao.actualizar_historia_clinica(mascota_id, antecedentes, alergias)

        return self.obtener_mascota(mascota_id)

    def actualizar_mascota(self, mascota: Mascota) -> Mascota:
        """Actualiza los datos de una mascota existente."""
        if mascota.id is None or self.mascota_dao.obtener_por_id(mascota.id) is None:
            raise ErrorEntidadNoEncontrada("Mascota", mascota.id)
        if not mascota.cliente_id:
            raise ErrorMascotaSinResponsable()
        if self.cliente_dao.obtener_por_id(mascota.cliente_id) is None:
            raise ErrorEntidadNoEncontrada("Cliente responsable", mascota.cliente_id)

        self.mascota_dao.actualizar(mascota)
        return self.obtener_mascota(mascota.id)

    def eliminar_mascota(self, mascota_id: int) -> None:
        """Elimina una mascota y su historia clínica si no registra consultas."""
        if self.mascota_dao.obtener_por_id(mascota_id) is None:
            raise ErrorEntidadNoEncontrada("Mascota", mascota_id)
        self.mascota_dao.eliminar(mascota_id)

    def obtener_mascota(self, mascota_id: int) -> Mascota:
        """Recupera una mascota con su especie y su cliente responsable."""
        mascota = self.mascota_dao.obtener_por_id(mascota_id)
        if mascota is None:
            raise ErrorEntidadNoEncontrada("Mascota", mascota_id)
        mascota.cliente = self.cliente_dao.obtener_por_id(mascota.cliente_id)
        return mascota

    def listar_mascotas(self) -> list[Mascota]:
        """Lista todas las mascotas registradas en la red."""
        return self.mascota_dao.listar_todas()

    def listar_mascotas_por_cliente(self, cliente_id: int) -> list[Mascota]:
        """Lista las mascotas asociadas a un cliente responsable."""
        return self.mascota_dao.listar_por_cliente(cliente_id)

    def obtener_historia_clinica_completa(self, mascota_id: int) -> HistoriaClinica:
        """
        Recupera la Historia Clínica integral de la mascota, incluyendo:
            - Datos de apertura, antecedentes y alergias.
            - Todas las vacunas aplicadas.
            - Todos los tratamientos prescriptos en sus consultas médicas.
        """
        historia = self.mascota_dao.obtener_historia_clinica(mascota_id)
        if historia is None:
            raise ErrorEntidadNoEncontrada("Historia Clínica de mascota", mascota_id)

        historia.tratamientos = self.consulta_dao.listar_tratamientos_por_mascota(mascota_id)
        return historia

    def actualizar_historia_clinica(
        self,
        mascota_id: int,
        antecedentes: str | None,
        alergias: str | None,
    ) -> HistoriaClinica:
        """Actualiza los antecedentes y alergias de la mascota."""
        if self.mascota_dao.obtener_por_id(mascota_id) is None:
            raise ErrorEntidadNoEncontrada("Mascota", mascota_id)
        self.mascota_dao.actualizar_historia_clinica(mascota_id, antecedentes, alergias)
        return self.obtener_historia_clinica_completa(mascota_id)

    def aplicar_vacuna(
        self,
        mascota_id: int,
        vacuna_id: int,
        fecha_aplicacion: str | None = None,
        consulta_id: int | None = None,
    ) -> VacunaAplicada:
        """Registra una dosis de vacuna aplicada a la mascota."""
        if self.mascota_dao.obtener_por_id(mascota_id) is None:
            raise ErrorEntidadNoEncontrada("Mascota", mascota_id)

        fecha = fecha_aplicacion or datetime.now().strftime("%Y-%m-%d")
        vacuna = VacunaAplicada(
            id=None,
            mascota_id=mascota_id,
            vacuna_id=vacuna_id,
            fecha_aplicacion=fecha,
            consulta_id=consulta_id,
        )
        self.mascota_dao.registrar_vacuna_aplicada(vacuna)
        return vacuna

    def controlar_esquema_vacunacion(
        self,
        mascota_id: int,
        fecha_referencia: str | None = None,
        exigir_al_dia: bool = False,
    ) -> list[dict]:
        """
        Validación de negocio obligatoria:
            "Controlar esquema de vacunas obligatorias al registrar atenciones."

        Compara el calendario obligatorio de la especie de la mascota con las dosis
        efectivamente aplicadas.

        Args:
            mascota_id: Identificador de la mascota a evaluar.
            fecha_referencia: Fecha ISO 'YYYY-MM-DD' de control (por defecto hoy).
            exigir_al_dia: Si es True y existen vacunas obligatorias faltantes o
                vencidas, lanza `ErrorVacunaObligatoriaFaltante`.

        Returns:
            Lista de vacunas obligatorias pendientes o vencidas.
        """
        if self.mascota_dao.obtener_por_id(mascota_id) is None:
            raise ErrorEntidadNoEncontrada("Mascota", mascota_id)

        pendientes = self.mascota_dao.obtener_vacunas_pendientes(
            mascota_id, fecha_referencia=fecha_referencia
        )
        if exigir_al_dia and pendientes:
            nombres = [f"{v['nombre_vacuna']} ({v['motivo_pendiente']})" for v in pendientes]
            raise ErrorVacunaObligatoriaFaltante(nombres)
        return pendientes

    # ==================================================================================
    # PROCESO 3: Consultas Médicas, Agenda y Órdenes de Derivación
    # ==================================================================================

    def verificar_disponibilidad_veterinario(
        self,
        veterinario_id: int,
        fecha_hora_inicio: str,
        duracion_minutos: int = 30,
        excluir_consulta_id: int | None = None,
    ) -> None:
        """
        Validación de negocio obligatoria:
            "Evitar superposición de turnos en la agenda médica."

        Verifica matemáticamente que el intervalo [inicio, inicio + duración) no se
        solape con ninguna otra consulta del mismo veterinario en esa fecha.

        Raises:
            ErrorSuperposicionTurno: Si existe intersección horaria con otro turno.
        """
        ConsultaMedica.validar_rango_horario(fecha_hora_inicio, duracion_minutos)
        fecha_dia = fecha_hora_inicio[:10]
        turnos_del_dia = self.consulta_dao.listar_por_veterinario_y_fecha(veterinario_id, fecha_dia)

        for turno in turnos_del_dia:
            if excluir_consulta_id is not None and turno.id == excluir_consulta_id:
                continue
            if turno.se_superpone_con(fecha_hora_inicio, duracion_minutos):
                raise ErrorSuperposicionTurno(turno.fecha_hora_inicio, turno.fecha_hora_fin)

    def registrar_consulta_medica(
        self,
        mascota_id: int,
        clinica_id: int,
        veterinario_id: int,
        fecha_hora_inicio: str,
        motivo: str,
        duracion_minutos: int = 30,
        diagnostico: str | None = None,
        costo_consulta: float = 0.0,
        tratamientos: Iterable[Tratamiento] | None = None,
        vacunas_aplicadas_ids: Iterable[int] | None = None,
        exigir_vacunas_al_dia: bool = False,
    ) -> tuple[ConsultaMedica, list[dict]]:
        """
        Registra una consulta médica completa dentro de una única transacción atómica:
            1. Verifica que la mascota exista.
            2. Valida que el veterinario no tenga superposición de turnos.
            3. Si se exigen vacunas al día (y no se están aplicando en este acto),
               controla el esquema obligatorio antes de proceder.
            4. Guarda la consulta y sus tratamientos prescriptos.
            5. Registra las vacunas aplicadas durante la consulta (si las hubiera).
            6. Evalúa y devuelve el estado final del esquema de vacunación de la mascota.

        Returns:
            Tupla (consulta_creada, vacunas_obligatorias_pendientes).
        """
        if self.mascota_dao.obtener_por_id(mascota_id) is None:
            raise ErrorEntidadNoEncontrada("Mascota", mascota_id)

        # 1. Validación de no superposición horaria
        self.verificar_disponibilidad_veterinario(
            veterinario_id=veterinario_id,
            fecha_hora_inicio=fecha_hora_inicio,
            duracion_minutos=duracion_minutos,
        )

        fecha_atencion = fecha_hora_inicio[:10]
        lista_tratamientos = list(tratamientos) if tratamientos else []
        lista_vacunas_ids = list(vacunas_aplicadas_ids) if vacunas_aplicadas_ids else []

        with self.conexion.transaccion():
            consulta = ConsultaMedica(
                id=None,
                mascota_id=mascota_id,
                clinica_id=clinica_id,
                veterinario_id=veterinario_id,
                fecha_hora_inicio=fecha_hora_inicio,
                duracion_minutos=duracion_minutos,
                motivo=motivo,
                diagnostico=diagnostico,
                costo_consulta=costo_consulta,
                tratamientos=lista_tratamientos,
            )
            consulta_id = self.consulta_dao.crear(consulta)

            # Si se aplicaron vacunas en la misma consulta, se registran vinculadas a ella
            for vacuna_id in lista_vacunas_ids:
                self.aplicar_vacuna(
                    mascota_id=mascota_id,
                    vacuna_id=vacuna_id,
                    fecha_aplicacion=fecha_atencion,
                    consulta_id=consulta_id,
                )

            # Control de esquema de vacunas obligatorias al registrar la atención
            vacunas_pendientes = self.controlar_esquema_vacunacion(
                mascota_id=mascota_id,
                fecha_referencia=fecha_atencion,
                exigir_al_dia=exigir_vacunas_al_dia,
            )

        consulta_guardada = self.consulta_dao.obtener_por_id(consulta_id)
        return consulta_guardada, vacunas_pendientes

    def obtener_consulta(self, consulta_id: int) -> ConsultaMedica:
        """Recupera una consulta médica con sus tratamientos y órdenes."""
        consulta = self.consulta_dao.obtener_por_id(consulta_id)
        if consulta is None:
            raise ErrorEntidadNoEncontrada("Consulta médica", consulta_id)
        return consulta

    def listar_consultas_por_mascota(self, mascota_id: int) -> list[ConsultaMedica]:
        """Lista todas las consultas médicas de un paciente."""
        return self.consulta_dao.listar_por_mascota(mascota_id)

    def emitir_orden_derivacion(
        self,
        consulta_id: int,
        tipo_estudio_id: int,
        indicaciones: str | None = None,
        prioridad: str = "Normal",
        fecha_hora_emision: str | None = None,
    ) -> OrdenDerivacion:
        """
        Emite una orden de derivación de laboratorio en el marco de una consulta médica.
        """
        if self.consulta_dao.obtener_por_id(consulta_id) is None:
            raise ErrorEntidadNoEncontrada("Consulta médica", consulta_id)

        fecha_emision = fecha_hora_emision or datetime.now().strftime(FORMATO_FECHA_HORA)
        orden = OrdenDerivacion(
            id=None,
            consulta_id=consulta_id,
            tipo_estudio_id=tipo_estudio_id,
            fecha_hora_emision=fecha_emision,
            indicaciones=indicaciones,
            prioridad=prioridad,
        )
        orden_id = self.consulta_dao.crear_orden_derivacion(orden)
        return self.consulta_dao.obtener_orden_por_id(orden_id)

    def extraer_muestra_biologica(
        self,
        orden_id: int,
        codigo_muestra: str,
        tipo_muestra_id: int,
        fecha_hora_extraccion: str | None = None,
    ) -> MuestraBiologica:
        """
        Registra la extracción física de una muestra biológica para una orden de derivación.
        Inicia el ciclo de vida de la muestra en estado 'Extraida' con su primer registro
        inmutable de trazabilidad.
        """
        if self.consulta_dao.obtener_orden_por_id(orden_id) is None:
            raise ErrorEntidadNoEncontrada("Orden de derivación", orden_id)

        fecha_extraccion = fecha_hora_extraccion or datetime.now().strftime(FORMATO_FECHA_HORA)
        muestra = MuestraBiologica(
            id=None,
            codigo_muestra=codigo_muestra,
            orden_id=orden_id,
            tipo_muestra_id=tipo_muestra_id,
            fecha_hora_extraccion=fecha_extraccion,
        )
        muestra_id = self.muestra_dao.crear(muestra)
        return self.muestra_dao.obtener_por_id(muestra_id)

    # ==================================================================================
    # Consultas de Catálogos y Entidades de la Red (delegadas en la capa DAO)
    # ==================================================================================

    def listar_especies(self) -> list[dict]:
        """Devuelve el catálogo de especies animales."""
        return self.mascota_dao.listar_especies()

    def listar_clinicas(self) -> list[dict]:
        """Devuelve las clínicas veterinarias de la red."""
        return self.consulta_dao.listar_clinicas()

    def listar_veterinarios(self) -> list[dict]:
        """Devuelve el plantel de profesionales veterinarios."""
        return self.consulta_dao.listar_veterinarios()

    def listar_tipos_estudio(self) -> list[dict]:
        """Devuelve el catálogo de estudios de laboratorio disponibles."""
        return self.consulta_dao.listar_tipos_estudio()

    def listar_tipos_muestra(self) -> list[dict]:
        """Devuelve el catálogo de tipos de muestra biológica."""
        return self.muestra_dao.listar_tipos_muestra()

    def listar_catalogo_vacunas(self, especie_id: int | None = None) -> list[dict]:
        """Devuelve el catálogo de vacunas (opcionalmente filtrado por especie)."""
        return self.mascota_dao.listar_catalogo_vacunas(especie_id)
