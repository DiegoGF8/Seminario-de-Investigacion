
from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import unicodedata
import pandas as pd

# ==========================================
# T26 - REVISION SEMANTICA DE CONTROLES
# SEMINARIO DE INVESTIGACION 2
# ==========================================

BASE = Path(__file__).resolve().parent
EVIDENCIAS = BASE / "evidencias"

ORIGEN = EVIDENCIAS / "25_control_reformulacion.json"

SALIDA_CSV = EVIDENCIAS / "26_revision_semantica.csv"
SALIDA_JSON = EVIDENCIAS / "26_revision_semantica.json"
SALIDA_TXT = EVIDENCIAS / "26_resumen_revision.txt"

if not ORIGEN.is_file():
    raise SystemExit("ERROR: No existe evidencia T25.")

datos = json.loads(
    ORIGEN.read_text(encoding="utf-8")
)

# Decisiones basadas en la revision
# de las tres respuestas observadas.

REVISIONES = {
    "CONTROL_001": {
        "esperado": (
            "El taller de fotografia comenzara "
            "el lunes a las diez de la manana."
        ),
        "decision": "APROBADO",
        "justificacion": (
            "Reformulacion equivalente. "
            "Conserva actividad, fecha y hora."
        )
    },
    "CONTROL_002": {
        "esperado": (
            "El equipo recibira el informe "
            "mensual el proximo viernes."
        ),
        "decision": "RECHAZADO",
        "justificacion": (
            "Repite el mensaje original sin "
            "una reformulacion sustantiva."
        )
    },
    "CONTROL_003": {
        "esperado": (
            "El horario actualizado de la "
            "biblioteca para esta semana "
            "ha sido revisado."
        ),
        "decision": "RECHAZADO",
        "justificacion": (
            "Introduce una revision del horario "
            "que no consta en el original."
        )
    }
}

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caracter for caracter in texto
        if not unicodedata.combining(caracter)
    )
    return re.sub(
        r"[^a-z0-9]+", " ",
        texto.lower()
    ).strip()

if len(datos["resultados"]) != 3:
    raise SystemExit("Se esperaban tres controles.")

resultados = []

for item in datos["resultados"]:

    identificador = item["id"]

    if identificador not in REVISIONES:
        raise SystemExit(
            f"Control desconocido: {identificador}"
        )

    revision = REVISIONES[identificador]

    # Evitar registrar decisiones sobre
    # una ejecucion diferente a la revisada.
    if normalizar(item["generado"]) != normalizar(
        revision["esperado"]
    ):
        raise SystemExit(
            "La respuesta no coincide con "
            f"la captura revisada: {identificador}"
        )

    resultados.append({
        "id": identificador,
        "texto_original": item["original"],
        "texto_generado": item["generado"],
        "decision": revision["decision"],
        "justificacion": revision["justificacion"],
        "alertas_automaticas": "; ".join(
            item["alertas"]
        )
    })

tabla = pd.DataFrame(resultados)

aprobados = int(
    tabla["decision"].eq("APROBADO").sum()
)

rechazados = int(
    tabla["decision"].eq("RECHAZADO").sum()
)

tabla.to_csv(
    SALIDA_CSV,
    index=False,
    encoding="utf-8-sig"
)

registro = {
    "fecha": datetime.now().astimezone().isoformat(),
    "fase": "Revision semantica de controles",
    "modelo": datos["modelo"],
    "sha256_evidencia_t25": hashlib.sha256(
        ORIGEN.read_bytes()
    ).hexdigest(),
    "total": len(resultados),
    "aprobados": aprobados,
    "rechazados": rechazados,
    "revision": resultados,
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

reporte = [
    "T26 - REVISION SEMANTICA",
    "=======================",
    f"Fecha: {registro['fecha']}",
    f"Modelo: {datos['modelo']}",
    f"Controles evaluados: {len(resultados)}",
    f"Aprobados: {aprobados}",
    f"Rechazados: {rechazados}",
    "",
    "DECISIONES:"
]

for item in resultados:
    reporte.append(
        f"{item['id']}: {item['decision']}"
    )
    reporte.append(
        f"Motivo: {item['justificacion']}"
    )

reporte.extend([
    "",
    "Generador: FUNCIONAL",
    "Calidad de reformulacion: REQUIERE AJUSTES",
    "Variantes del dataset: 0",
    "Prueba final: NO UTILIZADA",
    "Clasificadores: SIN MODIFICACIONES",
    "",
    "T26 FINALIZADO."
])

texto = "\n".join(reporte)

SALIDA_TXT.write_text(
    texto, encoding="utf-8"
)

print(texto)

print("\nARCHIVOS GENERADOS:")
print(SALIDA_CSV)
print(SALIDA_JSON)
print(SALIDA_TXT)
