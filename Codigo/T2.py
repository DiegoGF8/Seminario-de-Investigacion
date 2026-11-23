
from pathlib import Path
import hashlib
import pandas as pd

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
EVIDENCIAS = BASE / "evidencias"
EVIDENCIAS.mkdir(exist_ok=True)

archivos = list(RAW.glob("*.csv"))

if len(archivos) != 1:
    print("ERROR: Se esperaba un archivo CSV.")
    print("Archivos encontrados:", archivos)
    raise SystemExit(1)

archivo = archivos[0]

# Huella digital del archivo original
sha256 = hashlib.file_digest(
    archivo.open("rb"), "sha256"
).hexdigest()

# Lectura de SpaPhish
df = pd.read_csv(
    archivo,
    sep=",",
    encoding="utf-8-sig",
    low_memory=False
)

reporte = [
    "AUDITORIA INICIAL DE SPAPHISH",
    "============================",
    f"Archivo: {archivo.name}",
    f"SHA-256: {sha256}",
    f"Total de registros: {len(df)}",
    f"Total de columnas: {len(df.columns)}",
    "",
    "COLUMNAS DISPONIBLES:"
]

reporte.extend(df.columns.astype(str).tolist())

reporte.extend([
    "",
    "VALORES FALTANTES:",
    df.isna().sum().to_string(),
    "",
    f"Filas completamente duplicadas: {df.duplicated().sum()}"
])

resultado = "\n".join(reporte)
print(resultado)

destino = EVIDENCIAS / "01_auditoria_inicial.txt"
destino.write_text(resultado, encoding="utf-8")

print("\nReporte guardado en:", destino)
