# 🐾 Sistema de Gestión Veterinaria y Derivación de Laboratorio

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![SQLite STRICT](https://img.shields.io/badge/sqlite-3.37+%20STRICT-003B57.svg)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/tests-89%20passing-brightgreen.svg)](tests/)
[![Patrones GoF](https://img.shields.io/badge/GoF-State%20%7C%20Strategy%20%7C%20Iterator%20%7C%20Observer%20%7C%20Singleton%20%7C%20DAO-purple.svg)](src/patrones/)
[![GUI](https://img.shields.io/badge/GUI-CustomTkinter-blueviolet.svg)](src/interfaz/)

Sistema integral orientado a objetos con arquitectura en 5 capas y persistencia relacional para la administración de una red de clínicas veterinarias, atención clínica de pacientes y gestión logística con cadena de frío, custodia sanitaria y trazabilidad inmutable para la derivación de muestras biológicas hacia un laboratorio central de análisis.

> **Proyecto Integrador de Cátedra:** Desarrollo de Aplicaciones con Objetos (DAO) — Ingeniería en Sistemas de Información (UTN FRC — Ciclo Lectivo 2026).  
> **Tema:** Tema 2 — Veterinaria: Red de Clínicas y Derivación de Laboratorio.  
> **Grupo:** Grupo 089 (G-089)

### 👥 Integrantes del Grupo 089

| Legajo | Nombre y Apellido |
| :---: | :--- |
| **85656** | Bertoni Rocio |
| **90074** | Simonetti Franco |
| **90175** | Ojea Nicolas |
| **94030** | Diaz Tomás Agustín |
| **95738** | Paglino Luciano Ivo |

---

## 📌 Objetivos y Alcance Funcional

El sistema modela la operativa diaria de una red veterinaria y resuelve integralmente los **7 procesos obligatorios** del dominio, sus **validaciones de negocio críticas** y los **5 reportes gerenciales/sanitarios no triviales**:

1. **Gestión Clínica, Pacientes e Historia Clínica Única (Procesos 1, 2 y 3):**
   - Administración completa (altas, modificaciones, bajas y búsquedas multicriterio en vivo) de **Clientes** responsables y **Mascotas** tipificadas por catálogo de especies (*Canino, Felino, Ave, Roedor, Reptil*).
   - **Regla de Negocio — Responsable Obligatorio:** Ninguna mascota puede registrarse sin un cliente responsable asociado (`ErrorMascotaSinResponsable` + restricción `FOREIGN KEY NOT NULL`).
   - **Historia Clínica Digital (`1 a 1`):** Apertura atómica junto con el alta de la mascota, registrando antecedentes, alergias, tratamientos farmacológicos y control inteligente de **vacunas obligatorias** pendientes o vencidas por especie.
   - **Regla de Negocio — No Superposición de Turnos:** Control matemático de intervalos horarios semiabiertos `[inicio, inicio + duración)` por veterinario (`ErrorSuperposicionTurno`) y restricción `UNIQUE(veterinario_id, fecha_hora_inicio)`.

2. **Logística Sanitaria, Cadena de Frío y Trazabilidad Inmutable (Procesos 4, 5 y 6):**
   - Emisión de **Órdenes de Derivación** (`Normal` / `Urgente`) y extracción de **Muestras Biológicas** identificadas unívocamente.
   - Empaquetado en **Conservadoras Isotérmicas** validando su capacidad física máxima (`ErrorCapacidadConservadoraExcedida`), emisión de **Remitos Biológicos** y sellado con **Precintos Sanitarios** numerados (`Intacto` | `Roto` | `Violado`).
   - **Regla de Negocio — Trazabilidad Inmutable:** Ciclo de vida controlado mediante el patrón **State** (`Extraida` → `Empaquetada` → `EnTransito` → `Recibida` → `Analizada` / `Rechazada`). Cada cambio de estado queda asentado en objetos de valor inmutables (`@dataclass(frozen=True)`) y tablas de auditoría protegidas por **4 Triggers SQLite** (`BEFORE UPDATE` / `BEFORE DELETE` con `RAISE(ABORT)`).
   - **Regla de Negocio — Bloqueo por Precinto Vulnerado:** Si en la recepción del laboratorio el precinto sanitario arriba `Roto` o `Violado`, el remito y todas sus muestras pasan automáticamente a estado terminal `Rechazado`/`Rechazada` documentando el motivo e impidiendo de forma polimórfica su posterior análisis bioquímico.
   - **Recorrido con Patrón Iterator:** Recorrido desacoplado de conservadoras con `IteradorMuestras` e `IteradorMuestrasFiltradas` (filtrado de muestras viables sin romper el encapsulamiento).

3. **Resultados Bioquímicos y Facturación Polimórfica (Proceso 7):**
   - Carga de **Resultados de Análisis** firmados por bioquímicos matriculados (habilitada exclusivamente para muestras en estado `Recibida`).
   - Emisión de **Comprobantes de Atención** (`cabecera` y `detalles` desglosados) aplicando dinámicamente estrategias arancelarias intercambiables (**Patrón Strategy**: `TarifaEstandar`, `TarifaUrgenciaLaboratorio` `+30%`, `TarifaConvenioRed` `-15%`).

4. **Reportes Gerenciales y Exportación CSV:**
   - **Reporte 1:** Atenciones clínicas y derivaciones realizadas por período y clínica.
   - **Reporte 2:** Muestras biológicas rechazadas por fallas en el transporte (con detalle de precinto, conservadora y transportista).
   - **Reporte 3:** Tratamientos aplicados y vacunas obligatorias pendientes o vencidas por mascota.
   - **Reporte 4:** Facturación desglosada por clínica, laboratorio, aranceles y estrategias aplicadas.
   - **Reporte 5:** Tiempos promedio (SLA) de permanencia en clínica, tránsito logístico y procesamiento bioquímico.
   - **Exportación Flexible a CSV:** Exportación de la pestaña actual (con tablas principal y secundaria) o exportación del paquete completo de los 5 reportes en lote.

---

## 🏗️ Arquitectura del Sistema (5 Capas Estrictas)

El proyecto respeta la **regla de dependencia unidireccional**:  
`interfaz` ➔ `servicios` ➔ `persistencia`, con `dominio` y `patrones` como núcleo transversal puro.

```text
proyecto_veterinaria/
├── .gitignore
├── GEMINI.md                                         # Reglas arquitectónicas, principios SOLID/GRASP y Clean Code
├── README.md                                         # Documentación general del repositorio
├── main.py                                           # Punto de entrada de la aplicación de escritorio
├── cargar_datos_prueba.py                            # Set de datos de prueba cargado a través de los servicios
├── requirements.txt                                  # customtkinter>=5.2, pytest
├── veterinaria.db                                    # Base de datos SQLite 3.37+ STRICT local
├── docs/                                             # Documentación técnica oficial y diagramas
│   ├── TRABAJOPRACTICO.pdf                           # Enunciado oficial de la cátedra DAO (2026)
│   ├── diagrama_de_clases_y_diseno_poo.md            # Diagramas UML de las 5 capas y fundamentación POO
│   ├── especificacion_base_datos_y_arquitectura.md   # Especificación DER, 26 tablas STRICT y DDL
│   ├── diagrama_DER_completo.png                     # Diagrama Entidad-Relación en alta resolución
│   └── diagrama_clases_UML_completo.png              # Diagrama de Clases UML en alta resolución
├── src/
│   ├── __init__.py
│   ├── dominio/                                      # [100% COMPLETO] Núcleo puro de negocio (sin dependencias externas)
│   │   ├── cliente.py                                # Entidad Cliente y validaciones Fail-Fast
│   │   ├── mascota.py                                # Entidad Mascota (responsable obligatorio)
│   │   ├── historia_clinica.py                       # HistoriaClinica (cálculo de vacunas pendientes), VacunaAplicada y Tratamiento
│   │   ├── consulta_medica.py                        # ConsultaMedica (cálculo experto de solapamiento) y OrdenDerivacion
│   │   ├── muestra_biologica.py                      # MuestraBiologica y RegistroTrazabilidad inmutable (frozen=True)
│   │   ├── logistica.py                              # ConservadoraIsotermica, PrecintoSanitario, RemitoBiologico y EnvioLaboratorio
│   │   ├── facturacion.py                            # ResultadoAnalisis, ComprobanteAtencion y DetalleComprobante
│   │   └── excepciones.py                            # Jerarquía de excepciones tipadas con raíz en ErrorVeterinaria
│   ├── patrones/                                     # [100% COMPLETO] Patrones de Diseño GoF
│   │   ├── estado_muestra.py                         # Patrón STATE: Extraida -> Empaquetada -> EnTransito -> Recibida -> Analizada | Rechazada
│   │   ├── estrategia_facturacion.py                 # Patrón STRATEGY: TarifaEstandar, TarifaUrgenciaLaboratorio, TarifaConvenioRed
│   │   ├── iterador_muestras.py                      # Patrón ITERATOR: IteradorMuestras e IteradorMuestrasFiltradas
│   │   └── observador_eventos.py                     # Patrón OBSERVER: SujetoEventos, Observador y ObservadorAuditoria
│   ├── persistencia/                                 # [100% COMPLETO] Capa DAO + Singleton + SQLite STRICT
│   │   ├── esquema.sql                               # DDL de 26 tablas STRICT, constraints nombrados, 14 índices y 4 triggers
│   │   ├── conexion_bd.py                            # Patrón SINGLETON (ConexionBD) y unidad de trabajo transaccional
│   │   ├── inicializador_bd.py                       # Creador idempotente del esquema y semillas paramétricas
│   │   ├── traductor_errores.py                      # Traductor de errores SQLite a excepciones de dominio
│   │   ├── dao_base.py                               # Clase abstracta base DAOBase
│   │   ├── cliente_dao.py                            # ClienteDAO
│   │   ├── mascota_dao.py                            # MascotaDAO
│   │   ├── consulta_dao.py                           # ConsultaDAO
│   │   ├── muestra_dao.py                            # MuestraDAO
│   │   ├── logistica_dao.py                          # LogisticaDAO
│   │   └── facturacion_dao.py                        # FacturacionDAO
│   ├── servicios/                                    # [100% COMPLETO] Orquestación de Casos de Uso y Reportes
│   │   ├── servicio_clinica.py                       # Procesos 1 (Clientes), 2 (Mascotas e H.C.) y 3 (Consultas y Extracción)
│   │   ├── servicio_logistica.py                     # Procesos 4 (Empaquetado), 5 (Despacho) y 6 (Recepción y Precinto)
│   │   ├── servicio_laboratorio.py                   # Proceso 7 (Resultados Bioquímicos y Facturación Strategy)
│   │   └── servicio_reportes.py                      # Los 5 reportes no triviales, validación de fechas y exportación CSV
│   └── interfaz/                                     # [100% COMPLETO] Presentación GUI con CustomTkinter
│       ├── app.py                                    # VentanaPrincipal (zoom dinámico 75%-130% y suscripción Observer)
│       ├── tema.py                                   # Paleta de colores, tipografías y estilos
│       ├── componentes/
│       │   ├── alertas.py                            # Manejador seguro de errores y resaltado visual de campos
│       │   └── tabla_datos.py                        # Componente reutilizable TablaDatos (ttk.Treeview estilizado)
│       └── vistas/
│           ├── vista_clientes.py                     # Vista Proceso 1: Clientes y búsqueda en vivo
│           ├── vista_mascotas.py                     # Vista Proceso 2: Mascotas, Historia Clínica y Vacunas
│           ├── vista_consultas.py                    # Vista Proceso 3: Consultas, Derivaciones y Muestras
│           ├── vista_logistica.py                    # Vista Procesos 4, 5 y 6: Conservadoras, Precintos y Remitos
│           ├── vista_laboratorio.py                  # Vista Proceso 7: Informe Bioquímico y Liquidación
│           └── vista_reportes.py                     # Vista de los 5 Reportes, KPIs y exportador CSV
└── tests/                                            # [100% COMPLETO] Suite de 89 pruebas automatizadas
    ├── test_persistencia_base.py                     # Singleton, unidad de trabajo, constraints STRICT y triggers
    ├── test_dominio_y_patrones.py                    # Entidades de dominio y patrones State, Strategy, Iterator, Observer
    ├── test_daos.py                                  # Integración de los 6 DAOs contra SQLite en memoria
    ├── test_trazabilidad_e_historia_clinica.py       # Ciclo de vida de remitos, vacunas pendientes y rechazos con transporte
    ├── test_servicios_negocio.py                     # Orquestación de punta a punta de los Procesos 1 a 7
    ├── test_reportes.py                              # Exactitud estadística de los 5 reportes y exportación CSV
    ├── test_interfaz_arquitectura_y_ventana_principal.py # Regla de capas (AST), método .validar() y ventana principal
    ├── test_interfaz_logistica_y_laboratorio.py      # Integración de vistas de logística y laboratorio con patrones GoF
    └── test_interfaz_reportes_y_csv.py               # Integración de vista de reportes, validación de fechas y CSV
```

---

## 🧩 Patrones de Diseño Implementados

| Patrón | Clasificación | Archivo Principal | Propósito en el Sistema |
| :--- | :--- | :--- | :--- |
| **State** | Comportamiento *(GoF)* | [`src/patrones/estado_muestra.py`](src/patrones/estado_muestra.py) | Modela el ciclo de vida de `MuestraBiologica` (`Extraida` → `Empaquetada` → `EnTransito` → `Recibida` → `Analizada` / `Rechazada`). Bloquea transiciones ilegales y rechaza polimórficamente muestras con precinto roto o violado. |
| **Strategy** | Comportamiento *(GoF)* | [`src/patrones/estrategia_facturacion.py`](src/patrones/estrategia_facturacion.py) | Cálculo polimórfico de liquidaciones arancelarias (`TarifaEstandar`, `TarifaUrgenciaLaboratorio` con `+30%` sobre análisis bioquímicos y `TarifaConvenioRed` con `-15%` de bonificación en consulta clínica). |
| **Iterator** | Comportamiento *(GoF)* | [`src/patrones/iterador_muestras.py`](src/patrones/iterador_muestras.py) | Recorrido encapsulado de las muestras en `ConservadoraIsotermica` (`IteradorMuestras` e `IteradorMuestrasFiltradas` para muestras viables sin romper el encapsulamiento). |
| **Observer** | Comportamiento *(GoF)* | [`src/patrones/observador_eventos.py`](src/patrones/observador_eventos.py) | Publicación y suscripción desacoplada de eventos (`REMITO_DESPACHADO`, `MUESTRAS_RECHAZADAS_EN_RECEPCION`, `RESULTADO_ANALISIS_LISTO`) conectando servicios con auditoría y barra de estado de la UI. |
| **Singleton** | Creacional *(GoF)* | [`src/persistencia/conexion_bd.py`](src/persistencia/conexion_bd.py) | Garantiza una única instancia de `ConexionBD` con `PRAGMA foreign_keys = ON` y control transaccional atómico (`with conexion.transaccion():`). |
| **DAO** | Estructural *(Persistencia)* | [`src/persistencia/*_dao.py`](src/persistencia/) | Aisla el acceso a datos en 6 DAOs específicos sin lógica de negocio, traduciendo errores SQLite en excepciones de dominio mediante `traductor_errores.py`. |

---

## 🚀 Guía de Inicio Rápido

### 1. Requisitos Previos
* **Python 3.11 o superior** (con soporte para SQLite 3.37+ con sintaxis `STRICT`).
* **Tkinter**, requerido por CustomTkinter. En Debian/Ubuntu se instala con `sudo apt install python3-tk` para el Python del sistema.
* **Git**.

### 2. Clonar el Repositorio y Configurar Entorno

* **En Windows (PowerShell):**
  ```powershell
  git clone https://github.com/tu-usuario/proyecto_veterinaria.git
  cd proyecto_veterinaria
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

* **En Linux / macOS:**
  ```bash
  git clone https://github.com/tu-usuario/proyecto_veterinaria.git
  cd proyecto_veterinaria
  python3 -m venv .venv
  source .venv/bin/activate
  ```

> **Linux (Debian/Ubuntu):** instala Tkinter antes de crear el entorno virtual con `sudo apt install python3-tk`.
> **Importante:** Tkinter no se instala con `pip`. Si usas un Python distinto al del sistema (por ejemplo, Python 3.14 instalado aparte), asegúrate de instalar o compilar el soporte Tcl/Tk para esa misma versión y vuelve a crear el entorno virtual. Puedes comprobarlo con `python -m tkinter`.

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Inicializar la Base de Datos Local
Crea las 26 tablas `STRICT`, los triggers de inmutabilidad y precarga los catálogos paramétricos iniciales de forma idempotente:
```bash
python -m src.persistencia.inicializador_bd
```

#### 4.1. (Opcional) Cargar Datos de Prueba
Puebla la base con un escenario realista (agosto a noviembre de 2026) que recorre los 7 procesos y alimenta los 5 reportes. Los datos se cargan a través de la capa de servicios, por lo que pasan por las mismas validaciones de negocio y patrones que usa la interfaz:
```bash
python cargar_datos_prueba.py --reiniciar
```
> `--reiniciar` respalda la base actual en `veterinaria.db.bak` y crea una nueva. Sin esa opción, el script no hace nada si la base ya tiene clientes, para no mezclar datos.

| Entidad | Cantidad | Escenarios para probar |
| :--- | :---: | :--- |
| Clientes | 12 | Elena Suárez no tiene mascotas (baja permitida) y usa DNI y teléfono de 7 dígitos (valores límite). |
| Mascotas | 18 | Las 5 especies, con antecedentes y alergias. 5 mascotas quedan con 8 vacunas obligatorias vencidas o nunca aplicadas (Reporte 3). |
| Consultas | 30 | Las 3 clínicas, 19 tratamientos y turnos simultáneos de distintos veterinarios (no se superponen). Varias quedan sin facturar. |
| Muestras | 28 | 16 `Analizada`, 4 `Rechazada`, 2 `Recibida` sin analizar, 2 `EnTransito`, 1 `Empaquetada` y 3 `Extraida` pendientes de empaquetar. |
| Remitos | 12 | 8 `Recibido`, 2 `Rechazado` (precinto `Roto` y `Violado`, Reporte 2), 1 `EnTransito` y 1 `Precintado`. Queda libre sólo `CONS-001`. |
| Comprobantes | 16 | Las 3 estrategias: `Tarifa Estándar`, `Tarifa Urgencia` y `Tarifa Convenio Red` (Reporte 4). |

### 5. Iniciar la Aplicación de Escritorio
Lanza la interfaz gráfica interactiva con las 6 vistas operativas:
```bash
python main.py
```
> 💡 **Tip de Accesibilidad:** La aplicación cuenta con zoom dinámico ajustable desde el selector superior o mediante los atajos `Ctrl +`, `Ctrl -` y `Ctrl 0`.

### 6. Ejecutar la Suite de Pruebas Automatizadas
Ejecuta la totalidad de las 89 pruebas unitarias, de integración y arquitectónicas AST:
```bash
pytest -v
```

---

## 📚 Documentación Técnica Oficial

* 📙 **[`docs/diagrama_de_clases_y_diseno_poo.md`](docs/diagrama_de_clases_y_diseno_poo.md):** Diagrama de Clases UML completo, fundamentación de principios SOLID y GRASP, y detalle de los 4 patrones GoF implementados.
* 📘 **[`docs/especificacion_base_datos_y_arquitectura.md`](docs/especificacion_base_datos_y_arquitectura.md):** Especificación técnica del Modelo Entidad-Relación (DER), diccionario de las 26 tablas `STRICT`, llaves foráneas, índices y triggers de inmutabilidad.
* 🖼️ **[`docs/diagrama_DER_completo.png`](docs/diagrama_DER_completo.png):** Imagen del Diagrama Entidad-Relación completo.
* 🖼️ **[`docs/diagrama_clases_UML_completo.png`](docs/diagrama_clases_UML_completo.png):** Imagen del Diagrama de Clases UML completo.
