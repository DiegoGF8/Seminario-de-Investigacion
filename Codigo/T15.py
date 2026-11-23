
from pathlib import Path
from datetime import datetime
import hashlib
import pandas as pd
import numpy as np

from neutralizacion_v2 import neutralizar_v2

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
EVIDENCIAS = BASE / "evidencias"
PILOTO = BASE / "data" / "piloto_privado"

PILOTO.mkdir(exist_ok=True)
EVIDENCIAS.mkdir(exist_ok=True)

SEMILLA = 20261121
TAMANO_PILOTO = 30

# 1. CARGAR CORPUS Y PARTICIONES
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

# 2. VERIFICACIONES DE INTEGRIDAD
if len(df) != len(manifest):
    raise SystemExit("Numero de registros inconsistente.")

if not np.array_equal(
    manifest["row_id"].to_numpy(),
    np.arange(len(df))
):
    raise SystemExit("Orden de registros incorrecto.")

if not np.array_equal(
    df["hash"].astype(str).to_numpy(),
    manifest["hash"].astype(str).to_numpy()
):
    raise SystemExit("Hashes inconsistentes.")

if not np.array_equal(
    df["Label"].to_numpy(),
    manifest["Label"].to_numpy()
):
    raise SystemExit("Etiquetas inconsistentes.")

if manifest.groupby("cluster_id")["particion"].nunique().gt(1).any():
    raise SystemExit("Fuga entre particiones.")

# 3. SELECCIONAR SOLO PHISHING DE ENTRENAMIENTO
candidatos = manifest[
    (manifest["particion"] == "entrenamiento")
    & (manifest["Label"] == 1)
].copy()

if len(candidatos) < TAMANO_PILOTO:
    raise SystemExit("No hay suficientes mensajes.")

seleccion = candidatos.sample(
    n=TAMANO_PILOTO,
    random_state=SEMILLA
).sort_values("row_id")

# 4. APLICAR NEUTRALIZACION V2
indices = seleccion["row_id"].to_numpy()

textos = (
    df.loc[indices, "subject"].fillna("").astype(str)
    + " "
    + df.loc[indices, "body"].fillna("").astype(str)
).map(neutralizar_v2)

if textos.str.strip().eq("").any():
    raise SystemExit("Se encontraron textos vacios.")

# 5. PREPARAR ARCHIVO LOCAL PARA REVISION
piloto = pd.DataFrame({
    "row_id": indices,
    "id_par": [
        f"PILOTO_{i:03d}"
        for i in range(1, TAMANO_PILOTO + 1)
    ],
    "texto_neutralizado": textos.to_numpy(),
    "estado_revision": "PENDIENTE"
})

ruta_piloto = PILOTO / "piloto_30_desarrollo.csv"

if ruta_piloto.exists():
    raise SystemExit(
        "El piloto ya existe. No se sobrescribio."
    )

piloto.to_csv(
    ruta_piloto,
    index=False,
    encoding="utf-8-sig"
)

# 6. GENERAR EVIDENCIA SIN PUBLICAR TEXTOS
h = hashlib.sha256()
h.update(ruta_piloto.read_bytes())

reporte = [
    "T15 - PREPARACION DEL PILOTO EXPERIMENTAL",
    "=======================================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    f"Semilla: {SEMILLA}",
    f"Mensajes seleccionados: {len(piloto)}",
    "Etiqueta: 1 (phishing)",
    "Origen: entrenamiento",
    "Neutralizacion: V2",
    "Prueba final: NO UTILIZADA",
    f"SHA256 piloto: {h.hexdigest()}",
    "",
    "Estado: PENDIENTE DE REVISION MANUAL",
    "No se han generado variantes IA.",
    "No se han ejecutado predicciones nuevas.",
    "No se han modificado los modelos.",
    "",
    "El archivo de textos es exclusivamente local.",
    "No enviar a API antes de revisar datos sensibles."
]

resultado = "\n".join(reporte)
print(resultado)

ruta_reporte = (
    EVIDENCIAS / "15_preparacion_piloto.txt"
)

ruta_reporte.write_text(
    resultado,
    encoding="utf-8"
)

print("\nArchivo piloto:", ruta_piloto)
print("Evidencia:", ruta_reporte)
