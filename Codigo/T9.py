
from pathlib import Path
from datetime import datetime
import re
import pandas as pd

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
EVIDENCIAS = BASE / "evidencias"

EVIDENCIAS.mkdir(exist_ok=True)

archivos = list(RAW.glob("*.csv"))
if len(archivos) != 1:
    raise SystemExit("Debe existir exactamente un CSV.")

df = pd.read_csv(
    archivos[0],
    sep=",",
    encoding="utf-8-sig",
    low_memory=False
)

manifest = pd.read_csv(
    PROCESSED / "manifiesto_particiones.csv"
)

if len(df) != len(manifest):
    raise SystemExit("Cantidad de registros inconsistente.")

if not manifest["row_id"].equals(
    pd.Series(range(len(df)), name="row_id")
):
    raise SystemExit("Orden de registros incorrecto.")

if not (
    df["hash"].astype(str).to_numpy()
    == manifest["hash"].astype(str).to_numpy()
).all():
    raise SystemExit("Hashes inconsistentes.")

# Usar exclusivamente desarrollo
mask = manifest["particion"].isin(
    ["entrenamiento", "validacion"]
)

if mask.sum() != 595:
    raise SystemExit("Cantidad de desarrollo inesperada.")

desarrollo = df.loc[mask].copy()

textos = (
    desarrollo["subject"].fillna("").astype(str)
    + " "
    + desarrollo["body"].fillna("").astype(str)
)

# Reglas actuales de T6 y T7
P_URL = re.compile(
    r"\b(?:https?://|www\.)[^\s<>\"']+",
    re.IGNORECASE
)

P_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Indicadores adicionales para revision
P_NUMEROS = re.compile(r"\b\d{8,}\b")

P_DOMINIO = re.compile(
    r"\b(?:[a-z0-9-]+\.)+"
    r"(?:com|org|net|edu|gov|gt|es|info)\b",
    re.IGNORECASE
)

def neutralizar(texto):
    texto = P_URL.sub(" URL_NEUTRALIZADA ", texto)
    texto = P_EMAIL.sub(" EMAIL_NEUTRALIZADO ", texto)
    return re.sub(r"\s+", " ", texto).strip()

procesados = textos.map(neutralizar)

def contar(patron, serie):
    return int(serie.map(
        lambda x: bool(patron.search(x))
    ).sum())

metricas = {
    "urls_originales": contar(P_URL, textos),
    "emails_originales": contar(P_EMAIL, textos),
    "urls_residuales": contar(P_URL, procesados),
    "emails_residuales": contar(P_EMAIL, procesados),
    "dominios_residuales": contar(P_DOMINIO, procesados),
    "numeros_largos_residuales": contar(P_NUMEROS, procesados)
}

reporte = [
    "T9 - AUDITORIA DE NEUTRALIZACION",
    "================================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    f"Registros de desarrollo: {len(desarrollo)}",
    "Registros de prueba final: NO UTILIZADOS",
    "",
    "RESULTADOS:"
]

for nombre, valor in metricas.items():
    reporte.append(f"{nombre}: {valor}")

reporte.extend([
    "",
    "OBSERVACIONES:",
    "Se verificaron los patrones de neutralizacion.",
    "Los dominios y numeros largos requieren",
    "revision adicional antes de usar una API externa.",
    "Los resultados son indicadores, no una",
    "certificacion de anonimato completo.",
    "",
    "No se modificaron los datos originales.",
    "No se reentrenaron los clasificadores."
])

resultado = "\n".join(reporte)
print(resultado)

ruta = EVIDENCIAS / "08_auditoria_neutralizacion.txt"
ruta.write_text(resultado, encoding="utf-8")

print("\nReporte guardado:", ruta)
