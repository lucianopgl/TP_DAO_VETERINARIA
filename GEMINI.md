# Sistema Veterinario: Red de Clínicas y Derivación de Laboratorio
**Cátedra:** Desarrollo de Aplicaciones con Objetos (DAO) — UTN FRC (2026) — Tema 2

## 1. Filosofía de Diseño y Lineamientos de Cátedra (Prioridad Máxima)
Todo código que se escriba o modifique en este repositorio debe respetar de forma estricta:
- **Principios de Diseño POO (SOLID y GRASP):**
  - **Alta Cohesión y Responsabilidad Única (SRP):** Cada clase y módulo debe tener un propósito único y bien definido.
  - **Bajo Acoplamiento e Inversión de Dependencias (DIP):** Las capas superiores se comunican mediante abstracciones/interfaces claras sin conocer detalles internos de implementación de las capas inferiores.
  - **Experto en Información (GRASP):** Las reglas intrínsecas y cálculos sobre atributos propios viven en las entidades del Dominio (ej. `HistoriaClinica.calcular_vacunas_pendientes`, `ConsultaMedica.se_superpone_con`).
  - **Polimorfismo sobre condicionales:** Respetar los patrones GoF exigidos por la cátedra (**State**, **Strategy**, **Iterator**, **Observer**) y **Singleton** / **DAO** en persistencia, evitando reemplazar comportamiento polimórfico por cadenas de `if/elif`.
- **Clean Code:**
  - Código autoexplicativo, sin código muerto, sin imports ociosos, sin valores mágicos ("magic strings/numbers") y aplicando **DRY** (Don't Repeat Yourself).
  - Respeto total por la documentación oficial del proyecto en `docs/diagrama_de_clases_y_diseno_poo.md` y `docs/especificacion_base_datos_y_arquitectura.md`.

## 2. Mapa Arquitectónico y Regla Estricta de Capas
El proyecto implementa una arquitectura en capas bajo `src/`. **Regla de dependencia unidireccional:** cada capa sólo conoce a las capas inferiores (`interfaz` -> `servicios` -> `persistencia`, con `dominio` y `patrones` como núcleo transversal):

1. **`src/dominio/` (Núcleo Puro de Negocio):**
   - Entidades: `Cliente`, `Mascota`, `HistoriaClinica`, `VacunaAplicada`, `Tratamiento`, `ConsultaMedica`, `OrdenDerivacion`, `MuestraBiologica`, `RegistroTrazabilidad`, `ConservadoraIsotermica`, `PrecintoSanitario`, `RemitoBiologico`, `EnvioLaboratorio`, `ResultadoAnalisis`, `ComprobanteAtencion`, `DetalleComprobante`.
   - Excepciones jerárquicas con raíz única en `ErrorVeterinaria` (`excepciones.py`).
   - **Regla:** Prohibido importar `sqlite3` o librerías gráficas (`tkinter`/`customtkinter`). Todas las entidades exponen y ejecutan `.validar()`.
2. **`src/patrones/` (Patrones GoF de la Cátedra):**
   - **State (`estado_muestra.py`):** Ciclo de vida de `MuestraBiologica` (`Extraida` -> `Empaquetada` -> `EnTransito` -> `Recibida` -> `Analizada` | `Rechazada`).
   - **Strategy (`estrategia_facturacion.py`):** Liquidación polimórfica de aranceles (`TarifaEstandar`, `TarifaUrgenciaLaboratorio`, `TarifaConvenioRed`).
   - **Iterator (`iterador_muestras.py`):** Recorrido encapsulado y filtrado de muestras viables en `ConservadoraIsotermica`.
   - **Observer (`observador_eventos.py`):** Notificaciones desacopladas (`SujetoEventos`, `Observador`, `ObservadorAuditoria`).
3. **`src/persistencia/` (Patrón DAO + Singleton SQLite):**
   - `ConexionBD` (`conexion_bd.py`): **Singleton** con unidad de trabajo atómica (`with conexion.transaccion():`) y `PRAGMA foreign_keys = ON`.
   - `esquema.sql` e `inicializador_bd.py`: 26 tablas `STRICT`, triggers de inmutabilidad en historiales y precarga idempotente.
   - `traductor_errores.py`: Traduce errores de `sqlite3` a `ErrorIntegridadDatos` / `ErrorPersistencia` con mensajes amigables en español.
   - Objetos DAO (`cliente_dao.py`, `mascota_dao.py`, `consulta_dao.py`, `muestra_dao.py`, `logistica_dao.py`, `facturacion_dao.py`): **Único lugar de acceso transaccional SQL.** Sin lógica de negocio.
4. **`src/servicios/` (Orquestación de Casos de Uso y Reportes):**
   - `ServicioClinica`: Procesos 1 (Clientes), 2 (Mascotas e Historia Clínica 1:1, vacunas) y 3 (Consultas, no superposición horaria, órdenes y extracción de muestras).
   - `ServicioLogistica`: Procesos 4 (Empaquetado en conservadora con remito y precinto), 5 (Despacho a laboratorio) y 6 (Recepción y verificación de precinto intacto/roto/violado).
   - `ServicioLaboratorio`: Proceso 7 (Carga de resultados bioquímicos y emisión de comprobantes con Strategy).
   - `ServicioReportes`: Los 5 reportes gerenciales/sanitarios no triviales y exportación a CSV.
   - **Regla:** Los servicios de negocio (`ServicioClinica`, `ServicioLogistica`, `ServicioLaboratorio`) delegan todo acceso a datos en los DAOs (cero SQL en servicios de negocio).
5. **`src/interfaz/` (Presentación GUI con CustomTkinter):**
   - **Regla:** Solo interactúa con `src/servicios/`, entidades/excepciones de `src/dominio/` y objetos de `src/patrones/` (ej. observadores de UI o selección de estrategias).
   - **Prohibido:** Importar `sqlite3`, escribir SQL o instanciar DAOs desde la interfaz.
   - Captura siempre `ErrorDatosInvalidos` (usando `.campo` y `.mensaje`) y `ErrorVeterinaria` (mostrando `.mensaje` al usuario).

## 3. Reglas de Calidad y Verificación Continua
- **Excepciones tipadas:** Nunca lanzar `ValueError` o `Exception` genéricos para reglas de negocio; usar siempre subclases de `ErrorVeterinaria`.
- **Inmutabilidad de trazabilidad:** Nunca modificar ni eliminar filas de `historial_estados_muestra` ni `historial_estados_remito`.
- **Comandos de verificación obligatoria tras cambios:**
  - Inicializar/regenerar BD local: `python -m src.persistencia.inicializador_bd`
  - Ejecutar suite de pruebas (74 tests): `pytest`
