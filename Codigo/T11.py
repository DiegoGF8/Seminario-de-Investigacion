
from pathlib import Path
import pandas as pd
import re

BASE = Path(__file__).resolve().parent

df = pd.read_csv(
    next((BASE / "data" / "raw").glob("*.csv")),
    sep=",",
    encoding="utf-8-sig",
    low_memory=False
)

revision = pd.read_csv(
    BASE / "data" / "processed"
    / "revision_identificadores.csv"
)

P_URL = re.compile(
    r'\b(?:https?://|www\.)[^\s<>"\']+',
    re.I
)
P_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
P_DOMINIO = re.compile(
    r"\b(?:[a-z0-9-]+\.)+"
    r"(?:com|org|net|edu|gov|gt|es|info)\b",
    re.I
)
P_NUMERO = re.compile(r"\b\d{8,}\b")

resultados = []

for _, fila in revision.iterrows():
    indice = int(fila["row_id"])

    texto = (
        str(df.iloc[indice]["subject"])
        + " "
        + str(df.iloc[indice]["body"])
    )

    texto = P_URL.sub(" URL_NEUTRALIZADA ", texto)
    texto = P_EMAIL.sub(" EMAIL_NEUTRALIZADO ", texto)

    dominios = sorted(set(
        P_DOMINIO.findall(texto)
    ))

    numeros = P_NUMERO.findall(texto)

    resultados.append({
        "row_id": indice,
        "particion": fila["particion"],
        "dominios_detectados": "; ".join(dominios),
        "cantidad_numeros": len(numeros),
        "longitudes_numeros": "; ".join(
            str(len(n)) for n in numeros
        ),
        "decision": "PENDIENTE",
        "justificacion": ""
    })

salida = pd.DataFrame(resultados)

ruta = (
    BASE / "data" / "processed"
    / "revision_manual_local.csv"
)

salida.to_csv(
    ruta, index=False, encoding="utf-8-sig"
)

reporte = (
    "T11 - REVISION PRELIMINAR\n"
    "========================\n"
    f"Registros pendientes: {len(salida)}\n"
    "Se generaron indicadores para revision manual.\n"
    "Prueba final: NO UTILIZADA\n"
    "Modelos: SIN MODIFICACIONES\n"
)

print(reporte)
print("Archivo generado:", ruta)

(BASE / "evidencias"
 / "10_preparacion_revision_manual.txt").write_text(
    reporte, encoding="utf-8"
)
