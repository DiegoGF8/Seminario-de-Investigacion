
from pathlib import Path
from datetime import datetime
import re
import pandas as pd

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
EVIDENCIAS = BASE / "evidencias"

EVIDENCIAS.mkdir(exist_ok=True)

# Cargar archivos originales
archivos = list(RAW.glob("*.csv"))

if len(archivos) != 1:
    raise SystemExit("Se requiere exactamente un CSV.")

df = pd.read_csv(
    archivos[0],
    sep=",",
    encoding="utf-8-sig",
    low_memory=False
)

manifest = pd.read_csv(
    PROCESSED / "manifiesto_particiones.csv"
)

# Verificar correspondencia
if len(df) != len(manifest):
    raise SystemExit("Cantidad de registros inconsistente.")

if not (
    manifest["row_id"].to_numpy()
    == range(len(df))
).all():
    raise SystemExit("Orden de registros incorrecto.")

if not (
    df["hash"].astype(str).to_numpy()
    == manifest["hash"].astype(str).to_numpy()
).all():
    raise SystemExit("Hashes inconsistentes.")

# Solo entrenamiento y validacion
mask = manifest["particion"].isin(
    ["entrenamiento", "validacion"]
)

if mask.sum() != 595:
    raise SystemExit("Desarrollo diferente de 595 registros.")

datos = df.loc[mask]
particiones = manifest.loc[mask, "particion"]

textos = (
    datos["subject"].fillna("").astype(str)
    + " "
    + datos["body"].fillna("").astype(str)
)

# Patrones de deteccion
P_URL = re.compile(
    r'\b(?:https?://|www\.)[^\s<>"\']+',
    re.I
)

P_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

P_DOMINIO = re.compile(
    r"(?<![\w@])(?:[a-z0-9-]+\.)+"
    r"(?:com|org|net|edu|gov|gt|es|info)\b",
    re.I
)

P_NUMERO = re.compile(r"\b\d{8,}\b")

# Tratamiento original de T6 y T7
def neutralizar_v1(texto):
    texto = P_URL.sub(" URL_NEUTRALIZADA ", texto)
    texto = P_EMAIL.sub(" EMAIL_NEUTRALIZADO ", texto)
    return re.sub(r"\s+", " ", texto).strip()

# Tratamiento ampliado propuesto
def neutralizar_v2(texto):
    texto = neutralizar_v1(texto)
    texto = P_DOMINIO.sub(
        " DOMINIO_NEUTRALIZADO ", texto
    )
    texto = P_NUMERO.sub(
        " NUMERO_NEUTRALIZADO ", texto
    )
    return re.sub(r"\s+", " ", texto).strip()

version_1 = textos.map(neutralizar_v1)
version_2 = textos.map(neutralizar_v2)

# Comparar cambios
modificados = int(
    (version_1 != version_2).sum()
)

def contar(serie, patron):
    return int(serie.map(
        lambda texto: bool(patron.search(texto))
    ).sum())

# Revisar que la nueva version no cree
# textos identicos entre entrenamiento y validacion
revision = pd.DataFrame({
    "texto": version_2,
    "particion": particiones
})

cruces = int(
    revision.groupby("texto")["particion"]
    .nunique()
    .gt(1)
    .sum()
)

reporte = [
    "T12 - PROPUESTA DE NEUTRALIZACION V2",
    "===================================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    f"Registros de desarrollo: {len(datos)}",
    "Prueba final: NO UTILIZADA",
    "",
    "ANTES DE LA AMPLIACION:",
    f"Dominios residuales: {contar(version_1, P_DOMINIO)}",
    f"Numeros largos residuales: {contar(version_1, P_NUMERO)}",
    "",
    "DESPUES DE LA AMPLIACION:",
    f"URL residuales: {contar(version_2, P_URL)}",
    f"Emails residuales: {contar(version_2, P_EMAIL)}",
    f"Dominios residuales: {contar(version_2, P_DOMINIO)}",
    f"Numeros largos residuales: {contar(version_2, P_NUMERO)}",
    "",
    f"Mensajes modificados: {modificados}",
    f"Textos identicos entre particiones: {cruces}",
    "",
    "ESTADO: PROPUESTA METODOLOGICA",
    "Los datos originales no fueron modificados.",
    "Los clasificadores no fueron reentrenados.",
    "No se certifica anonimato completo.",
]

resultado = "\n".join(reporte)

print(resultado)

ruta = (
    EVIDENCIAS /
    "11_propuesta_neutralizacion_v2.txt"
)

ruta.write_text(
    resultado,
    encoding="utf-8"
)

print("\nReporte guardado:", ruta)

if cruces:
    print(
        "\nADVERTENCIA: revisar colisiones "
        "antes de adoptar la nueva version."
    )
