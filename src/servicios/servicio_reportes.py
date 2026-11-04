"""
Servicio de Reportes Gerenciales y Estadísticos (Fase 4 - Paso 4.2)
===================================================================

Centraliza la generación de los 5 reportes no triviales requeridos por el
Trabajo Práctico Integrador (Tema 2: Veterinaria - Red de Clínicas y Derivación
de Laboratorio), junto con utilidades nativas de exportación a formato CSV
(y soporte opcional para exportación a PDF si se dispone de ReportLab, según
el apunte de cátedra 'Reportes en Python.pdf').

Reportes implementados:
    1. Atenciones clínicas y derivaciones realizadas (por clínica, veterinario y período).
    2. Muestras biológicas rechazadas por fallas en el transporte (precinto Roto o Violado).
    3. Tratamientos aplicados y vacunas obligatorias pendientes por mascota.
    4. Facturación desglosada por clínica, estrategia de tarifa y servicios de laboratorio.
    5. Tiempo promedio de tránsito y procesamiento de muestras biológicas.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from src.persistencia.conexion_bd import ConexionBD
from src.persistencia.mascota_dao import MascotaDAO
from src.persistencia.muestra_dao import MuestraDAO


class ServicioReportes:
    """
    Servicio encargado de ejecutar consultas analíticas y de agregación sobre
    la base de datos para alimentar la vista de reportes y la exportación de informes.
    """

    def __init__(self, conexion: ConexionBD | None = None) -> None:
        self._conexion = conexion or ConexionBD.obtener_instancia()
        self._mascota_dao = MascotaDAO(self._conexion)
        self._muestra_dao = MuestraDAO(self._conexion)

    # ==================================================================================
    # REPORTE 1: Atenciones clínicas y derivaciones realizadas
    # ==================================================================================

    def reporte_atenciones_y_derivaciones(
        self,
        fecha_desde: str | None = None,
        fecha_hasta: str | None = None,
        clinica_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Genera el reporte estadístico y detallado de consultas médicas y órdenes de
        derivación emitidas hacia los laboratorios de la red.

        Permite filtrar opcionalmente por rango de fechas ('YYYY-MM-DD') y por clínica.

        Devuelve un diccionario con:
            - 'resumen_por_clinica': Totales agrupados por sede veterinaria.
            - 'detalle_atenciones': Listado enriquecido de cada consulta y sus derivaciones.
        """
        condiciones: list[str] = []
        parametros: list[Any] = []

        if fecha_desde:
            condiciones.append("substr(cm.fecha_hora_inicio, 1, 10) >= ?")
            parametros.append(fecha_desde)
        if fecha_hasta:
            condiciones.append("substr(cm.fecha_hora_inicio, 1, 10) <= ?")
            parametros.append(fecha_hasta)
        if clinica_id is not None:
            condiciones.append("cm.clinica_id = ?")
            parametros.append(clinica_id)

        clausula_where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

        sql_resumen = f"""
            SELECT
                cl.id AS clinica_id,
                cl.nombre AS clinica_nombre,
                COUNT(DISTINCT cm.id) AS total_consultas,
                COUNT(DISTINCT od.id) AS total_derivaciones,
                SUM(CASE WHEN od.prioridad = 'Urgente' THEN 1 ELSE 0 END) AS derivaciones_urgentes,
                COUNT(DISTINCT mb.id) AS total_muestras_extraidas,
                COALESCE(SUM(DISTINCT cm.costo_consulta), 0.0) AS monto_consultas
            FROM clinicas cl
            LEFT JOIN consultas_medicas cm ON cm.clinica_id = cl.id
            LEFT JOIN ordenes_derivacion od ON od.consulta_id = cm.id
            LEFT JOIN muestras_biologicas mb ON mb.orden_id = od.id
            {clausula_where}
            GROUP BY cl.id, cl.nombre
            HAVING COUNT(DISTINCT cm.id) > 0 OR ? IS NULL
            ORDER BY total_consultas DESC, cl.nombre ASC
        """
        filas_resumen = self._conexion.consultar_todos(
            sql_resumen, tuple(parametros) + (clinica_id,)
        )

        resumen_por_clinica = [
            {
                "clinica_id": int(f["clinica_id"]),
                "clinica_nombre": f["clinica_nombre"],
                "total_consultas": int(f["total_consultas"]),
                "total_derivaciones": int(f["total_derivaciones"]),
                "derivaciones_urgentes": int(f["derivaciones_urgentes"] or 0),
                "total_muestras_extraidas": int(f["total_muestras_extraidas"]),
                "monto_consultas": round(float(f["monto_consultas"] or 0.0), 2),
            }
            for f in filas_resumen
        ]

        sql_detalle = f"""
            SELECT
                cm.id AS consulta_id,
                cm.fecha_hora_inicio,
                cl.nombre AS clinica_nombre,
                v.apellido || ', ' || v.nombre AS veterinario_nombre,
                v.matricula AS veterinario_matricula,
                m.nombre AS mascota_nombre,
                ce.nombre AS especie_nombre,
                cli.apellido || ', ' || cli.nombre AS cliente_nombre,
                cm.motivo,
                cm.diagnostico,
                cm.costo_consulta,
                COUNT(DISTINCT od.id) AS cantidad_ordenes,
                GROUP_CONCAT(DISTINCT te.nombre) AS estudios_solicitados,
                COUNT(DISTINCT mb.id) AS cantidad_muestras
            FROM consultas_medicas cm
            JOIN clinicas cl ON cl.id = cm.clinica_id
            JOIN veterinarios v ON v.id = cm.veterinario_id
            JOIN mascotas m ON m.id = cm.mascota_id
            JOIN catalogo_especies ce ON ce.id = m.especie_id
            JOIN clientes cli ON cli.id = m.cliente_id
            LEFT JOIN ordenes_derivacion od ON od.consulta_id = cm.id
            LEFT JOIN catalogo_tipos_estudio te ON te.id = od.tipo_estudio_id
            LEFT JOIN muestras_biologicas mb ON mb.orden_id = od.id
            {clausula_where}
            GROUP BY cm.id
            ORDER BY cm.fecha_hora_inicio DESC
        """
        filas_detalle = self._conexion.consultar_todos(sql_detalle, tuple(parametros))

        detalle_atenciones = [
            {
                "consulta_id": int(f["consulta_id"]),
                "fecha_hora_inicio": f["fecha_hora_inicio"],
                "clinica_nombre": f["clinica_nombre"],
                "veterinario_nombre": f["veterinario_nombre"],
                "veterinario_matricula": f["veterinario_matricula"],
                "mascota_nombre": f["mascota_nombre"],
                "especie_nombre": f["especie_nombre"],
                "cliente_nombre": f["cliente_nombre"],
                "motivo": f["motivo"],
                "diagnostico": f["diagnostico"] or "Sin diagnóstico definitivo",
                "costo_consulta": round(float(f["costo_consulta"]), 2),
                "cantidad_ordenes": int(f["cantidad_ordenes"]),
                "estudios_solicitados": f["estudios_solicitados"] or "Ninguno",
                "cantidad_muestras": int(f["cantidad_muestras"]),
            }
            for f in filas_detalle
        ]

        return {
            "resumen_por_clinica": resumen_por_clinica,
            "detalle_atenciones": detalle_atenciones,
        }

    # ==================================================================================
    # REPORTE 2: Muestras biológicas rechazadas por fallas en el transporte
    # ==================================================================================

    def reporte_muestras_rechazadas_transporte(self) -> dict[str, Any]:
        """
        Genera el informe de auditoría de muestras biológicas rechazadas al arribar
        al laboratorio central debido a violación o rotura del precinto sanitario,
        o anomalías en la cadena de custodia/transporte.

        Devuelve un diccionario con:
            - 'total_rechazadas': Cantidad total de muestras rechazadas.
            - 'rechazos_por_estado_precinto': Conteo desglosado según estado del precinto ('Roto', 'Violado', etc.).
            - 'rechazos_por_clinica': Conteo agrupado por clínica emisora.
            - 'detalle_muestras': Listado completo con trazabilidad de remito, precinto, conservadora y transportista.
        """
        detalle = self._muestra_dao.listar_muestras_rechazadas_con_transporte()

        por_estado_precinto: dict[str, int] = {}
        por_clinica: dict[str, int] = {}

        for item in detalle:
            estado_precinto = item.get("precinto_estado") or "Sin Precinto"
            por_estado_precinto[estado_precinto] = por_estado_precinto.get(estado_precinto, 0) + 1

            clinica = item.get("clinica_origen") or "Desconocida"
            por_clinica[clinica] = por_clinica.get(clinica, 0) + 1

        return {
            "total_rechazadas": len(detalle),
            "rechazos_por_estado_precinto": por_estado_precinto,
            "rechazos_por_clinica": por_clinica,
            "detalle_muestras": detalle,
        }

    # ==================================================================================
    # REPORTE 3: Tratamientos aplicados y vacunas pendientes
    # ==================================================================================

    def reporte_tratamientos_y_vacunas_pendientes(
        self, fecha_referencia: str | None = None
    ) -> dict[str, Any]:
        """
        Genera el reporte clínico-sanitario que consolida:
            1. Todos los tratamientos farmacológicos y terapéuticos prescriptos.
            2. El control epidemiológico de vacunas obligatorias pendientes o vencidas
               para todas las mascotas registradas en la red.
        """
        sql_tratamientos = """
            SELECT
                t.id AS tratamiento_id,
                cm.fecha_hora_inicio AS fecha_consulta,
                cl.nombre AS clinica_nombre,
                v.apellido || ', ' || v.nombre AS veterinario_nombre,
                m.id AS mascota_id,
                m.nombre AS mascota_nombre,
                ce.nombre AS especie_nombre,
                cli.apellido || ', ' || cli.nombre AS cliente_nombre,
                t.descripcion,
                t.medicamento,
                t.dosis,
                t.duracion_dias
            FROM tratamientos t
            JOIN consultas_medicas cm ON cm.id = t.consulta_id
            JOIN clinicas cl ON cl.id = cm.clinica_id
            JOIN veterinarios v ON v.id = cm.veterinario_id
            JOIN mascotas m ON m.id = cm.mascota_id
            JOIN catalogo_especies ce ON ce.id = m.especie_id
            JOIN clientes cli ON cli.id = m.cliente_id
            ORDER BY cm.fecha_hora_inicio DESC, t.id ASC
        """
        filas_tratamientos = self._conexion.consultar_todos(sql_tratamientos)
        tratamientos_aplicados = [
            {
                "tratamiento_id": int(f["tratamiento_id"]),
                "fecha_consulta": f["fecha_consulta"],
                "clinica_nombre": f["clinica_nombre"],
                "veterinario_nombre": f["veterinario_nombre"],
                "mascota_id": int(f["mascota_id"]),
                "mascota_nombre": f["mascota_nombre"],
                "especie_nombre": f["especie_nombre"],
                "cliente_nombre": f["cliente_nombre"],
                "descripcion": f["descripcion"],
                "medicamento": f["medicamento"] or "No especificado",
                "dosis": f["dosis"] or "Según indicación",
                "duracion_dias": int(f["duracion_dias"]) if f["duracion_dias"] is not None else None,
            }
            for f in filas_tratamientos
        ]

        # Relevamiento de vacunas obligatorias pendientes/vencidas por mascota
        sql_mascotas = """
            SELECT
                m.id AS mascota_id,
                m.nombre AS mascota_nombre,
                ce.nombre AS especie_nombre,
                cli.apellido || ', ' || cli.nombre AS cliente_nombre,
                cli.telefono AS cliente_telefono
            FROM mascotas m
            JOIN catalogo_especies ce ON ce.id = m.especie_id
            JOIN clientes cli ON cli.id = m.cliente_id
            ORDER BY m.nombre ASC
        """
        filas_mascotas = self._conexion.consultar_todos(sql_mascotas)

        vacunas_pendientes_detalle: list[dict[str, Any]] = []
        mascotas_con_pendientes = 0

        for m in filas_mascotas:
            mascota_id = int(m["mascota_id"])
            pendientes = self._mascota_dao.obtener_vacunas_pendientes(
                mascota_id=mascota_id, fecha_referencia=fecha_referencia
            )
            if pendientes:
                mascotas_con_pendientes += 1
                for p in pendientes:
                    vacunas_pendientes_detalle.append(
                        {
                            "mascota_id": mascota_id,
                            "mascota_nombre": m["mascota_nombre"],
                            "especie_nombre": m["especie_nombre"],
                            "cliente_nombre": m["cliente_nombre"],
                            "cliente_telefono": m["cliente_telefono"],
                            "vacuna_id": p["vacuna_id"],
                            "nombre_vacuna": p["nombre_vacuna"],
                            "ultima_fecha_aplicacion": p.get("ultima_fecha_aplicacion") or "Sin registro",
                            "motivo_pendiente": p["motivo_pendiente"],
                        }
                    )

        return {
            "total_tratamientos": len(tratamientos_aplicados),
            "total_mascotas_con_vacunas_pendientes": mascotas_con_pendientes,
            "total_vacunas_pendientes": len(vacunas_pendientes_detalle),
            "tratamientos_aplicados": tratamientos_aplicados,
            "vacunas_pendientes": vacunas_pendientes_detalle,
        }

    # ==================================================================================
    # REPORTE 4: Facturación desglosada por clínica y servicios de laboratorio
    # ==================================================================================

    def reporte_facturacion_desglosada(
        self,
        fecha_desde: str | None = None,
        fecha_hasta: str | None = None,
    ) -> dict[str, Any]:
        """
        Genera el estado contable y financiero de los comprobantes emitidos,
        desglosando los ingresos por clínica veterinaria, por concepto facturado
        (Consultas, Estudios de Laboratorio, Tratamientos, Recargos y Bonificaciones)
        y por Estrategia de Tarifa aplicada (Patrón Strategy).
        """
        condiciones: list[str] = []
        parametros: list[Any] = []

        if fecha_desde:
            condiciones.append("substr(c.fecha_hora_emision, 1, 10) >= ?")
            parametros.append(fecha_desde)
        if fecha_hasta:
            condiciones.append("substr(c.fecha_hora_emision, 1, 10) <= ?")
            parametros.append(fecha_hasta)

        clausula_where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

        sql_por_clinica = f"""
            SELECT
                cl.id AS clinica_id,
                cl.nombre AS clinica_nombre,
                COUNT(DISTINCT c.id) AS cantidad_comprobantes,
                COALESCE(SUM(CASE WHEN dc.tipo_concepto = 'Consulta' THEN dc.monto ELSE 0.0 END), 0.0) AS subtotal_consultas,
                COALESCE(SUM(CASE WHEN dc.tipo_concepto = 'Laboratorio' THEN dc.monto ELSE 0.0 END), 0.0) AS subtotal_laboratorio,
                COALESCE(SUM(CASE WHEN dc.tipo_concepto IN ('Tratamiento', 'Vacuna') THEN dc.monto ELSE 0.0 END), 0.0) AS subtotal_otros_clinica,
                COALESCE(SUM(CASE WHEN dc.tipo_concepto = 'Recargo' THEN dc.monto ELSE 0.0 END), 0.0) AS total_recargos,
                COALESCE(SUM(CASE WHEN dc.tipo_concepto = 'Bonificacion' THEN dc.monto ELSE 0.0 END), 0.0) AS total_bonificaciones,
                COALESCE(SUM(dc.monto), 0.0) AS total_facturado
            FROM comprobantes c
            JOIN consultas_medicas cm ON cm.id = c.consulta_id
            JOIN clinicas cl ON cl.id = cm.clinica_id
            JOIN detalles_comprobante dc ON dc.comprobante_id = c.id
            {clausula_where}
            GROUP BY cl.id, cl.nombre
            ORDER BY total_facturado DESC
        """
        filas_clinica = self._conexion.consultar_todos(sql_por_clinica, tuple(parametros))

        desglose_por_clinica = [
            {
                "clinica_id": int(f["clinica_id"]),
                "clinica_nombre": f["clinica_nombre"],
                "cantidad_comprobantes": int(f["cantidad_comprobantes"]),
                "subtotal_consultas": round(float(f["subtotal_consultas"]), 2),
                "subtotal_laboratorio": round(float(f["subtotal_laboratorio"]), 2),
                "subtotal_otros_clinica": round(float(f["subtotal_otros_clinica"]), 2),
                "total_recargos": round(float(f["total_recargos"]), 2),
                "total_bonificaciones": round(float(f["total_bonificaciones"]), 2),
                "total_facturado": round(float(f["total_facturado"]), 2),
            }
            for f in filas_clinica
        ]

        sql_por_estrategia = f"""
            SELECT
                c.estrategia_tarifa,
                COUNT(c.id) AS cantidad_comprobantes,
                COALESCE(SUM(c.monto_total), 0.0) AS total_facturado
            FROM comprobantes c
            {clausula_where}
            GROUP BY c.estrategia_tarifa
            ORDER BY total_facturado DESC
        """
        filas_estrategia = self._conexion.consultar_todos(sql_por_estrategia, tuple(parametros))

        desglose_por_estrategia = [
            {
                "estrategia_tarifa": f["estrategia_tarifa"],
                "cantidad_comprobantes": int(f["cantidad_comprobantes"]),
                "total_facturado": round(float(f["total_facturado"]), 2),
            }
            for f in filas_estrategia
        ]

        total_general = round(sum(item["total_facturado"] for item in desglose_por_clinica), 2)
        total_laboratorio = round(sum(item["subtotal_laboratorio"] for item in desglose_por_clinica), 2)
        total_clinicas = round(
            sum(item["subtotal_consultas"] + item["subtotal_otros_clinica"] for item in desglose_por_clinica),
            2,
        )

        return {
            "total_general_facturado": total_general,
            "total_servicios_laboratorio": total_laboratorio,
            "total_servicios_clinica": total_clinicas,
            "desglose_por_clinica": desglose_por_clinica,
            "desglose_por_estrategia": desglose_por_estrategia,
        }

    # ==================================================================================
    # REPORTE 5: Tiempo promedio de tránsito y procesamiento de muestras
    # ==================================================================================

    def reporte_tiempos_transito_y_procesamiento(self) -> dict[str, Any]:
        """
        Calcula indicadores de desempeño logístico y bioquímico (SLA) a partir de las
        marcas de tiempo ISO-8601 (utilizando julian day `julianday()` en SQLite):
            - Tiempo de espera en clínica (Extracción -> Despacho).
            - Tiempo de tránsito en ruta (Despacho -> Recepción en laboratorio).
            - Tiempo de procesamiento analítico (Recepción -> Emisión de resultado).
            - Tiempo total del ciclo diagnóstico (Extracción -> Emisión de resultado).

        Devuelve métricas globales, promedios agrupados por clínica de origen y
        el detalle cronológico de cada muestra procesada o recibida.
        """
        sql_tiempos = """
            SELECT
                mb.id AS muestra_id,
                mb.codigo_muestra,
                tm.nombre AS tipo_muestra,
                te.nombre AS tipo_estudio,
                od.prioridad,
                cl.id AS clinica_id,
                cl.nombre AS clinica_nombre,
                mb.estado_actual,
                mb.fecha_hora_extraccion,
                el.fecha_hora_despacho,
                el.fecha_hora_recepcion,
                ra.fecha_hora_analisis,
                ROUND((julianday(el.fecha_hora_despacho) - julianday(mb.fecha_hora_extraccion)) * 24.0, 2)
                    AS horas_espera_clinica,
                ROUND((julianday(el.fecha_hora_recepcion) - julianday(el.fecha_hora_despacho)) * 24.0, 2)
                    AS horas_transito,
                ROUND((julianday(ra.fecha_hora_analisis) - julianday(el.fecha_hora_recepcion)) * 24.0, 2)
                    AS horas_procesamiento_lab,
                ROUND((julianday(ra.fecha_hora_analisis) - julianday(mb.fecha_hora_extraccion)) * 24.0, 2)
                    AS horas_ciclo_total
            FROM muestras_biologicas mb
            JOIN catalogo_tipos_muestra tm ON tm.id = mb.tipo_muestra_id
            JOIN ordenes_derivacion od ON od.id = mb.orden_id
            JOIN catalogo_tipos_estudio te ON te.id = od.tipo_estudio_id
            JOIN consultas_medicas cm ON cm.id = od.consulta_id
            JOIN clinicas cl ON cl.id = cm.clinica_id
            LEFT JOIN remitos_biologicos rb ON rb.id = mb.remito_id
            LEFT JOIN envios_laboratorio el ON el.remito_id = rb.id
            LEFT JOIN resultados_analisis ra ON ra.muestra_id = mb.id
            WHERE el.fecha_hora_despacho IS NOT NULL
            ORDER BY mb.fecha_hora_extraccion DESC
        """
        filas = self._conexion.consultar_todos(sql_tiempos)

        detalle_muestras: list[dict[str, Any]] = []
        transitos_validos: list[float] = []
        procesamientos_validos: list[float] = []
        ciclos_totales_validos: list[float] = []

        agrupado_clinica: dict[str, dict[str, list[float]]] = {}

        for f in filas:
            h_espera = float(f["horas_espera_clinica"]) if f["horas_espera_clinica"] is not None else None
            h_transito = float(f["horas_transito"]) if f["horas_transito"] is not None else None
            h_proc = float(f["horas_procesamiento_lab"]) if f["horas_procesamiento_lab"] is not None else None
            h_total = float(f["horas_ciclo_total"]) if f["horas_ciclo_total"] is not None else None

            clinica = f["clinica_nombre"]
            if clinica not in agrupado_clinica:
                agrupado_clinica[clinica] = {"transito": [], "procesamiento": [], "total": []}

            if h_transito is not None:
                transitos_validos.append(h_transito)
                agrupado_clinica[clinica]["transito"].append(h_transito)
            if h_proc is not None:
                procesamientos_validos.append(h_proc)
                agrupado_clinica[clinica]["procesamiento"].append(h_proc)
            if h_total is not None:
                ciclos_totales_validos.append(h_total)
                agrupado_clinica[clinica]["total"].append(h_total)

            detalle_muestras.append(
                {
                    "muestra_id": int(f["muestra_id"]),
                    "codigo_muestra": f["codigo_muestra"],
                    "tipo_muestra": f["tipo_muestra"],
                    "tipo_estudio": f["tipo_estudio"],
                    "prioridad": f["prioridad"],
                    "clinica_nombre": clinica,
                    "estado_actual": f["estado_actual"],
                    "fecha_hora_extraccion": f["fecha_hora_extraccion"],
                    "fecha_hora_despacho": f["fecha_hora_despacho"],
                    "fecha_hora_recepcion": f["fecha_hora_recepcion"],
                    "fecha_hora_analisis": f["fecha_hora_analisis"],
                    "horas_espera_clinica": h_espera,
                    "horas_transito": h_transito,
                    "horas_procesamiento_lab": h_proc,
                    "horas_ciclo_total": h_total,
                }
            )

        def _promedio(valores: list[float]) -> float:
            return round(sum(valores) / len(valores), 2) if valores else 0.0

        promedios_por_clinica = [
            {
                "clinica_nombre": nombre_clinica,
                "muestras_evaluadas": max(
                    len(metricas["transito"]),
                    len(metricas["procesamiento"]),
                    len(metricas["total"]),
                ),
                "promedio_horas_transito": _promedio(metricas["transito"]),
                "promedio_horas_procesamiento_lab": _promedio(metricas["procesamiento"]),
                "promedio_horas_ciclo_total": _promedio(metricas["total"]),
            }
            for nombre_clinica, metricas in agrupado_clinica.items()
        ]

        return {
            "promedio_global_horas_transito": _promedio(transitos_validos),
            "promedio_global_horas_procesamiento_lab": _promedio(procesamientos_validos),
            "promedio_global_horas_ciclo_total": _promedio(ciclos_totales_validos),
            "cantidad_muestras_en_transito_o_recibidas": len(detalle_muestras),
            "promedios_por_clinica": promedios_por_clinica,
            "detalle_tiempos_muestras": detalle_muestras,
        }

    # ==================================================================================
    # EXPORTACIÓN DE INFORMES (CSV Estándar - Apunte 'Reportes en Python.pdf')
    # ==================================================================================

    @staticmethod
    def exportar_a_csv(
        filas: list[dict[str, Any]],
        ruta_archivo: str | Path,
        columnas: list[str] | None = None,
    ) -> Path:
        """
        Exporta una colección tabular de diccionarios a un archivo CSV codificado en UTF-8,
        siguiendo las pautas del material de cátedra ('Reportes en Python.pdf').

        Parámetros:
            filas: Lista de diccionarios con los registros del reporte.
            ruta_archivo: Ruta de destino del archivo '.csv'.
            columnas: Orden explícito de encabezados (si es None, se infiere de la primera fila).

        Retorna:
            Objeto Path apuntando al archivo generado.
        """
        destino = Path(ruta_archivo)
        destino.parent.mkdir(parents=True, exist_ok=True)

        encabezados = columnas or (list(filas[0].keys()) if filas else [])

        with destino.open(mode="w", newline="", encoding="utf-8-sig") as archivo_csv:
            if encabezados:
                escritor = csv.DictWriter(
                    archivo_csv, fieldnames=encabezados, extrasaction="ignore"
                )
                escritor.writeheader()
                for fila in filas:
                    escritor.writerow(fila)

        return destino
