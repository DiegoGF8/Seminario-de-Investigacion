
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
import hashlib
import json
import re
import unicodedata

# ============================================
# T25 - SEGUNDA PRUEBA DE REFORMULACION
# SEMINARIO DE INVESTIGACION 2
# ============================================

BASE = Path(__file__).resolve().parent
EVIDENCIAS = BASE / "evidencias"

ORIGEN = EVIDENCIAS / "24_prueba_generador.json"
REGISTRO_MODELO = EVIDENCIAS / "23_verificacion_generador.json"
SALIDA = EVIDENCIAS / "25_control_reformulacion.json"
REPORTE = EVIDENCIAS / "25_control_reformulacion.txt"

MODELO = "llama3.2:3b"
API = "http://127.0.0.1:11434/api/generate"

PARAMETROS = {
    "temperature": 0.2,
    "top_p": 0.9,
    "seed": 20261121,
    "num_predict": 120,
    "num_ctx": 2048
}

INSTRUCCIONES = """
Eres un asistente de reformulacion de texto.

Tu tarea consiste exclusivamente en reformular
oraciones administrativas inofensivas en espanol.

REGLAS:
1. Conserva exactamente los hechos originales.
2. No inventes informacion.
3. No elimines informacion importante.
4. No cambies fechas, lugares ni cantidades.
5. No agregues interpretaciones o explicaciones.
6. Utiliza una redaccion diferente a la original.
7. Devuelve solamente una oracion reformulada.
8. No agregues enlaces ni datos de contacto.
9. Si no puedes conservar el significado,
   responde: NO_REFORMULABLE.
"""

def sha256(texto):
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    return re.sub(
        r"[^a-z0-9]+", " ",
        texto.lower()
    ).strip()

def generar(texto):
    datos = {
        "model": MODELO,
        "system": INSTRUCCIONES,
        "prompt": texto,
        "stream": False,
        "options": PARAMETROS
    }

    req = Request(
        API,
        data=json.dumps(datos).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urlopen(req, timeout=240) as respuesta:
        resultado = json.load(respuesta)

    return resultado.get("response", "").strip()

# Verificar evidencias anteriores
for ruta in [ORIGEN, REGISTRO_MODELO]:
    if not ruta.exists():
        raise SystemExit(f"Falta archivo: {ruta}")

if SALIDA.exists():
    raise SystemExit(
        "T25 ya tiene evidencia. "
        "No se sobrescribio el archivo."
    )

datos_t24 = json.loads(
    ORIGEN.read_text(encoding="utf-8")
)

datos_modelo = json.loads(
    REGISTRO_MODELO.read_text(encoding="utf-8")
)

if datos_modelo["modelo"] != MODELO:
    raise SystemExit("Modelo diferente al registrado.")

resultados = []

print("T25 - CONTROL DE REFORMULACION")
print("================================")

for item in datos_t24["resultados"]:
    identificador = item["id"]
    original = item["texto_referencia"]

    print(f"\nProcesando {identificador}")

    generado = generar(original)

    alertas = []

    if not generado:
        alertas.append("RESPUESTA_VACIA")

    if normalizar(original) == normalizar(generado):
        alertas.append("SIN_REFORMULACION_REAL")

    if generado == "NO_REFORMULABLE":
        alertas.append("NO_REFORMULABLE")

    if re.search(
        r"https?://|www\.|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        generado,
        re.I
    ):
        alertas.append("CONTACTO_O_ENLACE")

    estado = (
        "REVISAR_ALERTAS"
        if alertas else
        "PENDIENTE_REVISION_SEMANTICA"
    )

    resultados.append({
        "id": identificador,
        "original": original,
        "generado": generado,
        "sha256_original": sha256(original),
        "sha256_generado": sha256(generado),
        "alertas": alertas,
        "estado": estado,
        "equivalencia_semantica_aprobada": False
    })

    print("Original:", original)
    print("Generado:", generado)
    print("Estado:", estado)
    print("Alertas:", alertas)

registro = {
    "fecha": datetime.now().astimezone().isoformat(),
    "modelo": MODELO,
    "digest_modelo": datos_modelo["digest_modelo"],
    "parametros": PARAMETROS,
    "instrucciones": INSTRUCCIONES.strip(),
    "resultados": resultados,
    "variantes_dataset_generadas": 0,
    "prueba_final_utilizada": False
}

SALIDA.write_text(
    json.dumps(
        registro, indent=2,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

n_alertas = sum(bool(x["alertas"]) for x in resultados)

resumen = [
    "T25 - CONTROL DE REFORMULACION",
    "================================",
    f"Fecha: {registro['fecha']}",
    f"Modelo: {MODELO}",
    f"Ejemplos: {len(resultados)}",
    f"Ejemplos con alertas: {n_alertas}",
    "Validacion semantica: PENDIENTE",
    "Variantes del dataset: 0",
    "Prueba final: NO UTILIZADA",
    "",
    "T25 FINALIZADO."
]

REPORTE.write_text(
    "\n".join(resumen),
    encoding="utf-8"
)

print("\n" + "\n".join(resumen))
print("\nEvidencias guardadas:")
print(SALIDA)
print(REPORTE)
