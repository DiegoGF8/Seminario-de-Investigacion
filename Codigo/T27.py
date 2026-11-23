
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
import hashlib
import json
import re
import time
import unicodedata
from difflib import SequenceMatcher

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

# ==========================================
# T27 - COMPARACION DE INSTRUCCIONES
# SEMINARIO DE INVESTIGACION 2
# ==========================================

BASE = Path(__file__).resolve().parent
EVIDENCIAS = BASE / "evidencias"
EVIDENCIAS.mkdir(parents=True, exist_ok=True)

ORIGEN = EVIDENCIAS / "25_control_reformulacion.json"
MODELO_PREVIO = EVIDENCIAS / "23_verificacion_generador.json"

SALIDA_JSON = EVIDENCIAS / "27_comparacion_prompts.json"
SALIDA_EXCEL = EVIDENCIAS / "27_revision_comparacion.xlsx"
SALIDA_TXT = EVIDENCIAS / "27_resumen_comparacion.txt"

MODELO = "llama3.2:3b"
API = "http://127.0.0.1:11434"

PARAMETROS = {
    "temperature": 0.2,
    "top_p": 0.9,
    "seed": 20261121,
    "num_predict": 120,
    "num_ctx": 2048
}

# ==========================================
# 1. DEFINIR INSTRUCCIONES
# ==========================================

PROMPT_A = """
Eres un asistente de reformulacion en espanol.

Reformula exclusivamente oraciones administrativas
inofensivas.

Reglas:
- Conserva todos los hechos originales.
- Conserva sujeto, accion, tiempo y cantidades.
- Cambia la redaccion sin cambiar el significado.
- No agregues hechos, acciones ni interpretaciones.
- No elimines informacion importante.
- No inventes fechas, lugares o datos de contacto.
- Responde solamente con la oracion reformulada.
- Si no es posible, responde NO_REFORMULABLE.
"""

PROMPT_B = """
Eres un asistente de reformulacion en espanol.

Conserva exactamente los hechos originales.
Cambia solamente la forma de expresar la informacion.

No agregues ni elimines informacion.
No cambies fechas, cantidades, sujetos o acciones.
No agregues instrucciones ni enlaces.

Ejemplo 1:
Original: La capacitacion empieza el martes.
Reformulacion: El martes comienza la capacitacion.

Ejemplo 2:
Original: El informe estara disponible el viernes.
Reformulacion: El viernes estara disponible el informe.

Devuelve solamente una oracion reformulada.
Si no puedes conservar el significado,
responde NO_REFORMULABLE.
"""

CONFIGURACIONES = {
    "A_ESTRICTA": PROMPT_A,
    "B_CON_EJEMPLOS": PROMPT_B
}

# ==========================================
# 2. FUNCIONES
# ==========================================

def sha256(texto):
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caracter for caracter in texto
        if not unicodedata.combining(caracter)
    )
    return re.sub(
        r"[^a-z0-9]+", " ", texto.lower()
    ).strip()


def consultar(endpoint, datos=None):
    contenido = None

    if datos is not None:
        contenido = json.dumps(
            datos, ensure_ascii=False
        ).encode("utf-8")

    solicitud = Request(
        API + endpoint,
        data=contenido,
        headers={"Content-Type": "application/json"}
    )

    with urlopen(solicitud, timeout=240) as respuesta:
        return json.load(respuesta)


def analizar(original, generado):
    alertas = []

    if not generado.strip():
        alertas.append("RESPUESTA_VACIA")

    if generado.strip() == "NO_REFORMULABLE":
        alertas.append("NO_REFORMULABLE")

    a = normalizar(original)
    b = normalizar(generado)

    similitud = SequenceMatcher(
        None, a, b
    ).ratio()

    if a == b:
        alertas.append("SIN_REFORMULACION_REAL")
    elif similitud > 0.95:
        alertas.append("CAMBIO_TEXTUAL_MINIMO")

    if re.search(
        r"https?://|www\.|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        generado,
        re.I
    ):
        alertas.append("CONTACTO_O_ENLACE")

    return alertas, round(similitud, 4)


# ==========================================
# 3. VERIFICAR EVIDENCIAS ANTERIORES
# ==========================================

for ruta in [ORIGEN, MODELO_PREVIO]:
    if not ruta.is_file():
        raise SystemExit(f"Archivo faltante: {ruta}")

if any(ruta.exists() for ruta in [
    SALIDA_JSON, SALIDA_EXCEL, SALIDA_TXT
]):
    raise SystemExit(
        "Ya existen evidencias de T27. "
        "No se sobrescribieron."
    )

datos_t25 = json.loads(
    ORIGEN.read_text(encoding="utf-8")
)

datos_modelo = json.loads(
    MODELO_PREVIO.read_text(encoding="utf-8")
)

controles = datos_t25["resultados"]

if len(controles) != 3:
    raise SystemExit("Se esperaban tres controles.")

# Verificar integridad de controles originales
for item in controles:
    if sha256(item["original"]) != item["sha256_original"]:
        raise SystemExit(
            f"Control alterado: {item['id']}"
        )

modelos = consultar("/api/tags")["models"]

