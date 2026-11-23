
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError
import hashlib
import json

BASE = Path(__file__).resolve().parent
EVIDENCIAS = BASE / "evidencias"
EVIDENCIAS.mkdir(exist_ok=True)

API = "http://127.0.0.1:11434"
MODELO = "llama3.2:3b"

PARAMETROS = {
    "temperature": 0.3,
    "seed": 20261121,
    "num_predict": 150
}

def consultar(endpoint, datos=None):
    cuerpo = (
        json.dumps(datos).encode("utf-8")
        if datos is not None else None
    )

    req = Request(
        API + endpoint,
        data=cuerpo,
        headers={"Content-Type": "application/json"}
    )

    with urlopen(req, timeout=240) as respuesta:
        return json.load(respuesta)

try:
    version = consultar("/api/version")
    modelos = consultar("/api/tags")
except (URLError, TimeoutError) as e:
    raise SystemExit(
        f"No se pudo conectar con Ollama: {e}"
    )

disponibles = modelos.get("models", [])

elegido = next(
    (
        m for m in disponibles
        if m.get("name") == MODELO
    ),
    None
)

if elegido is None:
    raise SystemExit(
        f"Modelo {MODELO} no encontrado. "
        f"Ejecuta: ollama pull {MODELO}"
    )

# Prueba inocua, sin contenido del dataset
PROMPT = (
    "Reformula con otras palabras, en espanol, "
    "sin alterar el significado y en una sola frase: "
    "'La reunion del equipo sera el jueves "
    "por la tarde.'"
)

datos = {
    "model": MODELO,
    "prompt": PROMPT,
    "stream": False,
    "options": PARAMETROS
}

respuesta = consultar("/api/generate", datos)
texto = respuesta.get("response", "").strip()

if not texto:
    raise SystemExit(
        "El modelo no devolvio contenido."
    )

registro = {
    "fecha": datetime.now().astimezone().isoformat(),
    "modelo": MODELO,
    "digest_modelo": elegido.get("digest"),
    "version_ollama": version.get("version"),
    "parametros": PARAMETROS,
    "tipo_prueba": "CONEXION_INOFENSIVA",
    "entrada": PROMPT,
    "salida": texto,
    "sha256_salida": hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest(),
    "variantes_phishing_generadas": 0,
    "prueba_final_utilizada": False
}

destino = (
    EVIDENCIAS / "23_verificacion_generador.json"
)

if destino.exists():
    previo = json.loads(
        destino.read_text(encoding="utf-8")
    )
    if previo.get("digest_modelo") != elegido.get("digest"):
        raise SystemExit(
            "El modelo cambio respecto al registro previo."
        )

destino.write_text(
    json.dumps(
        registro, indent=2,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

print("T23 - VERIFICACION DEL GENERADOR")
print("================================")
print("Ollama:", version.get("version"))
print("Modelo:", MODELO)
print("Digest:", elegido.get("digest"))
print("Prueba de conexion: CORRECTA")
print("Respuesta:", texto)
print("Variantes del piloto generadas: 0")
print("Prueba final: NO UTILIZADA")
print("Evidencia:", destino)
print("\nT23 FINALIZADO")
