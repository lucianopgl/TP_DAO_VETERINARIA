# 🐾 Sistema de Gestión Veterinaria y Derivación de Laboratorio

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![SQLite STRICT](https://img.shields.io/badge/sqlite-3.37+-lightgrey.svg)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/tests-57%20passing-brightgreen.svg)](tests/)

Sistema integral para la administración de una red de clínicas veterinarias, atención clínica de pacientes y gestión logística con trazabilidad para la derivación de muestras biológicas hacia un laboratorio central de análisis.

> **Proyecto Integrador de Cátedra:** Desarrollo de Aplicaciones con Objetos (DAO) — Ingeniería en Sistemas de Información (2026).  
> **Tema:** Red de Clínicas Veterinarias y Derivación de Laboratorio.

---

## 📌 ¿De qué trata el proyecto?

El sistema modela la operativa diaria de una red veterinaria y resuelve integralmente tres grandes problemáticas:

1. **Gestión Clínica y Pacientes:**
   - Registro de Clientes (dueños/responsables) y Mascotas.
   - Historias clínicas digitales, registro de antecedentes, alergias y plan de vacunación.
   - Consultas médicas, diagnósticos y prescripción de tratamientos farmacológicos.

2. **Logística y Trazabilidad de Muestras Biológicas:**
   - Órdenes de derivación médica para estudios de laboratorio (Hemogramas, Perfiles Bioquímicos, Urianálisis, etc.).
   - Seguimiento estricto del ciclo de vida de cada muestra biológica mediante máquina de estados.
   - Agrupamiento en conservadoras de transporte térmico con precintos de seguridad numerados y remitos de envío.

3. **Facturación, Auditoría y Notificaciones:**
   - Liquidación y facturación de consultas y estudios aplicando diferentes estrategias arancelarias (Tarifa Plena, Obra Social/Convenio, Urgencia).
   - Generación de comprobantes fiscales cabecera/detalle.
   - Notificaciones basadas en eventos para alertar ante rechazo de muestras o emisión de resultados.

---

## 🏗️ Arquitectura y Patrones de Diseño

El proyecto está diseñado bajo una arquitectura en capas limpia, desacoplada y orientada a objetos:

```text
proyecto_veterinaria/
├── docs/                       # Especificaciones funcionales, diagramas UML y modelo relacional
├── src/
│   ├── dominio/                # Entidades del negocio, dataclasses y reglas de validación
│   ├── patrones/               # Implementación de Patrones de Diseño GoF
│   ├── persistencia/           # Capa de acceso a datos (Patrón DAO) y DDL SQLite
│   ├── servicios/              # Orquestación de casos de uso y transacciones (En desarrollo)
│   └── interfaz/               # Interfaz gráfica de usuario con CustomTkinter (En desarrollo)
└── tests/                      # Suite de tests automatizados unitarios y de integración
```

### Patrones GoF Implementados
* **State (`src/patrones/estado_muestra.py`):** Modela el ciclo de vida de las muestras biológicas (`Extraída` $\to$ `Empaquetada` $\to$ `EnTránsito` $\to$ `Recibida` $\to$ `Analizada` / `Rechazada`), impidiendo transiciones inválidas.
* **Strategy (`src/patrones/estrategia_facturacion.py`):** Permite calcular los importes finales de las facturas intercambiando dinámicamente las reglas de cobro (Particular / Convenio / Urgencia).
* **Iterator (`src/patrones/iterador_muestras.py`):** Proporciona un recorrido seguro y desacoplado de las muestras asignadas a una conservadora de transporte.
* **Observer (`src/patrones/observador_eventos.py`):** Desacopla la emisión de eventos clave (ej. resultado disponible, muestra rechazada) de los canales de notificación.
* **Singleton (`src/persistencia/conexion_bd.py`):** Garantiza un único punto centralizado de conexión atómica hacia la base de datos relacional.
* **DAO (Data Access Object) (`src/persistencia/*_dao.py`):** Aisla completamente la lógica del dominio de las sentencias SQL y la tecnología de almacenamiento.

---

## 🚦 Estado Actual del Desarrollo

* [x] **Capa de Dominio:** Entidades, reglas de validación y excepciones de negocio (100%).
* [x] **Patrones de Diseño:** Implementación y cobertura de los 4 patrones GoF (100%).
* [x] **Persistencia Relacional:** Esquema DDL en SQLite con tablas `STRICT`, restricciones de integridad, triggers y DAOs completos (100%).
* [x] **Tests Automatizados:** Cobertura de 57 pruebas unitarias y de integración pasando al 100%.
* [ ] **Capa de Servicios:** Orquestación de casos de uso, agenda de turnos y reportes analíticos (En progreso).
* [ ] **Interfaz Gráfica (GUI):** Vistas y pantallas con `CustomTkinter` (En progreso).
* [ ] **Punto de Entrada (`main.py`):** Lanzador global de la aplicación (En progreso).

---

## 🚀 Guía de Inicio: Cómo clonar y poner a correr el proyecto

Si acabas de clonar el repositorio, sigue estos pasos para configurar tu entorno local y verificar que todo funcione:

### 1. Requisitos Previos

* **Python 3.11 o superior** instalado (se requiere soporte nativo de `sqlite3` con tablas `STRICT`).
* **Git** instalado.

---

### 2. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/proyecto_veterinaria.git
cd proyecto_veterinaria
```

---

### 3. Crear y activar un entorno virtual

Se recomienda crear un entorno virtual aislado para no alterar tu instalación global de Python:

* **En Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```
  *(Si PowerShell restringe scripts, ejecuta antes: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

* **En Windows (CMD):**
  ```cmd
  python -m venv .venv
  .\.venv\Scripts\activate.bat
  ```

* **En Linux / macOS:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

---

### 4. Instalar las dependencias

Instala los paquetes necesarios del proyecto y la herramienta de pruebas:

```bash
pip install -r requirements.txt
pip install pytest
```

---

### 5. Generar la Base de Datos Local

> ℹ️ **¿Por qué no vino el archivo `.db` en el repositorio?**  
> El archivo físico `veterinaria.db` no se sube al control de versiones (está ignorado en `.gitignore`) por seguridad, prevención de conflictos binarios al fusionar ramas (merge conflicts) y para mantener limpio el repositorio.

Para crear la base de datos desde cero con todas sus tablas, restricciones relacionales y catálogos paramétricos (especies, vacunas, estudios médicos, transportistas, etc.), ejecuta el inicializador idempotente:

```bash
python -m src.persistencia.inicializador_bd
```

*Verás un mensaje confirmando que `veterinaria.db` se ha generado y precargado exitosamente.*

---

### 6. Ejecutar la Suite de Pruebas

Para validar que todo el dominio, la persistencia relacional, los triggers y los patrones funcionan adecuadamente en tu máquina:

```bash
pytest
```

Deberías ver una salida indicando que **todos los tests pasaron exitosamente** (57 passed).

---

### 7. Uso Rápido e Interacción con el Dominio y DAOs

Dado que la interfaz gráfica interactiva se encuentra en desarrollo, puedes explorar el funcionamiento mediante una sesión interactiva de Python:

```bash
python
```

```python
from src.persistencia.cliente_dao import ClienteDAO
from src.dominio.cliente import Cliente

dao = ClienteDAO()

# 1. Crear un cliente
nuevo_cliente = Cliente(
    id=None,
    dni="40123456",
    nombre="Juan",
    apellido="Pérez",
    telefono="1144556677",
    email="juan.perez@example.com"
)
id_cliente = dao.guardar(nuevo_cliente)
print(f"Cliente guardado con ID: {id_cliente}")

# 2. Consultarlo
cliente_recuperado = dao.buscar_por_id(id_cliente)
print(f"Recuperado: {cliente_recuperado.nombre_completo()} - DNI: {cliente_recuperado.dni}")
```

---

## 📚 Documentación Adicional

En la carpeta [`docs/`](docs/) encontrarás material de apoyo y especificaciones detalladas:
* [`docs/especificacion_base_datos_y_arquitectura.md`](docs/especificacion_base_datos_y_arquitectura.md): Explicación exhaustiva del modelo relacional, integridad referencial y decisiones de diseño técnico.
* [`docs/diagrama_de_clases_y_diseno_poo.md`](docs/diagrama_de_clases_y_diseno_poo.md): Diagramas de clases UML completos con descripción de cada patrón GoF.
* [`docs/diagrama_BD.svg`](docs/diagrama_BD.svg): Diagrama visual del esquema de base de datos.
