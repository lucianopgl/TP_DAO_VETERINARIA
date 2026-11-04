---
name: gui-veterinaria
description: >-
  Guía arquitectónica POO y Clean Code para implementar la interfaz gráfica en CustomTkinter
  del sistema veterinario (Cátedra DAO - UTN FRC). Activar cuando el usuario solicite diseñar,
  programar o probar vistas, formularios, componentes visuales o el punto de entrada main.py.
---

# Skill: Construcción de Interfaz Gráfica POO (CustomTkinter)

## 1. Principios de Diseño POO en la Capa de Presentación (Prioridad Máxima)
1. **Prohibido crear Clases Dios (God Objects):**
   - Cada módulo funcional debe vivir en su propia clase dentro de `src/interfaz/vistas/` heredando de `ctk.CTkFrame` (**Alta Cohesión / SRP**).
   - Evitar métodos extensos; separar la construcción de widgets (`_construir_ui`) de los manejadores de eventos (`_al_guardar`, `_al_seleccionar`) y del refresco de datos (`refrescar_datos`).
2. **Bajo Acoplamiento e Inyección de Dependencias (DIP):**
   - Las vistas reciben por constructor únicamente las instancias de servicios que necesitan (`ServicioClinica`, `ServicioLogistica`, `ServicioLaboratorio` o `ServicioReportes`).
   - **Prohibido:** Importar `sqlite3`, escribir SQL o instanciar `ConexionBD` / DAOs dentro de `src/interfaz/`.
3. **Aplicación estricta de DRY en Componentes Visuales:**
   - Extraer widgets repetidos (tablas estilizadas con `ttk.Treeview`, tarjetas de resumen KPI, selectores mapeados `id <-> texto` y diálogos de alerta) en `src/interfaz/componentes/` para no duplicar código de configuración visual en cada vista.
4. **Patrones GoF Visibles e Interactivos en la Interfaz:**
   - **Observer (`src/patrones/observador_eventos.py`):** La ventana principal (`app.py`) o un componente de notificaciones debe implementar la interfaz `Observador` y suscribirse al `SujetoEventos` compartido por `ServicioLogistica` y `ServicioLaboratorio` para mostrar alertas en vivo cuando ocurran `MUESTRAS_RECHAZADAS_EN_RECEPCION`, `REMITO_DESPACHADO`, `REMITO_RECIBIDO_CONFORME` o `RESULTADO_ANALISIS_LISTO`.
   - **Strategy (`src/patrones/estrategia_facturacion.py`):** En la vista de facturación, permitir seleccionar entre `'Tarifa Estándar'`, `'Tarifa Urgencia'` y `'Tarifa Convenio Red'`, previsualizando en pantalla el desglose polimórfico devuelto por `servicio_laboratorio.calcular_liquidacion_consulta(consulta_id, estrategia)`.
   - **State (`src/patrones/estado_muestra.py`):** Mostrar claramente el `estado_actual` de cada `MuestraBiologica` y permitir consultar su `historial` inmutable de trazabilidad (`RegistroTrazabilidad`).
   - **Iterator (`src/patrones/iterador_muestras.py`):** Mostrar la ocupación de cada `ConservadoraIsotermica` (`cantidad_muestras / capacidad_maxima`) y las muestras contenidas.

---

## 2. Estructura de Archivos Objetivo
```text
proyecto_veterinaria/
├── main.py                              # Punto de entrada: inicializa BD, servicios y lanza App
└── src/interfaz/
    ├── __init__.py
    ├── app.py                           # Ventana principal, barra lateral de navegación y Observador UI
    ├── componentes/
    │   ├── __init__.py
    │   ├── tabla.py                     # Tabla reutilizable (Treeview estilizado con scrollbars)
    │   └── alertas.py                   # Manejador centralizado de ErrorVeterinaria y popups
    └── vistas/
        ├── __init__.py
        ├── vista_clientes.py            # Proceso 1: ABMC y buscador de Clientes
        ├── vista_mascotas.py            # Proceso 2: Mascotas, Historia Clínica 1:1 y Vacunas
        ├── vista_consultas.py           # Proceso 3: Agenda/Turnos, Tratamientos, Órdenes y Extracción
        ├── vista_logistica.py           # Procesos 4, 5 y 6: Conservadoras, Remitos, Despacho y Recepción
        ├── vista_laboratorio.py         # Proceso 7: Resultados bioquímicos y Facturación (Strategy)
        └── vista_reportes.py            # Los 5 reportes no triviales + exportación a CSV
```

