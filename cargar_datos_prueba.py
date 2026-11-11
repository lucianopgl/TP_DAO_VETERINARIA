"""
Carga de un set de datos de prueba completo (`cargar_datos_prueba.py`)
======================================================================

Cátedra: Desarrollo de Aplicaciones con Objetos (DAO) — UTN FRC (2026)
Tema 2: Veterinaria — Red de Clínicas y Derivación de Laboratorio
Grupo: Grupo 089

Puebla la base con datos realistas (agosto a noviembre de 2026) que recorren los
7 procesos obligatorios y alimentan los 5 reportes. Todos los datos se cargan a
través de la capa de servicios, por lo que pasan por las mismas validaciones de
negocio, patrones (State, Strategy, Iterator, Observer) y transacciones que usa la
interfaz gráfica: no se inserta nada "a mano" en las tablas.

Escenarios cubiertos:
    - 12 clientes (uno sin mascotas, para probar la baja) y 18 mascotas de las
      5 especies, con antecedentes y alergias en sus historias clínicas.
    - Vacunas obligatorias al día, vencidas y nunca aplicadas (Reporte 3).
    - 30 consultas en las 3 clínicas, con tratamientos, vacunas aplicadas y turnos
      simultáneos de distintos veterinarios.
    - 12 remitos con todos los estados posibles:
        * Recibidos con precinto 'Intacto' y muestras analizadas.
        * Rechazados con precinto 'Roto' y 'Violado' (Reporte 2).
        * Recibidos con muestras pendientes de análisis.
        * En tránsito y precintados sin despachar.
    - Muestras extraídas pendientes de empaquetar en dos clínicas.
    - Comprobantes con las 3 estrategias de facturación y consultas sin facturar.
    - Al finalizar, CONS-001 queda disponible y CONS-002 / CONS-003 ocupadas.

Ejecución desde la raíz del repositorio:

    python cargar_datos_prueba.py              # Sólo si la base no tiene clientes.
    python cargar_datos_prueba.py --reiniciar  # Respalda veterinaria.db y la recrea.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timedelta

from src.dominio.consulta_medica import FORMATO_FECHA_HORA
from src.dominio.historia_clinica import Tratamiento
from src.patrones.observador_eventos import ObservadorAuditoria, SujetoEventos
from src.persistencia.conexion_bd import RUTA_BD_POR_DEFECTO, ConexionBD
from src.persistencia.inicializador_bd import inicializar_base_datos
from src.servicios.servicio_clinica import ServicioClinica
from src.servicios.servicio_laboratorio import ServicioLaboratorio
from src.servicios.servicio_logistica import ServicioLogistica


# ======================================================================================
# Datos de prueba
# Las entidades de la red (clínicas, veterinarios, etc.) se referencian por nombre,
# matrícula o código, nunca por id, para no depender del orden de inserción.
# ======================================================================================

CLINICAS = {
    "Centro": "Clínica Veterinaria Centro",
    "Nueva Córdoba": "Clínica Veterinaria Nueva Córdoba",
    "Cerro": "Clínica Veterinaria Cerro de las Rosas",
}

LABORATORIO = "Laboratorio Central de Diagnóstico Veterinario"

TRANSPORTISTAS = {
    "LSC": "30-71234567-8",   # Logística Sanitaria Córdoba
    "BIO": "30-79876543-2",   # BioTraslados SRL
}

# (dni, nombre, apellido, telefono, email, direccion)
CLIENTES: tuple[tuple[str, str, str, str, str | None, str | None], ...] = (
    ("28456789", "María", "Fernández", "3514567890", "maria.fernandez@gmail.com", "Av. Colón 2345, Córdoba"),
    ("31234567", "Juan", "Pérez", "3515123456", "juanperez@hotmail.com", "Obispo Trejo 850, Córdoba"),
    ("25987654", "Lucía", "Romero", "3516234567", None, "Bv. San Juan 410, Córdoba"),
    ("33456123", "Federico", "Álvarez", "3517345678", "fede.alvarez@outlook.com", "Av. Rafael Núñez 5100, Córdoba"),
    ("29876123", "Sofía", "Castro", "3518456789", "sofia.castro@yahoo.com.ar", "Chacabuco 1200, Córdoba"),
    ("35678901", "Matías", "Herrera", "3519567890", None, None),
    ("27345678", "Valentina", "Moreno", "3514678901", "vmoreno@gmail.com", "Av. Hipólito Yrigoyen 300, Córdoba"),
    ("38123456", "Agustín", "Benítez", "3515789012", "agus.benitez@gmail.com", "Duarte Quirós 1500, Córdoba"),
    ("24567890", "Graciela", "Ortiz", "3516890123", "graciela.ortiz@gmail.com", "Av. Fuerza Aérea 2100, Córdoba"),
    ("40123987", "Camila", "Navarro", "3517901234", "cami.navarro@gmail.com", "Independencia 650, Córdoba"),
    ("32765432", "Ricardo", "Medina", "3518012345", None, "Av. Recta Martinoli 7200, Córdoba"),
    # Valores límite (DNI y teléfono de 7 dígitos) y sin mascotas: se puede dar de baja.
    ("9876543", "Elena", "Suárez", "4801234", None, "Belgrano 120, Córdoba"),
)

# (clave, nombre, especie, raza, edad, sexo, dni_responsable, apertura_hc, antecedentes, alergias)
MASCOTAS: tuple[tuple[str, str, str, str, int, str, str, str, str | None, str | None], ...] = (
    ("toby", "Toby", "Canino", "Labrador Retriever", 5, "Macho", "28456789", "2024-03-10",
     "Displasia de cadera leve diagnosticada en 2023.", None),
    ("luna", "Luna", "Felino", "Siamés", 3, "Hembra", "28456789", "2024-05-02",
     None, "Alergia a la penicilina."),
    ("rocky", "Rocky", "Canino", "Bulldog Francés", 4, "Macho", "31234567", "2025-01-15",
     "Síndrome braquicefálico; cirugía de paladar blando en 2024.", None),
    ("michi", "Michi", "Felino", "Común europeo", 8, "Macho", "25987654", "2023-09-20",
     "Enfermedad renal crónica estadio 2.", None),
    ("kiwi", "Kiwi", "Ave", "Agapornis", 2, "Hembra", "25987654", "2025-08-11", None, None),
    ("thor", "Thor", "Canino", "Ovejero Alemán", 7, "Macho", "33456123", "2022-06-05",
     "Otitis externa recurrente.", "Hipersensibilidad a la picadura de pulga."),
    ("nala", "Nala", "Canino", "Golden Retriever", 1, "Hembra", "33456123", "2026-02-14", None, None),
    ("simba", "Simba", "Felino", "Persa", 6, "Macho", "29876123", "2023-11-30",
     "Poliquistosis renal en seguimiento.", None),
    ("pelusa", "Pelusa", "Roedor", "Cobayo", 2, "Hembra", "29876123", "2025-10-01", None, None),
    ("bruno", "Bruno", "Canino", "Mestizo", 10, "Macho", "35678901", "2021-04-18",
     "Cardiopatía (insuficiencia mitral) en tratamiento.", "Alergia alimentaria a la proteína de pollo."),
    ("mora", "Mora", "Felino", "Mestizo", 0, "Hembra", "27345678", "2026-08-20", None, None),
    ("coco", "Coco", "Canino", "Caniche Toy", 12, "Hembra", "27345678", "2020-07-07",
     "Enfermedad periodontal; extracciones dentales en 2025.", None),
    ("spike", "Spike", "Reptil", "Iguana verde", 4, "Macho", "38123456", "2024-12-03",
     "Enfermedad ósea metabólica leve (2024).", None),
    ("milo", "Milo", "Canino", "Beagle", 3, "Macho", "24567890", "2024-02-22",
     None, "Alergia a la amoxicilina."),
    ("olivia", "Olivia", "Felino", "Maine Coon", 4, "Hembra", "24567890", "2024-09-09", None, None),
    ("max", "Max", "Canino", "Border Collie", 2, "Macho", "40123987", "2025-03-03", None, None),
    ("pipo", "Pipo", "Ave", "Canario", 1, "Macho", "32765432", "2026-01-10", None, None),
    ("lola", "Lola", "Canino", "Dachshund", 9, "Hembra", "32765432", "2022-10-25",
     "Hernia de disco operada en 2024.", None),
)

# Antecedentes de vacunación aplicados fuera de la red (sin consulta asociada).
# Junto con las vacunas aplicadas en las consultas y con refuerzo cada 12 meses, al
# 11/11/2026 quedan 8 vacunas obligatorias pendientes en 5 mascotas (Reporte 3):
#   vencidas: bruno (antirrábica), olivia (triple), lola (antirrábica)
#   nunca aplicadas: michi (antirrábica y triple), bruno (séxtuple), olivia y mora
#   (antirrábica).
# Luna, Rocky y Thor tenían vacunas vencidas que se regularizan en sus consultas.
# (clave_mascota, vacuna, fecha_aplicacion)
VACUNAS_PREVIAS: tuple[tuple[str, str, str], ...] = (
    ("toby", "Antirrábica", "2026-03-15"),
    ("toby", "Séxtuple canina", "2026-03-15"),
    ("luna", "Antirrábica", "2025-06-10"),
    ("luna", "Triple felina", "2026-04-20"),
    ("rocky", "Antirrábica", "2026-01-20"),
    ("rocky", "Séxtuple canina", "2025-09-01"),
    ("thor", "Antirrábica", "2025-05-10"),
    ("thor", "Séxtuple canina", "2025-05-10"),
    ("nala", "Séxtuple canina", "2026-03-20"),
    ("simba", "Antirrábica", "2026-02-11"),
    ("simba", "Triple felina", "2026-02-11"),
    ("simba", "Leucemia felina", "2026-02-11"),
    ("bruno", "Antirrábica", "2024-08-30"),
    ("coco", "Antirrábica", "2026-07-07"),
    ("coco", "Séxtuple canina", "2026-07-07"),
    ("coco", "Tos de las perreras", "2026-07-07"),
    ("milo", "Antirrábica", "2025-12-01"),
    ("milo", "Séxtuple canina", "2025-12-01"),
    ("olivia", "Triple felina", "2025-10-15"),
    ("max", "Antirrábica", "2026-03-10"),
    ("max", "Séxtuple canina", "2026-03-10"),
    ("lola", "Antirrábica", "2025-10-30"),
    ("lola", "Séxtuple canina", "2026-05-05"),
)

# Cada consulta puede incluir tratamientos (descripcion, medicamento, dosis, dias),
# vacunas aplicadas en el acto y órdenes de derivación con sus muestras:
#   ordenes = [(codigo_estudio, prioridad, indicaciones, [(codigo_muestra, tipo_muestra)])]
# La orden se emite 20 minutos después del inicio y cada muestra se extrae 5 minutos más tarde.
CONSULTAS: tuple[dict, ...] = (
    dict(clave="c01", mascota="toby", clinica="Centro", veterinario="MP-1001",
         inicio="2026-08-04 09:00:00", duracion=30, costo=15000.0,
         motivo="Control anual y cojera en miembro posterior.",
         diagnostico="Displasia de cadera estable; sobrepeso leve.",
         tratamientos=[("Condroprotector articular", "Condrovet", "1 comprimido cada 24 hs", 60)],
         ordenes=[("HEMOGRAMA", "Normal", "Control anual.", [("MUE-2026-0001", "SANGRE")]),
                  ("PERFIL_BIOQUIMICO", "Normal", "Evaluar función hepática y renal.",
                   [("MUE-2026-0002", "SUERO")])]),
    dict(clave="c02", mascota="luna", clinica="Centro", veterinario="MP-1004",
         inicio="2026-08-04 10:00:00", duracion=30, costo=14000.0,
         motivo="Vómitos intermitentes desde hace una semana.",
         diagnostico="Gastritis leve.",
         tratamientos=[("Protector gástrico", "Omeprazol", "5 mg cada 24 hs", 10)],
         vacunas=[("Antirrábica", "Felino")],
         ordenes=[("COPROPARASITOLOGICO", "Normal", "Descartar parásitos intestinales.",
                   [("MUE-2026-0003", "MATERIA_FECAL")])]),
    dict(clave="c03", mascota="rocky", clinica="Nueva Córdoba", veterinario="MP-1002",
         inicio="2026-08-06 11:00:00", duracion=45, costo=18000.0,
         motivo="Dificultad respiratoria luego del ejercicio.",
         diagnostico="Síndrome braquicefálico; sin indicación quirúrgica por ahora.",
         tratamientos=[("Control de peso y ejercicio moderado en horas frescas", None, None, None)]),
    dict(clave="c04", mascota="thor", clinica="Nueva Córdoba", veterinario="MP-1003",
         inicio="2026-08-10 16:00:00", duracion=30, costo=16000.0,
         motivo="Prurito intenso y sacudidas de cabeza.",
         diagnostico="Dermatitis alérgica por pulgas con otitis externa.",
         tratamientos=[("Antiparasitario externo", "Bravecto", "1 comprimido", 90),
                       ("Limpieza y gotas óticas", "Otomax", "5 gotas cada 12 hs", 14)],
         ordenes=[("CITOLOGIA", "Normal", "Citología de conducto auditivo.",
                   [("MUE-2026-0004", "HISOPADO")]),
                  ("CULTIVO_ANTIBIOGRAMA", "Urgente", "Otitis recurrente: definir antibiótico.",
                   [("MUE-2026-0005", "HISOPADO")])]),
    dict(clave="c05", mascota="nala", clinica="Nueva Córdoba", veterinario="MP-1001",
         inicio="2026-08-12 09:30:00", duracion=30, costo=12000.0,
         motivo="Vacunación y control de cachorra.",
         diagnostico="Paciente sana.",
         vacunas=[("Antirrábica", "Canino")]),
    dict(clave="c06", mascota="michi", clinica="Cerro", veterinario="MP-1004",
         inicio="2026-08-18 15:00:00", duracion=40, costo=17000.0,
         motivo="Pérdida de peso y aumento de la sed.",
         diagnostico="Enfermedad renal crónica: control de progresión.",
         tratamientos=[("Dieta renal", "Royal Canin Renal", "A voluntad", None),
                       ("Quelante de fósforo", "Ipakitine", "1 medida cada 12 hs", 30)],
         ordenes=[("PERFIL_BIOQUIMICO", "Urgente", "Urea, creatinina y fósforo.",
                   [("MUE-2026-0006", "SUERO")]),
                  ("URIANALISIS", "Urgente", "Densidad urinaria y proteinuria.",
                   [("MUE-2026-0007", "ORINA")])]),
    dict(clave="c07", mascota="bruno", clinica="Cerro", veterinario="MP-1002",
         inicio="2026-08-20 10:00:00", duracion=45, costo=20000.0,
         motivo="Tos nocturna y cansancio en los paseos.",
         diagnostico="Insuficiencia mitral estadio B2.",
         tratamientos=[("Inodilatador", "Pimobendan", "0,25 mg/kg cada 12 hs", 180)],
         ordenes=[("HEMOGRAMA", "Normal", "Prequirúrgico / control cardiológico.",
                   [("MUE-2026-0008", "SANGRE")])]),
    dict(clave="c08", mascota="simba", clinica="Centro", veterinario="MP-1004",
         inicio="2026-09-01 11:00:00", duracion=30, costo=15000.0,
         motivo="Control de poliquistosis renal.",
         diagnostico="Quistes renales estables.",
         ordenes=[("URIANALISIS", "Normal", "Control semestral.", [("MUE-2026-0009", "ORINA")])]),
    # Mismo horario que c08 con otro veterinario: no hay superposición de turnos.
    dict(clave="c09", mascota="milo", clinica="Centro", veterinario="MP-1003",
         inicio="2026-09-01 11:00:00", duracion=30, costo=15000.0,
         motivo="Diarrea crónica de tres semanas.",
         diagnostico="Enteropatía crónica a esclarecer.",
         tratamientos=[("Probiótico", "Florentero", "1 sobre cada 24 hs", 15)],
         ordenes=[("COPROPARASITOLOGICO", "Normal", "Seriado de 3 días.",
                   [("MUE-2026-0010", "MATERIA_FECAL")])]),
    dict(clave="c10", mascota="spike", clinica="Cerro", veterinario="MP-1001",
         inicio="2026-09-03 17:00:00", duracion=30, costo=19000.0,
         motivo="Inapetencia y letargo.",
         diagnostico="Hipotermia por mala termorregulación del terrario.",
         tratamientos=[("Suplemento de calcio y vitamina D3", "Calcio D3 reptiles",
                        "Espolvorear en el alimento 3 veces por semana", 60)],
         ordenes=[("HEMOGRAMA", "Normal", "Paciente exótico: iguana.", [("MUE-2026-0011", "SANGRE")])]),
    dict(clave="c11", mascota="olivia", clinica="Nueva Córdoba", veterinario="MP-1004",
         inicio="2026-09-08 10:00:00", duracion=30, costo=13000.0,
         motivo="Estornudos y secreción ocular.",
         diagnostico="Rinotraqueítis felina.",
         tratamientos=[("Antiviral oftálmico", "Aciclovir colirio", "1 gota cada 8 hs", 10)]),
    dict(clave="c12", mascota="coco", clinica="Cerro", veterinario="MP-1002",
         inicio="2026-09-10 09:00:00", duracion=60, costo=25000.0,
         motivo="Masa subcutánea en el flanco derecho.",
         diagnostico="Nódulo subcutáneo: se realiza exéresis y biopsia.",
         tratamientos=[("Analgésico postquirúrgico", "Meloxicam", "0,1 mg/kg cada 24 hs", 5)],
         ordenes=[("HISTOPATOLOGIA", "Urgente", "Evaluar márgenes quirúrgicos.",
                   [("MUE-2026-0012", "BIOPSIA")]),
                  ("CITOLOGIA", "Urgente", "Citología por punción previa.",
                   [("MUE-2026-0013", "BIOPSIA")])]),
    dict(clave="c13", mascota="max", clinica="Nueva Córdoba", veterinario="MP-1001",
         inicio="2026-09-15 18:00:00", duracion=30, costo=18000.0,
         motivo="Ingesta de un juguete de goma.",
         diagnostico="Gastroenteritis por cuerpo extraño; sin obstrucción.",
         tratamientos=[("Antiemético", "Maropitant", "1 mg/kg cada 24 hs", 3)],
         ordenes=[("HEMOGRAMA", "Urgente", "Guardia.", [("MUE-2026-0014", "SANGRE")]),
                  ("PERFIL_BIOQUIMICO", "Urgente", "Guardia.", [("MUE-2026-0015", "SUERO")])]),
    dict(clave="c14", mascota="thor", clinica="Nueva Córdoba", veterinario="MP-1003",
         inicio="2026-09-22 16:00:00", duracion=30, costo=14000.0,
         motivo="Control de otitis y revacunación.",
         diagnostico="Otitis en remisión.",
         vacunas=[("Antirrábica", "Canino"), ("Séxtuple canina", "Canino")],
         ordenes=[("CULTIVO_ANTIBIOGRAMA", "Normal", "Repetición: la muestra anterior fue rechazada.",
                   [("MUE-2026-0016", "HISOPADO")])]),
    dict(clave="c15", mascota="lola", clinica="Centro", veterinario="MP-1001",
         inicio="2026-10-01 10:00:00", duracion=30, costo=17000.0,
         motivo="Dolor lumbar y dificultad para subir escaleras.",
         diagnostico="Recidiva de discopatía.",
         tratamientos=[("Antiinflamatorio", "Meloxicam", "0,1 mg/kg cada 24 hs", 7),
                       ("Reposo estricto en jaula", None, None, 21)]),
    dict(clave="c16", mascota="mora", clinica="Centro", veterinario="MP-1004",
         inicio="2026-10-05 09:00:00", duracion=30, costo=12000.0,
         motivo="Primera consulta y vacunación.",
         diagnostico="Gatita sana; se desparasita.",
         tratamientos=[("Desparasitación interna", "Total Full Gatos", "1/4 de comprimido", 1)],
         vacunas=[("Triple felina", "Felino")]),
    dict(clave="c17", mascota="bruno", clinica="Cerro", veterinario="MP-1002",
         inicio="2026-10-07 10:00:00", duracion=30, costo=20000.0,
         motivo="Control cardiológico.",
         diagnostico="Insuficiencia mitral compensada.",
         ordenes=[("PERFIL_BIOQUIMICO", "Normal", "Control de función renal por medicación.",
                   [("MUE-2026-0017", "SUERO")])]),
    dict(clave="c18", mascota="rocky", clinica="Nueva Córdoba", veterinario="MP-1002",
         inicio="2026-10-14 11:00:00", duracion=30, costo=16000.0,
         motivo="Lagrimeo y ojo rojo.",
         diagnostico="Úlcera corneal superficial.",
         tratamientos=[("Colirio antibiótico", "Tobramicina", "1 gota cada 6 hs", 7)],
         vacunas=[("Séxtuple canina", "Canino")]),
    dict(clave="c19", mascota="luna", clinica="Centro", veterinario="MP-1004",
         inicio="2026-10-20 09:00:00", duracion=30, costo=12000.0,
         motivo="Control de gastritis.",
         diagnostico="Recuperada.",
         ordenes=[("HEMOGRAMA", "Normal", "Control.", [("MUE-2026-0018", "SANGRE")])]),
    dict(clave="c20", mascota="toby", clinica="Centro", veterinario="MP-1001",
         inicio="2026-10-20 09:00:00", duracion=30, costo=12000.0,
         motivo="Control de peso.",
         diagnostico="Bajó 2 kg; continúa plan alimentario.",
         ordenes=[("PERFIL_BIOQUIMICO", "Normal", "Control de lípidos.", [("MUE-2026-0019", "SUERO")])]),
    dict(clave="c21", mascota="simba", clinica="Cerro", veterinario="MP-1004",
         inicio="2026-10-28 15:00:00", duracion=30, costo=15000.0,
         motivo="Control renal semestral.",
         diagnostico="Pendiente de resultados.",
         ordenes=[("URIANALISIS", "Normal", "Control.", [("MUE-2026-0020", "ORINA")]),
                  ("PERFIL_BIOQUIMICO", "Normal", "Control.", [("MUE-2026-0021", "SUERO")])]),
    dict(clave="c22", mascota="pipo", clinica="Nueva Córdoba", veterinario="MP-1001",
         inicio="2026-10-30 17:30:00", duracion=30, costo=15000.0,
         motivo="Pérdida de plumas.",
         diagnostico="Muda anormal por estrés.",
         tratamientos=[("Suplemento vitamínico", "Vitaminas aviares", "5 gotas en el bebedero", 30)]),
    dict(clave="c23", mascota="kiwi", clinica="Nueva Córdoba", veterinario="MP-1001",
         inicio="2026-11-03 10:00:00", duracion=30, costo=12000.0,
         motivo="Control general.",
         diagnostico="Paciente sana."),
    dict(clave="c24", mascota="pelusa", clinica="Cerro", veterinario="MP-1003",
         inicio="2026-11-04 11:00:00", duracion=30, costo=14000.0,
         motivo="Lesiones en la piel y caída de pelo.",
         diagnostico="Sospecha de dermatofitosis.",
         tratamientos=[("Baños antifúngicos", "Clorhexidina + miconazol", "1 baño cada 3 días", 21)],
         ordenes=[("CITOLOGIA", "Normal", "Raspaje cutáneo.", [("MUE-2026-0022", "HISOPADO")])]),
    dict(clave="c25", mascota="coco", clinica="Centro", veterinario="MP-1002",
         inicio="2026-11-09 09:00:00", duracion=30, costo=13000.0,
         motivo="Control postquirúrgico del nódulo.",
         diagnostico="Herida cicatrizada.",
         ordenes=[("HEMOGRAMA", "Normal", "Control.", [("MUE-2026-0023", "SANGRE")])]),
    dict(clave="c26", mascota="milo", clinica="Centro", veterinario="MP-1003",
         inicio="2026-11-09 09:30:00", duracion=30, costo=13000.0,
         motivo="Control de enteropatía.",
         diagnostico="Mejoría parcial.",
         ordenes=[("COPROPARASITOLOGICO", "Normal", "Repetición: la muestra anterior fue rechazada.",
                   [("MUE-2026-0024", "MATERIA_FECAL")])]),
    dict(clave="c27", mascota="max", clinica="Nueva Córdoba", veterinario="MP-1001",
         inicio="2026-11-10 10:00:00", duracion=30, costo=14000.0,
         motivo="Vómitos tras cambio de alimento.",
         diagnostico="Intolerancia alimentaria.",
         ordenes=[("HEMOGRAMA", "Urgente", "Descartar infección.", [("MUE-2026-0025", "SANGRE")])]),
    dict(clave="c28", mascota="lola", clinica="Centro", veterinario="MP-1001",
         inicio="2026-11-10 16:00:00", duracion=30, costo=12000.0,
         motivo="Control de discopatía.",
         diagnostico="Evolución favorable.",
         ordenes=[("PERFIL_BIOQUIMICO", "Normal", "Control por uso de antiinflamatorios.",
                   [("MUE-2026-0026", "SUERO")])]),
    dict(clave="c29", mascota="nala", clinica="Cerro", veterinario="MP-1003",
         inicio="2026-11-11 09:00:00", duracion=30, costo=12000.0,
         motivo="Prequirúrgico de castración.",
         diagnostico="Apta para cirugía, pendiente de análisis.",
         ordenes=[("HEMOGRAMA", "Normal", "Prequirúrgico.", [("MUE-2026-0027", "SANGRE")]),
                  ("PERFIL_BIOQUIMICO", "Normal", "Prequirúrgico.", [("MUE-2026-0028", "SUERO")])]),
    dict(clave="c30", mascota="michi", clinica="Cerro", veterinario="MP-1004",
         inicio="2026-11-11 15:00:00", duracion=40, costo=17000.0,
         motivo="Control de enfermedad renal crónica."),
)

# Los remitos se procesan en orden cronológico: una conservadora sólo se puede volver
# a usar después de que el laboratorio recibe el remito anterior que la ocupaba.
#   despacho  = (fecha_hora, clave_transportista) o None si quedó precintado.
#   recepcion = (fecha_hora, estado_precinto, observaciones) o None si sigue en tránsito.
REMITOS: tuple[dict, ...] = (
    dict(numero="REM-2026-0001", clinica="Centro", conservadora="CONS-001", precinto="PREC-2026-0001",
         muestras=["MUE-2026-0001", "MUE-2026-0002", "MUE-2026-0003"], creacion="2026-08-05 08:00:00",
         despacho=("2026-08-05 09:00:00", "LSC"),
         recepcion=("2026-08-05 13:30:00", "Intacto", "Cadena de frío conforme (4 °C).")),
    dict(numero="REM-2026-0002", clinica="Nueva Córdoba", conservadora="CONS-002", precinto="PREC-2026-0002",
         muestras=["MUE-2026-0004", "MUE-2026-0005"], creacion="2026-08-11 08:30:00",
         despacho=("2026-08-11 09:15:00", "BIO"),
         recepcion=("2026-08-11 15:00:00", "Roto",
                    "Precinto cortado y conservadora abierta durante el traslado.")),
    dict(numero="REM-2026-0003", clinica="Cerro", conservadora="CONS-003", precinto="PREC-2026-0003",
         muestras=["MUE-2026-0006", "MUE-2026-0007", "MUE-2026-0008"], creacion="2026-08-21 08:00:00",
         despacho=("2026-08-21 08:45:00", "LSC"),
         recepcion=("2026-08-21 12:10:00", "Intacto", "")),
    dict(numero="REM-2026-0004", clinica="Centro", conservadora="CONS-001", precinto="PREC-2026-0004",
         muestras=["MUE-2026-0009", "MUE-2026-0010"], creacion="2026-09-02 08:00:00",
         despacho=("2026-09-02 08:30:00", "BIO"),
         recepcion=("2026-09-02 14:45:00", "Violado",
                    "El número de precinto no coincide con el remito; signos de manipulación.")),
    dict(numero="REM-2026-0005", clinica="Cerro", conservadora="CONS-003", precinto="PREC-2026-0005",
         muestras=["MUE-2026-0011", "MUE-2026-0012", "MUE-2026-0013"], creacion="2026-09-11 08:00:00",
         despacho=("2026-09-11 08:40:00", "LSC"),
         recepcion=("2026-09-11 11:20:00", "Intacto", "Biopsias congeladas a -15 °C.")),
    dict(numero="REM-2026-0006", clinica="Nueva Córdoba", conservadora="CONS-002", precinto="PREC-2026-0006",
         muestras=["MUE-2026-0014", "MUE-2026-0015"], creacion="2026-09-15 19:00:00",
         despacho=("2026-09-15 19:30:00", "BIO"),
         recepcion=("2026-09-15 22:00:00", "Intacto", "Envío de guardia.")),
    dict(numero="REM-2026-0007", clinica="Nueva Córdoba", conservadora="CONS-001", precinto="PREC-2026-0007",
         muestras=["MUE-2026-0016"], creacion="2026-09-23 08:00:00",
         despacho=("2026-09-23 08:30:00", "BIO"),
         recepcion=("2026-09-23 12:00:00", "Intacto", "")),
    dict(numero="REM-2026-0008", clinica="Cerro", conservadora="CONS-003", precinto="PREC-2026-0008",
         muestras=["MUE-2026-0017"], creacion="2026-10-08 08:00:00",
         despacho=("2026-10-08 08:30:00", "LSC"),
         recepcion=("2026-10-08 11:00:00", "Intacto", "")),
    dict(numero="REM-2026-0009", clinica="Centro", conservadora="CONS-001", precinto="PREC-2026-0009",
         muestras=["MUE-2026-0018", "MUE-2026-0019"], creacion="2026-10-21 08:00:00",
         despacho=("2026-10-21 08:30:00", "BIO"),
         recepcion=("2026-10-21 13:00:00", "Intacto", "")),
    dict(numero="REM-2026-0010", clinica="Cerro", conservadora="CONS-001", precinto="PREC-2026-0010",
         muestras=["MUE-2026-0020", "MUE-2026-0021", "MUE-2026-0022"], creacion="2026-11-05 08:00:00",
         despacho=("2026-11-05 08:30:00", "LSC"),
         recepcion=("2026-11-05 12:00:00", "Intacto", "")),
    # Queda en tránsito (CONS-002 ocupada).
    dict(numero="REM-2026-0011", clinica="Centro", conservadora="CONS-002", precinto="PREC-2026-0011",
         muestras=["MUE-2026-0023", "MUE-2026-0024"], creacion="2026-11-10 08:00:00",
         despacho=("2026-11-10 08:45:00", "LSC"), recepcion=None),
    # Queda precintado sin despachar (CONS-003 ocupada).
    dict(numero="REM-2026-0012", clinica="Nueva Córdoba", conservadora="CONS-003", precinto="PREC-2026-0012",
         muestras=["MUE-2026-0025"], creacion="2026-11-10 12:00:00",
         despacho=None, recepcion=None),
)
# Quedan en estado 'Extraida' (pendientes de empaquetar): MUE-2026-0026 (Centro),
# MUE-2026-0027 y MUE-2026-0028 (Cerro).

# Muestras recibidas que no se analizan, para probar el Proceso 7 desde la interfaz:
# MUE-2026-0021 y MUE-2026-0022.
# (codigo_muestra, matricula_bioquimico, fecha_hora, valores_medidos, conclusion)
RESULTADOS: tuple[tuple[str, str, str, str, str], ...] = (
    ("MUE-2026-0001", "BQ-2001", "2026-08-06 10:00:00",
     "Hto 48 %; Hb 16,2 g/dl; GB 9.800/µl; Plaquetas 310.000/µl",
     "Hemograma dentro de parámetros normales."),
    ("MUE-2026-0002", "BQ-2001", "2026-08-06 11:30:00",
     "ALT 62 U/l; FAS 140 U/l; Urea 38 mg/dl; Creatinina 1,1 mg/dl; Colesterol 310 mg/dl",
     "Hipercolesterolemia leve compatible con sobrepeso."),
    ("MUE-2026-0003", "BQ-2002", "2026-08-07 09:00:00",
     "Método de Willis y Sheather: negativo",
     "No se observan elementos parasitarios."),
    ("MUE-2026-0006", "BQ-2002", "2026-08-22 09:15:00",
     "Urea 98 mg/dl; Creatinina 2,4 mg/dl; Fósforo 6,1 mg/dl",
     "Azotemia renal compatible con ERC estadio 2-3 (IRIS)."),
    ("MUE-2026-0007", "BQ-2002", "2026-08-22 10:00:00",
     "Densidad 1,018; Proteínas ++; Sedimento sin particularidades",
     "Isostenuria con proteinuria moderada."),
    ("MUE-2026-0008", "BQ-2001", "2026-08-22 11:00:00",
     "Hto 41 %; Hb 13,8 g/dl; GB 11.200/µl",
     "Hemograma sin alteraciones relevantes."),
    ("MUE-2026-0011", "BQ-2001", "2026-09-12 09:00:00",
     "Hto 29 %; GB 6.400/µl; Heterófilos 58 %",
     "Valores dentro del rango de referencia para Iguana iguana."),
    ("MUE-2026-0012", "BQ-2002", "2026-09-14 16:00:00",
     "Lipoma bien diferenciado; márgenes quirúrgicos libres",
     "Lesión benigna. No requiere tratamiento adicional."),
    ("MUE-2026-0013", "BQ-2002", "2026-09-12 12:00:00",
     "Adipocitos maduros sin atipia",
     "Citología compatible con lipoma."),
    ("MUE-2026-0014", "BQ-2001", "2026-09-16 08:30:00",
     "Hto 52 %; GB 17.500/µl; Neutrófilos 82 %",
     "Leucocitosis neutrofílica leve por estrés/inflamación."),
    ("MUE-2026-0015", "BQ-2001", "2026-09-16 09:30:00",
     "ALT 45 U/l; Urea 42 mg/dl; Creatinina 1,0 mg/dl; Glucosa 110 mg/dl",
     "Perfil bioquímico normal."),
    ("MUE-2026-0016", "BQ-2002", "2026-09-26 10:00:00",
     "Staphylococcus pseudintermedius; sensible a enrofloxacina; resistente a amoxicilina",
     "Se sugiere tratamiento tópico con enrofloxacina."),
    ("MUE-2026-0017", "BQ-2001", "2026-10-09 09:00:00",
     "Urea 52 mg/dl; Creatinina 1,4 mg/dl; Potasio 4,6 mEq/l",
     "Función renal conservada bajo tratamiento."),
    ("MUE-2026-0018", "BQ-2002", "2026-10-23 09:00:00",
     "Hto 38 %; Hb 12,6 g/dl; GB 8.900/µl",
     "Hemograma normal."),
    ("MUE-2026-0019", "BQ-2001", "2026-10-23 10:30:00",
     "Colesterol 240 mg/dl; Triglicéridos 95 mg/dl",
     "Mejoría del perfil lipídico respecto del control anterior."),
    ("MUE-2026-0020", "BQ-2002", "2026-11-06 09:00:00",
     "Densidad 1,022; Proteínas +; Sin cristales",
     "Leve proteinuria, sin cambios respecto del control anterior."),
)

# Las consultas no listadas quedan sin facturar para probar el Proceso 7 desde la interfaz.
# (clave_consulta, estrategia, fecha_hora_emision)
COMPROBANTES: tuple[tuple[str, str, str], ...] = (
    ("c01", "Tarifa Estándar", "2026-08-07 18:00:00"),
    ("c02", "Tarifa Convenio Red", "2026-08-07 18:10:00"),
    ("c03", "Tarifa Estándar", "2026-08-06 12:00:00"),
    ("c04", "Tarifa Estándar", "2026-08-11 18:00:00"),
    ("c06", "Tarifa Urgencia", "2026-08-22 18:00:00"),
    ("c07", "Tarifa Convenio Red", "2026-08-22 18:15:00"),
    ("c10", "Tarifa Estándar", "2026-09-12 18:00:00"),
    ("c12", "Tarifa Urgencia", "2026-09-14 18:00:00"),
    ("c13", "Tarifa Urgencia", "2026-09-16 12:00:00"),
    ("c14", "Tarifa Convenio Red", "2026-09-26 18:00:00"),
    ("c15", "Tarifa Estándar", "2026-10-01 11:00:00"),
    ("c16", "Tarifa Convenio Red", "2026-10-05 10:00:00"),
    ("c17", "Tarifa Convenio Red", "2026-10-09 18:00:00"),
    ("c19", "Tarifa Estándar", "2026-10-23 18:00:00"),
    ("c20", "Tarifa Estándar", "2026-10-23 18:05:00"),
    ("c22", "Tarifa Estándar", "2026-10-30 18:30:00"),
)


# ======================================================================================
# Carga
# ======================================================================================

def _sumar_minutos(fecha_hora: str, minutos: int) -> str:
    """Devuelve la fecha y hora desplazada en la cantidad de minutos indicada."""
    instante = datetime.strptime(fecha_hora, FORMATO_FECHA_HORA) + timedelta(minutes=minutos)
    return instante.strftime(FORMATO_FECHA_HORA)


def cargar_datos_prueba(conexion: ConexionBD) -> dict[str, int]:
    """
    Carga el set de datos de prueba completo a través de la capa de servicios.

    Returns:
        Cantidad de registros cargados por tipo de entidad.
    """
    sujeto_eventos = SujetoEventos()
    sujeto_eventos.suscribir(ObservadorAuditoria())
    clinica = ServicioClinica(conexion=conexion)
    logistica = ServicioLogistica(conexion=conexion, sujeto_eventos=sujeto_eventos)
    laboratorio = ServicioLaboratorio(conexion=conexion, sujeto_eventos=sujeto_eventos)

    # Diccionarios de búsqueda de los catálogos y entidades precargadas.
    especies = {e["nombre"]: e["id"] for e in clinica.listar_especies()}
    clinicas = {c["nombre"]: c["id"] for c in clinica.listar_clinicas()}
    veterinarios = {v["matricula"]: v["id"] for v in clinica.listar_veterinarios()}
    tipos_estudio = {t["codigo"]: t["id"] for t in clinica.listar_tipos_estudio()}
    tipos_muestra = {t["codigo"]: t["id"] for t in clinica.listar_tipos_muestra()}
    vacunas = {(v["nombre"], v["especie_id"]): v["id"] for v in clinica.listar_catalogo_vacunas()}
    laboratorios = {lab["nombre"]: lab["id"] for lab in logistica.listar_laboratorios()}
    transportistas = {t["cuit_dni"]: t["id"] for t in logistica.listar_transportistas()}
    conservadoras = {
        fila["codigo"]: fila["id"]
        for fila in conexion.consultar_todos("SELECT id, codigo FROM conservadoras")
    }
    bioquimicos = {p["matricula"]: p["id"] for p in laboratorio.listar_profesionales_laboratorio()}

    # Proceso 1: clientes.
    clientes: dict[str, int] = {}
    for dni, nombre, apellido, telefono, email, direccion in CLIENTES:
        cliente = clinica.registrar_cliente(dni, nombre, apellido, telefono, email, direccion)
        clientes[dni] = cliente.id

    # Proceso 2: mascotas con su historia clínica y antecedentes de vacunación.
    mascotas: dict[str, int] = {}
    especie_de_mascota: dict[str, int] = {}
    for (clave, nombre, especie, raza, edad, sexo, dni, apertura,
         antecedentes, alergias) in MASCOTAS:
        mascota = clinica.registrar_mascota(
            nombre=nombre,
            especie_id=especies[especie],
            edad=edad,
            sexo=sexo,
            cliente_id=clientes[dni],
            raza=raza,
            fecha_apertura_historia=apertura,
            antecedentes=antecedentes,
            alergias=alergias,
        )
        mascotas[clave] = mascota.id
        especie_de_mascota[clave] = especies[especie]

    for clave, nombre_vacuna, fecha in VACUNAS_PREVIAS:
        clinica.aplicar_vacuna(
            mascota_id=mascotas[clave],
            vacuna_id=vacunas[(nombre_vacuna, especie_de_mascota[clave])],
            fecha_aplicacion=fecha,
        )

    # Proceso 3: consultas, tratamientos, vacunas, órdenes de derivación y muestras.
    consultas: dict[str, int] = {}
    muestras: dict[str, int] = {}
    for datos in CONSULTAS:
        consulta, _ = clinica.registrar_consulta_medica(
            mascota_id=mascotas[datos["mascota"]],
            clinica_id=clinicas[CLINICAS[datos["clinica"]]],
            veterinario_id=veterinarios[datos["veterinario"]],
            fecha_hora_inicio=datos["inicio"],
            motivo=datos["motivo"],
            duracion_minutos=datos["duracion"],
            diagnostico=datos.get("diagnostico"),
            costo_consulta=datos["costo"],
            tratamientos=[
                Tratamiento(None, 0, descripcion, medicamento, dosis, dias)
                for descripcion, medicamento, dosis, dias in datos.get("tratamientos", [])
            ],
            vacunas_aplicadas_ids=[
                vacunas[(nombre, especies[especie])]
                for nombre, especie in datos.get("vacunas", [])
            ],
        )
        consultas[datos["clave"]] = consulta.id

        for codigo_estudio, prioridad, indicaciones, muestras_orden in datos.get("ordenes", []):
            orden = clinica.emitir_orden_derivacion(
                consulta_id=consulta.id,
                tipo_estudio_id=tipos_estudio[codigo_estudio],
                indicaciones=indicaciones,
                prioridad=prioridad,
                fecha_hora_emision=_sumar_minutos(datos["inicio"], 20),
            )
            for codigo_muestra, tipo in muestras_orden:
                muestra = clinica.extraer_muestra_biologica(
                    orden_id=orden.id,
                    codigo_muestra=codigo_muestra,
                    tipo_muestra_id=tipos_muestra[tipo],
                    fecha_hora_extraccion=_sumar_minutos(datos["inicio"], 25),
                )
                muestras[codigo_muestra] = muestra.id

    # Procesos 4, 5 y 6: empaquetado, despacho y recepción en el laboratorio.
    for datos in REMITOS:
        remito = logistica.empaquetar_muestras(
            numero_remito=datos["numero"],
            clinica_origen_id=clinicas[CLINICAS[datos["clinica"]]],
            laboratorio_destino_id=laboratorios[LABORATORIO],
            conservadora_id=conservadoras[datos["conservadora"]],
            numero_serie_precinto=datos["precinto"],
            muestras_ids=[muestras[codigo] for codigo in datos["muestras"]],
            fecha_hora=datos["creacion"],
        )
        if datos["despacho"] is not None:
            fecha_despacho, transportista = datos["despacho"]
            logistica.despachar_remito(
                remito_id=remito.id,
                transportista_id=transportistas[TRANSPORTISTAS[transportista]],
                fecha_hora_despacho=fecha_despacho,
            )
        if datos["recepcion"] is not None:
            fecha_recepcion, estado_precinto, observaciones = datos["recepcion"]
            logistica.recibir_remito_en_laboratorio(
                remito_id=remito.id,
                estado_precinto=estado_precinto,
                fecha_hora_recepcion=fecha_recepcion,
                observaciones=observaciones,
            )

    # Proceso 7: resultados bioquímicos y comprobantes de atención.
    for codigo, matricula, fecha, valores, conclusion in RESULTADOS:
        laboratorio.registrar_resultado_analisis(
            muestra_id=muestras[codigo],
            profesional_laboratorio_id=bioquimicos[matricula],
            valores_medidos=valores,
            conclusion=conclusion,
            fecha_hora_analisis=fecha,
        )

    for clave, estrategia, fecha in COMPROBANTES:
        consulta_id = consultas[clave]
        # Misma numeración que propone la interfaz, para no generar duplicados.
        laboratorio.emitir_comprobante_atencion(
            consulta_id=consulta_id,
            numero_comprobante=f"FAC-0001-{consulta_id:06d}",
            estrategia=estrategia,
            fecha_hora_emision=fecha,
        )

    return {
        "Clientes": len(clientes),
        "Mascotas": len(mascotas),
        "Vacunas previas": len(VACUNAS_PREVIAS),
        "Consultas": len(consultas),
        "Muestras": len(muestras),
        "Remitos": len(REMITOS),
        "Resultados": len(RESULTADOS),
        "Comprobantes": len(COMPROBANTES),
    }


# ======================================================================================
# Ejecución manual
# ======================================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="Carga un set de datos de prueba completo.")
    parser.add_argument(
        "--reiniciar",
        action="store_true",
        help="Respalda la base actual en veterinaria.db.bak y la recrea desde cero.",
    )
    argumentos = parser.parse_args()

    if argumentos.reiniciar and RUTA_BD_POR_DEFECTO.exists():
        respaldo = RUTA_BD_POR_DEFECTO.with_suffix(".db.bak")
        shutil.move(RUTA_BD_POR_DEFECTO, respaldo)
        print(f"Base anterior respaldada en: {respaldo}")

    conexion = inicializar_base_datos()
    try:
        if conexion.consultar_uno("SELECT COUNT(*) FROM clientes")[0] > 0:
            print(
                "La base ya tiene clientes cargados. Ejecute con --reiniciar para "
                "respaldarla y cargar los datos de prueba sobre una base nueva.",
                file=sys.stderr,
            )
            return 1

        cantidades = cargar_datos_prueba(conexion)
        print(f"Datos de prueba cargados en: {conexion.ruta_bd}\n")
        for entidad, cantidad in cantidades.items():
            print(f"  {entidad:<16} {cantidad:>4}")
    finally:
        conexion.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
