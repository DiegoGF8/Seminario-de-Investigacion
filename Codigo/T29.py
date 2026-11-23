
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from difflib import SequenceMatcher
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import hashlib
import json
import re
import time
import unicodedata

# ==========================================
# T29 - VALIDACION ADICIONAL DEL GENERADOR
# SEMINARIO DE INVESTIGACION 2
# ==========================================

BASE = Path(__file__).resolve().parent
EVIDENCIAS = BASE / "evidencias"

ORIGEN = EVIDENCIAS / "28_seleccion_protocolo.json"
MODELO_PREVIO = EVIDENCIAS / "23_verificacion_generador.json"
T27 = EVIDENCIAS / "27_comparacion_prompts.json"

SALIDA_JSON = EVIDENCIAS / "29_validacion_generador.json"
SALIDA_EXCEL = EVIDENCIAS / "29_revision_controles.xlsx"
SALIDA_TXT = EVIDENCIAS / "29_resumen_validacion.txt"

API = "http://127.0.0.1:11434"
CONFIGURACION = "B_CON_EJEMPLOS"

# ==========================================
# 1. CARGAR CONFIGURACION SELECCIONADA
# ==========================================

for ruta in [ORIGEN, MODELO_PREVIO, T27]:
    if not ruta.is_file():
        raise SystemExit(f"Archivo faltante: {ruta}")

for ruta in [SALIDA_JSON, SALIDA_EXCEL, SALIDA_TXT]:
    if ruta.exists():
        raise SystemExit(
            f"Ya existe {ruta.name}. "
            "No se sobrescribieron evidencias."
        )

protocolo = json.loads(
    ORIGEN.read_text(encoding="utf-8")
)

registro_modelo = json.loads(
    MODELO_PREVIO.read_text(encoding="utf-8")
)

datos_t27 = json.loads(
    T27.read_text(encoding="utf-8")
)

if protocolo["configuracion_seleccionada"] != CONFIGURACION:
    raise SystemExit("Configuracion inesperada.")

MODELO = protocolo["modelo"]
DIGEST = protocolo["digest_modelo"]
PARAMETROS = protocolo["parametros"]
INSTRUCCIONES = protocolo["instrucciones_seleccionadas"]

if DIGEST != registro_modelo["digest_modelo"]:
    raise SystemExit("El digest no coincide con T23.")

# ==========================================
# 2. NUEVOS CONTROLES INOFENSIVOS
# ==========================================

CONTROLES = [
    (
        "CONTROL_004", "Fecha",
        "El comite publicara el acta el miercoles a las nueve."
    ),
    (
        "CONTROL_005", "Cierre",
        "La biblioteca permanecera cerrada el proximo lunes por mantenimiento."
    ),
    (
        "CONTROL_006", "Duracion",
        "La capacitacion virtual tendra una duracion de dos horas."
    ),
    (
        "CONTROL_007", "Orden temporal",
        "El personal recibira las instrucciones antes del inicio de la actividad."
    ),
    (
        "CONTROL_008", "Cantidades",
        "El informe final incluye tres tablas y dos figuras."
    ),
    (
        "CONTROL_009", "Secuencia",
        "Las solicitudes recibidas despues del viernes se revisaran el lunes."
    ),
    (
        "CONTROL_010", "Negacion",
        "El curso no se impartira durante la semana de vacaciones."
    ),
    (
        "CONTROL_011", "Tiempo pasado",
        "El inventario fue actualizado ayer por el equipo de logistica."
    ),
    (
        "CONTROL_012", "Fecha limite",
        "La encuesta estara disponible unicamente hasta el 30 de noviembre."
    ),
    (
        "CONTROL_013", "Horario",
        "El laboratorio abre a las ocho y cierra a las cuatro."
    ),
    (
        "CONTROL_014", "Entrega",
        "Los participantes deben entregar el formulario en la oficina principal."
    ),
    (
        "CONTROL_015", "Cambio de ubicacion",
        "La reunion cambio del salon A al salon C por motivos de espacio."
    )
]

# Comprobar que no repetimos los ejemplos de T27
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    return re.sub(
        r"[^a-z0-9]+", " ", texto.lower()
    ).strip()

anteriores = {
    normalizar(item["original"])
    for item in datos_t27["resultados"]
}

for _, _, texto in CONTROLES:
    if normalizar(texto) in anteriores:
        raise SystemExit(
            "Se encontro un control repetido de T27."
        )

# ==========================================
# 3. FUNCIONES
# ==========================================

def sha256(texto):
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()

def consultar(endpoint, datos=None):
    cuerpo = (
        json.dumps(
            datos, ensure_ascii=False
        ).encode("utf-8")
        if datos is not None else None
    )

    solicitud = Request(
        API + endpoint,
        data=cuerpo,
        headers={"Content-Type": "application/json"}
    )

    with urlopen(solicitud, timeout=240) as respuesta:
        return json.load(respuesta)

