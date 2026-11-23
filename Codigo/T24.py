
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import hashlib
import json
import re
import time

# ============================================
# T24 - PRUEBA CONTROLADA DEL GENERADOR
# SEMINARIO DE INVESTIGACION 2
# ============================================

BASE = Path(__file__).resolve().parent
EVIDENCIAS = BASE / "evidencias"

EVIDENCIAS.mkdir(parents=True, exist_ok=True)

API = "http://127.0.0.1:11434"
MODELO = "llama3.2:3b"

PARAMETROS = {
    "temperature": 0.3,
    "top_p": 0.9,
    "seed": 20261121,
    "num_predict": 150,
    "num_ctx": 2048
}

# ============================================
# 1. VERIFICAR REGISTROS ANTERIORES
# ============================================

ARCHIVOS_REQUERIDOS = [
    EVIDENCIAS / "21_insumos_piloto.json",
    EVIDENCIAS / "22_protocolo_generacion.json",
    EVIDENCIAS / "23_verificacion_generador.json"
]

for archivo in ARCHIVOS_REQUERIDOS:
    if not archivo.is_file():
        raise SystemExit(
            f"ERROR: Falta el archivo {archivo}"
        )

registro_t23 = json.loads(
    ARCHIVOS_REQUERIDOS[2].read_text(
        encoding="utf-8"
    )
)

# ============================================
# 2. CONEXION LOCAL CON OLLAMA
# ============================================

def consultar(endpoint, datos=None):
    cuerpo = None

    if datos is not None:
        cuerpo = json.dumps(
            datos,
            ensure_ascii=False
        ).encode("utf-8")

    solicitud = Request(
        API + endpoint,
        data=cuerpo,
        headers={
            "Content-Type": "application/json"
        }
    )

    with urlopen(
        solicitud, timeout=240
    ) as respuesta:
        return json.load(respuesta)


try:
    version = consultar("/api/version")
    modelos = consultar("/api/tags")

except (URLError, HTTPError, TimeoutError) as error:
    raise SystemExit(
        f"ERROR: No se pudo conectar con Ollama: {error}"
    )

modelo_actual = next(
    (
        modelo
        for modelo in modelos.get("models", [])
        if modelo.get("name") == MODELO
    ),
    None
)

if modelo_actual is None:
    raise SystemExit(
        "ERROR: Modelo no instalado."
    )

DIGEST = modelo_actual.get("digest")

if DIGEST != registro_t23.get("digest_modelo"):
    raise SystemExit(
        "ERROR: El modelo difiere del registrado en T23."
    )

# ============================================
# 3. EJEMPLOS SINTETICOS INOFENSIVOS
# ============================================

EJEMPLOS = [
    {
        "id": "CONTROL_001",
        "texto": (
            "El taller de fotografia iniciara "
            "el lunes a las diez de la manana."
        )
    },
    {
        "id": "CONTROL_002",
        "texto": (
            "El equipo recibira el informe "
            "mensual el proximo viernes."
        )
    },
    {
        "id": "CONTROL_003",
        "texto": (
            "Se actualizo el horario de la "
            "biblioteca para esta semana."
        )
    }
]

# ============================================
# 4. REGLAS DE GENERACION
# ============================================

SISTEMA = (
    "Eres un asistente que reformula "
    "mensajes administrativos inofensivos. "
    "Conserva el significado original. "
    "Responde solamente con una reformulacion "
    "breve en espanol. "
    "No agregues enlaces, datos de contacto, "
    "instrucciones nuevas ni informacion personal."
)

def sha256_texto(texto):
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()


def comprobar_salida(texto):
    problemas = []

    if not texto.strip():
        problemas.append("Respuesta vacia")

    if re.search(r"https?://|www\.", texto, re.I):
        problemas.append("Posible URL")

    if re.search(
        r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        texto,
        re.I
    ):
        problemas.append("Posible email")

    return problemas

# ============================================
# 5. EJECUTAR PRUEBAS
# ============================================

resultados = []

print("T24 - PRUEBA CONTROLADA DE GENERACION")
print("====================================")
print("Modelo:", MODELO)
print("Ollama:", version.get("version"))
print("Ejemplos de control:", len(EJEMPLOS))
print()

for ejemplo in EJEMPLOS:

    print("Procesando:", ejemplo["id"])

    entrada = {
        "model": MODELO,
        "system": SISTEMA,
        "prompt": ejemplo["texto"],
        "stream": False,
        "options": PARAMETROS
    }

    inicio = time.perf_counter()

    try:
        respuesta = consultar(
            "/api/generate", entrada
        )

    except (URLError, HTTPError, TimeoutError) as error:
        raise SystemExit(
            f"Error generando {ejemplo['id']}: {error}"
        )

    duracion = time.perf_counter() - inicio

    texto_generado = respuesta.get(
        "response", ""
    ).strip()

    problemas = comprobar_salida(
        texto_generado
    )

    estado = (
        "REVISION_REQUERIDA"
        if problemas
        else "SIN_ALERTAS_AUTOMATICAS"
    )

    registro = {
        "id": ejemplo["id"],
        "texto_referencia": ejemplo["texto"],
        "texto_generado": texto_generado,
        "sha256_referencia": sha256_texto(
            ejemplo["texto"]
        ),
        "sha256_generado": sha256_texto(
            texto_generado
        ),
        "duracion_segundos": round(
            duracion, 4
        ),
        "estado": estado,
        "alertas": problemas
    }

    resultados.append(registro)

    print("Respuesta:", texto_generado)
    print("Estado:", estado)
    print("Duracion:", round(duracion, 3), "s")
    print()

# ============================================
# 6. GUARDAR EVIDENCIAS
# ============================================

registro_final = {
    "proyecto": "Seminario de Investigacion 2",
    "fase": "Prueba del generador",
    "fecha": datetime.now().astimezone().isoformat(),
    "modelo": MODELO,
    "digest": DIGEST,
    "version_ollama": version.get("version"),
    "parametros": PARAMETROS,
    "tipo_datos": "SINTETICOS_INOFENSIVOS",
    "cantidad_controles": len(EJEMPLOS),
    "variantes_dataset_generadas": 0,
    "prueba_final_utilizada": False,
    "resultados": resultados
}

ruta_json = (
    EVIDENCIAS / "24_prueba_generador.json"
)

ruta_json.write_text(
    json.dumps(
        registro_final,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)

alertas = sum(
    bool(resultado["alertas"])
    for resultado in resultados
)

resumen = [
    "T24 - VERIFICACION DEL GENERADOR",
    "================================",
    f"Fecha: {registro_final['fecha']}",
    f"Modelo: {MODELO}",
    f"Ejemplos procesados: {len(resultados)}",
    f"Respuestas con alertas: {alertas}",
    "Variantes del dataset: 0",
    "Prueba final: NO UTILIZADA",
    "Modelos clasificadores: SIN MODIFICACIONES",
    "",
    "Las respuestas requieren revision humana.",
    "No se certifica equivalencia semantica.",
    "",
    "T24 FINALIZADO."
]

texto_resumen = "\n".join(resumen)

ruta_txt = (
    EVIDENCIAS / "24_resumen_generador.txt"
)

ruta_txt.write_text(
    texto_resumen,
    encoding="utf-8"
)

print(texto_resumen)
print()
print("Evidencias:")
print(ruta_json)
print(ruta_txt)