---

## 3. Contrato de Métodos de la Capa de Servicios (Referencia Rápida)

### `ServicioClinica` (`src/servicios/servicio_clinica.py`)
- **Proceso 1 (Clientes):**
  - `registrar_cliente(dni, nombre, apellido, telefono, email=None, direccion=None) -> Cliente`
  - `actualizar_cliente(cliente: Cliente) -> Cliente`
  - `eliminar_cliente(cliente_id: int) -> None`
  - `listar_clientes() -> list[Cliente]` | `buscar_clientes(termino: str) -> list[Cliente]`
- **Proceso 2 (Mascotas, Historia Clínica 1:1 y Vacunas):**
  - `registrar_mascota(nombre, especie_id, edad, sexo, cliente_id, raza=None, fecha_apertura_historia=None, antecedentes=None, alergias=None) -> Mascota`
  - `actualizar_mascota(mascota: Mascota) -> Mascota` | `eliminar_mascota(mascota_id: int) -> None`
  - `listar_mascotas() -> list[Mascota]` | `listar_mascotas_por_cliente(cliente_id: int) -> list[Mascota]`
  - `obtener_historia_clinica_completa(mascota_id: int) -> HistoriaClinica`
  - `actualizar_historia_clinica(mascota_id, antecedentes, alergias) -> HistoriaClinica`
  - `aplicar_vacuna(mascota_id, vacuna_id, fecha_aplicacion=None, consulta_id=None) -> VacunaAplicada`
  - `controlar_esquema_vacunacion(mascota_id, fecha_referencia=None, exigir_al_dia=False) -> list[dict]`
- **Proceso 3 (Consultas, Agenda sin superposición, Órdenes y Muestras):**
  - `registrar_consulta_medica(mascota_id, clinica_id, veterinario_id, fecha_hora_inicio, motivo, duracion_minutos=30, diagnostico=None, costo_consulta=0.0, tratamientos=None, vacunas_aplicadas_ids=None, exigir_vacunas_al_dia=False) -> tuple[ConsultaMedica, list[dict]]`
  - `listar_consultas_por_mascota(mascota_id: int) -> list[ConsultaMedica]`
  - `emitir_orden_derivacion(consulta_id, tipo_estudio_id, indicaciones=None, prioridad="Normal", fecha_hora_emision=None) -> OrdenDerivacion`
  - `extraer_muestra_biologica(orden_id, codigo_muestra, tipo_muestra_id, fecha_hora_extraccion=None) -> MuestraBiologica`
- **Catálogos para ComboBoxes:**
  - `listar_especies()`, `listar_clinicas()`, `listar_veterinarios()`, `listar_tipos_estudio()`, `listar_tipos_muestra()`, `listar_catalogo_vacunas(especie_id=None)`

### `ServicioLogistica` (`src/servicios/servicio_logistica.py`)
- **Proceso 4 (Empaquetado en Conservadora con Remito y Precinto):**
  - `empaquetar_muestras(numero_remito, clinica_origen_id, laboratorio_destino_id, conservadora_id, numero_serie_precinto, muestras_ids, fecha_hora=None, observacion="") -> RemitoBiologico`
- **Proceso 5 (Despacho a Laboratorio):**
  - `despachar_remito(remito_id, transportista_id, fecha_hora_despacho=None, observacion="") -> EnvioLaboratorio`
