
from pathlib import Path
import pandas as pd
import re

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
EVIDENCIAS = BASE / "evidencias"
EVIDENCIAS.mkdir(exist_ok=True)

archivos = list(RAW.glob("*.csv"))

if len(archivos) != 1:
    raise SystemExit("Debe existir exactamente un CSV en data/raw")

df = pd.read_csv(
    archivos[0],
    sep=",",
    encoding="utf-8-sig",
    low_memory=False
)

columnas = ["hash", "subject", "body", "Label"]

for columna in columnas:
    if columna not in df.columns:
        raise SystemExit(f"Falta la columna: {columna}")

# Normalizar etiquetas para la auditoria
etiquetas = (
    df["Label"]
    .astype("string")
    .str.strip()
    .str.lower()
)

# Revisar contenido util
asuntos = df["subject"].fillna("").astype(str)
cuerpos = df["body"].fillna("").astype(str)

sin_texto = (
    asuntos.str.strip().eq("") &
    cuerpos.str.strip().eq("")
)

# Comparacion exacta de texto normalizado
def normalizar(texto):
    return re.sub(r"\s+", " ", texto).strip().lower()

contenido = (
    asuntos.map(normalizar) +
    "\n" +
    cuerpos.map(normalizar)
)

# Revisar identificadores duplicados
hashes = df["hash"].astype("string").str.strip()
hashes_validos = hashes.dropna()
hashes_validos = hashes_validos[hashes_validos.ne("")]

duplicados_hash = hashes_validos.duplicated().sum()
duplicados_texto = contenido.duplicated().sum()

# Identificar textos asociados con distintas etiquetas
revision = pd.DataFrame({
    "contenido": contenido,
    "etiqueta": etiquetas
})

conflictos = (
    revision.groupby("contenido")["etiqueta"]
    .nunique(dropna=True)
    .gt(1)
    .sum()
)

reporte = [
    "AUDITORIA DE CALIDAD - SPAPHISH",
    "================================",
    f"Total de registros: {len(df)}",
    "",
    "DISTRIBUCION DE ETIQUETAS:",
    etiquetas.value_counts(dropna=False).to_string(),
    "",
    f"Registros sin asunto ni cuerpo: {sin_texto.sum()}",
    f"Hashes faltantes: {len(df) - len(hashes_validos)}",
    f"Hashes repetidos: {duplicados_hash}",
    f"Textos repetidos: {duplicados_texto}",
    f"Textos con etiquetas contradictorias: {conflictos}",
]

resultado = "\n".join(map(str, reporte))

print(resultado)

salida = EVIDENCIAS / "02_auditoria_calidad.txt"
salida.write_text(resultado, encoding="utf-8")

print("\nReporte guardado en:", salida)