def verificar(original, generado):
    alertas = []

    a = normalizar(original)
    b = normalizar(generado)

    similitud = SequenceMatcher(
        None, a, b
    ).ratio()

    if not generado.strip():
        alertas.append("TEXTO_VACIO")

    if generado.strip() == "NO_REFORMULABLE":
        alertas.append("NO_REFORMULABLE")

    if a == b:
        alertas.append("SIN_REFORMULACION")

    if re.search(
        r"https?://|www\.|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        generado,
        re.I
    ):
        alertas.append("ENLACE_O_CONTACTO")

    # Alerta orientativa: los numeros escritos
    # con palabras requieren revision manual.
    numeros_originales = re.findall(r"\b\d+\b", original)
    numeros_generados = re.findall(r"\b\d+\b", generado)

    if sorted(numeros_originales) != sorted(numeros_generados):
        alertas.append("REVISAR_CANTIDADES")

    return alertas, round(similitud, 4)

# ==========================================
# 4. VERIFICAR MODELO LOCAL
# ==========================================

modelos = consultar("/api/tags")["models"]

actual = next(
    (
        m for m in modelos
        if m.get("name") == MODELO
    ),
    None
)

if actual is None:
    raise SystemExit("Modelo no disponible.")

if actual.get("digest") != DIGEST:
    raise SystemExit("El modelo ha cambiado.")

# ==========================================
# 5. GENERAR LOS 12 CONTROLES
# ==========================================

resultados = []

print("T29 - VALIDACION ADICIONAL")
print("==========================")
print("Modelo:", MODELO)
print("Configuracion:", CONFIGURACION)
print("Controles nuevos:", len(CONTROLES))
print()

for identificador, foco, original in CONTROLES:

    datos = {
        "model": MODELO,
        "system": INSTRUCCIONES,
        "prompt": "Reformula esta oracion:\n" + original,
        "stream": False,
        "options": PARAMETROS
    }

    inicio = time.perf_counter()

    respuesta = consultar("/api/generate", datos)

    duracion = time.perf_counter() - inicio

    generado = respuesta.get(
        "response", ""
    ).strip()

    alertas, similitud = verificar(
        original, generado
    )

    resultados.append({
        "id": identificador,
        "foco": foco,
        "original": original,
        "generado": generado,
        "sha256_original": sha256(original),
        "sha256_generado": sha256(generado),
        "similitud_textual": similitud,
        "alertas": alertas,
        "duracion_segundos": round(duracion, 4),
        "revision_manual": "PENDIENTE"
    })

    print("ID:", identificador)
    print("Original:", original)
    print("Generado:", generado)
    print("Similitud:", similitud)
    print("Alertas:", alertas)
    print()

# ==========================================
# 6. GUARDAR EVIDENCIA JSON
# ==========================================

registro = {
    "fecha": datetime.now().astimezone().isoformat(),
    "modelo": MODELO,
    "digest": DIGEST,
    "configuracion": CONFIGURACION,
    "parametros": PARAMETROS,
    "instrucciones": INSTRUCCIONES,
    "controles_nuevos": 12,
    "resultados": resultados,
    "variantes_dataset_generadas": 0,
    "prueba_final_utilizada": False
}

SALIDA_JSON.write_text(
    json.dumps(
        registro,
        indent=2,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

# ==========================================
# 7. CREAR EXCEL PARA REVISION
# ==========================================

libro = Workbook()
hoja = libro.active
hoja.title = "Revision T29"

hoja.append([
    "id_control",
    "foco_prueba",
    "texto_original",
    "texto_generado",
    "similitud_textual",
    "alertas",
    "conserva_significado",
    "reformulacion_real",
    "decision_manual",
    "observaciones"
])

for item in resultados:
    hoja.append([
        item["id"],
        item["foco"],
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
    "A": 18, "B": 22, "C": 75,
    "D": 75, "E": 20, "F": 32,
    "G": 24, "H": 24, "I": 22, "J": 65
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
    hoja.row_dimensions[fila[0].row].height = 65

hoja.freeze_panes = "C2"
hoja.auto_filter.ref = hoja.dimensions

libro.save(SALIDA_EXCEL)

# ==========================================
# 8. REPORTE
# ==========================================

alertados = sum(
    bool(item["alertas"])
    for item in resultados
)

reporte = [
    "T29 - VALIDACION ADICIONAL DEL GENERADOR",
    "======================================",
    f"Fecha: {registro['fecha']}",
    f"Modelo: {MODELO}",
    f"Configuracion: {CONFIGURACION}",
    f"Controles nuevos: {len(resultados)}",
    f"Controles con alertas: {alertados}",
    "Revision semantica: PENDIENTE",
    "Variantes del dataset: 0",
    "Prueba final: NO UTILIZADA",
    "Clasificadores: SIN MODIFICACIONES",
    "",
    "Las alertas son indicadores preliminares.",
    "La aceptacion requiere revision humana.",
    "",
    "T29 FINALIZADO."
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