- **Proceso 6 (Recepción y Verificación de Precinto):**
  - `recibir_remito_en_laboratorio(remito_id, estado_precinto, fecha_hora_recepcion=None, observaciones="") -> RemitoBiologico` (donde `estado_precinto` es `'Intacto'`, `'Roto'` o `'Violado'`)
- **Consultas de apoyo:**
  - `listar_muestras_extraidas_pendientes(clinica_id=None)`, `listar_conservadoras_disponibles()`, `listar_remitos_por_estado(estado)`, `listar_todos_los_remitos()`, `listar_laboratorios()`, `listar_transportistas()`

### `ServicioLaboratorio` (`src/servicios/servicio_laboratorio.py`)
- **Proceso 7A (Resultados de Análisis):**
  - `registrar_resultado_analisis(muestra_id, profesional_laboratorio_id, valores_medidos, conclusion, costo_analisis=None, fecha_hora_analisis=None, observacion="") -> ResultadoAnalisis`
  - `listar_muestras_recibidas_pendientes_analisis() -> list[MuestraBiologica]`
  - `listar_profesionales_laboratorio() -> list[dict]`
- **Proceso 7B (Facturación con Patrón Strategy):**
  - `calcular_liquidacion_consulta(consulta_id, estrategia=None) -> LiquidacionFactura`
  - `emitir_comprobante_atencion(consulta_id, numero_comprobante, estrategia=None, fecha_hora_emision=None) -> ComprobanteAtencion`
  - `listar_comprobantes() -> list[ComprobanteAtencion]`

### `ServicioReportes` (`src/servicios/servicio_reportes.py`)
- `reporte_atenciones_y_derivaciones(fecha_desde=None, fecha_hasta=None, clinica_id=None) -> dict`
- `reporte_muestras_rechazadas_transporte() -> dict`
- `reporte_tratamientos_y_vacunas_pendientes(fecha_referencia=None) -> dict`
- `reporte_facturacion_desglosada(fecha_desde=None, fecha_hasta=None) -> dict`
- `reporte_tiempos_transito_y_procesamiento() -> dict`
- `exportar_a_csv(filas, ruta_archivo, columnas=None) -> Path`

---

## 4. Protocolo de Manejo de Excepciones en la UI
Toda acción disparada por un botón de formulario debe envolverse mediante un manejador centralizado:
```python
try:
    # Acción del servicio
    ...
except ErrorDatosInvalidos as error:
    # Mostrar error.mensaje indicando el campo error.campo
    ...
except ErrorVeterinaria as error:
    # Mostrar error.mensaje amigable al usuario (incluye superposición horaria,
    # vacunas faltantes, capacidad de conservadora, transición State inválida o integridad BD)
    ...
```

---

## 5. Metodología de Implementación Paso a Paso (Interactiva)
Para mantener control de calidad y permitir validación continua del usuario, construir en **4 etapas incrementales**:
1. **Etapa 1 (Base + Proceso 1):** Crear `src/interfaz/componentes/` (`tabla.py`, `alertas.py`), `src/interfaz/app.py` (navegación lateral + barra de notificaciones `Observador`), `src/interfaz/vistas/vista_clientes.py` y `main.py`. Verificar que la app inicie y opere el ABMC de clientes.
2. **Etapa 2 (Procesos 2 y 3):** Implementar `vista_mascotas.py` (con Historia Clínica 1:1 y control de vacunas) y `vista_consultas.py` (agenda con validación de superposición, tratamientos, órdenes y extracción de muestras).
3. **Etapa 3 (Procesos 4, 5, 6 y 7):** Implementar `vista_logistica.py` (empaquetado en conservadora con Iterator, precinto, despacho y recepción con rechazo automático si precinto Roto/Violado) y `vista_laboratorio.py` (carga de resultados con State y emisión de comprobantes con Strategy).
4. **Etapa 4 (Reportes y Cierre):** Implementar `vista_reportes.py` (los 5 reportes gerenciales/sanitarios con exportación a CSV) y ejecutar `pytest` para confirmar que toda la suite sigue en verde.
