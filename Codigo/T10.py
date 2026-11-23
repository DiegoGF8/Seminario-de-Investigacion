
from pathlib import Path
import pandas as pd
import re

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
EVIDENCIAS = BASE / "evidencias"

archivo = next(RAW.glob("*.csv"))

df = pd.read_csv(
    archivo,
    sep=",",
    encoding="utf-8-sig",
    low_memory=False
)

manifest = pd.read_csv(
    PROCESSED / "manifiesto_particiones.csv"
)

assert len(df) == len(manifest)
assert (manifest["row_id"].to_numpy()
        == range(len(df))).all()

# Exclusivamente desarrollo
mask = manifest["particion"].isin(
    ["entrenamiento", "validacion"]
)

datos = df.loc[mask]
particiones = manifest.loc[mask]

textos = (
    datos["subject"].fillna("").astype(str)
    + " " +
    datos["body"].fillna("").astype(str)
)

# Repetir neutralizacion de T6/T7
def neutralizar(t):
    t = re.sub(
        r'\b(?:https?://|www\.)[^\s<>"\']+',
        " URL_NEUTRALIZADA ",
        t,
        flags=re.I
    )
    t = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        " EMAIL_NEUTRALIZADO ",
        t
    )
    return re.sub(r"\s+", " ", t).strip()

procesados = textos.map(neutralizar)

patron_dominio = re.compile(
    r"\b(?:[a-z0-9-]+\.)+"
    r"(?:com|org|net|edu|gov|gt|es|info)\b",
    re.I
)

patron_numero = re.compile(r"\b\d{8,}\b")

dominios = procesados.map(
    lambda x: bool(patron_dominio.search(x))
)

numeros = procesados.map(
    lambda x: bool(patron_numero.search(x))
)

revision = pd.DataFrame({
    "row_id": particiones["row_id"].to_numpy(),
    "particion": particiones["particion"].to_numpy(),
    "etiqueta": datos["Label"].to_numpy(),
    "revisar_dominio": dominios.to_numpy(),
    "revisar_numero": numeros.to_numpy()
})

revision = revision[
    revision["revisar_dominio"] |
    revision["revisar_numero"]
]

ruta = PROCESSED / "revision_identificadores.csv"
revision.to_csv(ruta, index=False)

reporte = (
    "T10 - REVISION DE IDENTIFICADORES\n"
    "================================\n"
    f"Mensajes de desarrollo: {mask.sum()}\n"
    f"Mensajes pendientes de revision: {len(revision)}\n"
    f"Con dominios: {dominios.sum()}\n"
    f"Con numeros largos: {numeros.sum()}\n"
    "Prueba final: NO UTILIZADA\n"
    "No se modificaron modelos ni textos.\n"
)

print(reporte)
print("Archivo generado:", ruta)

(EVIDENCIAS / "09_revision_identificadores.txt").write_text(
    reporte, encoding="utf-8"
)