modelo_actual = next(
    (
        m for m in modelos
        if m.get("name") == MODELO
    ),
    None
)

if modelo_actual is None:
    raise SystemExit("Modelo Ollama no disponible.")

if modelo_actual.get("digest") != datos_modelo["digest_modelo"]:
    raise SystemExit(
        "El modelo difiere del registrado en T23."
    )

# ==========================================
# 4. EJECUTAR LAS DOS CONFIGURACIONES
# ==========================================

resultados = []

print("T27 - COMPARACION DE INSTRUCCIONES")
print("=================================")
print("Modelo:", MODELO)
print("Configuraciones:", len(CONFIGURACIONES))
print("Controles:", len(controles))
print()

for configuracion, instrucciones in CONFIGURACIONES.items():

    print("CONFIGURACION:", configuracion)

    for item in controles:

        identificador = item["id"]
        original = item["original"]

        solicitud = {
            "model": MODELO,
            "system": instrucciones,
            "prompt": (
                "Reformula esta oracion:\n" + original
            ),
            "stream": False,
            "options": PARAMETROS
        }

        inicio = time.perf_counter()

        respuesta = consultar(
            "/api/generate", solicitud
        )

        duracion = time.perf_counter() - inicio

        generado = respuesta.get(
            "response", ""
        ).strip()

        alertas, similitud = analizar(
            original, generado
        )

        resultado = {
            "id": identificador,
            "configuracion": configuracion,
            "original": original,
            "generado": generado,
            "sha256_original": sha256(original),
            "sha256_generado": sha256(generado),
            "similitud_textual": similitud,
            "alertas": alertas,
            "duracion_segundos": round(duracion, 4),
            "revision_semantica": "PENDIENTE",
            "aprobacion_manual": False
        }

        resultados.append(resultado)

        print("ID:", identificador)
        print("Generado:", generado)
        print("Similitud:", similitud)
        print("Alertas:", alertas)
        print()

# ==========================================
# 5. GUARDAR RESULTADOS JSON
# ==========================================

registro = {
    "fecha": datetime.now().astimezone().isoformat(),
    "fase": "Comparacion de instrucciones",
    "modelo": MODELO,
    "digest": modelo_actual["digest"],
    "parametros": PARAMETROS,
    "configuraciones": CONFIGURACIONES,
    "resultados": resultados,
    "variantes_dataset_generadas": 0,
    "prueba_final_utilizada": False
}

SALIDA_JSON.write_text(
    json.dumps(
        registro,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)

# ==========================================
# 6. CREAR EXCEL PARA REVISION MANUAL
# ==========================================

libro = Workbook()
hoja = libro.active
hoja.title = "Revision T27"

encabezados = [
    "id_control",
    "configuracion",
    "texto_original",
    "texto_generado",
    "similitud_textual",
    "alertas",
    "conserva_significado",
    "reformulacion_real",
    "decision_manual",
    "observaciones"
]

hoja.append(encabezados)

for item in resultados:
    hoja.append([
        item["id"],
        item["configuracion"],
        item["original"],
        item["generado"],
        item["similitud_textual"],
        "; ".join(item["alertas"]),
        "PENDIENTE",
        "PENDIENTE",
        "PENDIENTE",
        ""
    ])

anchos = {
    "A": 19, "B": 23, "C": 75,
    "D": 75, "E": 20, "F": 35,
    "G": 25, "H": 25, "I": 23,
    "J": 65
}

for columna, ancho in anchos.items():
    hoja.column_dimensions[columna].width = ancho

for celda in hoja[1]:
    celda.fill = PatternFill(
        "solid", fgColor="176B55"
    )
    celda.font = Font(
        color="FFFFFF", bold=True
    )

for fila in hoja.iter_rows(min_row=2):
    for celda in fila:
        celda.alignment = Alignment(
            vertical="top",
            wrap_text=True
        )
    hoja.row_dimensions[fila[0].row].height = 66

hoja.freeze_panes = "C2"
hoja.auto_filter.ref = hoja.dimensions

libro.save(SALIDA_EXCEL)

# ==========================================
# 7. REPORTE DE EVIDENCIA
# ==========================================

alertados = sum(
    bool(item["alertas"])
    for item in resultados
)

reporte = [
    "T27 - COMPARACION DE INSTRUCCIONES",
    "=================================",
    f"Fecha: {registro['fecha']}",
    f"Modelo: {MODELO}",
    f"Controles originales: {len(controles)}",
    f"Configuraciones: {len(CONFIGURACIONES)}",
    f"Respuestas obtenidas: {len(resultados)}",
    f"Respuestas con alertas: {alertados}",
    "",
    "Revision semantica: PENDIENTE",
    "Variantes del dataset: 0",
    "Clasificadores: SIN MODIFICACIONES",
    "Prueba final: NO UTILIZADA",
    "",
    "La similitud textual no demuestra",
    "equivalencia semantica.",
    "",
    "T27 FINALIZADO."
]

resumen = "\n".join(reporte)

SALIDA_TXT.write_text(
    resumen, encoding="utf-8"
)

print(resumen)

print("\nARCHIVOS GENERADOS:")
print(SALIDA_JSON)
print(SALIDA_EXCEL)
print(SALIDA_TXT)
