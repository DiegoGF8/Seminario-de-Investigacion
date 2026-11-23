
from pathlib import Path
from datetime import datetime
import hashlib
import numpy as np
import pandas as pd

# CONFIGURACION DEL EXPERIMENTO
BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
EVIDENCIAS = BASE / "evidencias"

SEMILLA = 20261121
rng = np.random.default_rng(SEMILLA)

OBJETIVO_PRUEBA = {1: 400, 0: 400}
OBJETIVO_VALIDACION = {1: 66, 0: 53}

# 1. CARGAR LOS ARCHIVOS VERIFICADOS
archivos = list(RAW.glob("*.csv"))
if len(archivos) != 1:
    raise SystemExit("Debe existir un unico CSV en data/raw")

archivo = archivos[0]

df = pd.read_csv(
    archivo,
    sep=",",
    encoding="utf-8-sig",
    low_memory=False
)

df["row_id"] = np.arange(len(df))
df["Label"] = pd.to_numeric(
    df["Label"], errors="raise"
).astype(int)

if not df["Label"].isin([0, 1]).all():
    raise SystemExit("Existen etiquetas no validas")

mapa = pd.read_csv(
    PROCESSED / "mapa_clusters.csv"
)

if len(mapa) != len(df):
    raise SystemExit("El mapa no coincide con el CSV")

if not mapa["row_id"].equals(df["row_id"]):
    raise SystemExit("El orden de registros no coincide")

if not mapa["Label"].equals(df["Label"]):
    raise SystemExit("Las etiquetas no coinciden")

df["cluster_id"] = mapa["cluster_id"]

# 2. VERIFICAR ETIQUETAS DE LOS CLUSTERS
conflictos = (
    df.groupby("cluster_id")["Label"]
    .nunique()
)

if (conflictos > 1).any():
    raise SystemExit(
        "Hay clusters con etiquetas contradictorias"
    )

grupos = (
    df.groupby(["Label", "cluster_id"])
    .size()
    .reset_index(name="cantidad")
)

# 3. SELECCIONAR CLUSTERS SIN DIVIDIRLOS
def seleccionar(grupos_disponibles, etiqueta, objetivo):
    candidatos = (
        grupos_disponibles[
            grupos_disponibles["Label"] == etiqueta
        ]
        .to_dict("records")
    )

    rng.shuffle(candidatos)

    seleccionados = []
    acumulado = 0

    for grupo in candidatos:
        cantidad = int(grupo["cantidad"])

        if acumulado + cantidad <= objetivo:
            seleccionados.append(grupo["cluster_id"])
            acumulado += cantidad

        if acumulado == objetivo:
            break

    if acumulado != objetivo:
        raise SystemExit(
            f"No se alcanzo la cuota para {etiqueta}: "
            f"{acumulado}/{objetivo}"
        )

    return seleccionados

# 4. RESERVAR PRUEBA FINAL
ids_prueba = []

for etiqueta, cantidad in OBJETIVO_PRUEBA.items():
    ids_prueba.extend(
        seleccionar(grupos, etiqueta, cantidad)
    )

# 5. SEPARAR VALIDACION DEL DESARROLLO
restantes = grupos[
    ~grupos["cluster_id"].isin(ids_prueba)
].copy()

ids_validacion = []

for etiqueta, cantidad in OBJETIVO_VALIDACION.items():
    ids_validacion.extend(
        seleccionar(restantes, etiqueta, cantidad)
    )

# 6. ASIGNAR PARTICIONES
manifiesto = df[
    ["row_id", "hash", "Label", "cluster_id"]
].copy()

manifiesto["particion"] = "entrenamiento"

manifiesto.loc[
    manifiesto["cluster_id"].isin(ids_validacion),
    "particion"
] = "validacion"

manifiesto.loc[
    manifiesto["cluster_id"].isin(ids_prueba),
    "particion"
] = "prueba_sellada"

# 7. VERIFICAR INTEGRIDAD DE LA DIVISION
tabla = pd.crosstab(
    manifiesto["particion"],
    manifiesto["Label"]
).reindex(
    index=["entrenamiento", "validacion", "prueba_sellada"],
    columns=[0, 1],
    fill_value=0
)

esperado = pd.DataFrame(
    {
        0: [211, 53, 400],
        1: [265, 66, 400]
    },
    index=[
        "entrenamiento",
        "validacion",
        "prueba_sellada"
    ]
)

if not tabla.equals(esperado):
    raise SystemExit(
        f"Distribucion inesperada:\n{tabla}"
    )

traslapes = (
    manifiesto.groupby("cluster_id")["particion"]
    .nunique()
    .gt(1)
    .sum()
)

if traslapes != 0:
    raise SystemExit("FUGA: cluster en varias particiones")

if manifiesto["row_id"].duplicated().any():
    raise SystemExit("Hay identificadores repetidos")

# 8. GUARDAR MANIFIESTO REPRODUCIBLE
salida = PROCESSED / "manifiesto_particiones.csv"
manifiesto.to_csv(salida, index=False)

with archivo.open("rb") as f:
    sha256 = hashlib.file_digest(
        f, "sha256"
    ).hexdigest()

reporte = [
    "PARTICION EXPERIMENTAL - SPAPHISH V5",
    "====================================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    f"Semilla: {SEMILLA}",
    f"SHA256 corpus: {sha256}",
    f"Total original: {len(df)}",
    "",
    "DISTRIBUCION (0=legitimo, 1=phishing):",
    tabla.to_string(),
    "",
    f"Clusters cruzados: {traslapes}",
    f"Registros asignados: {len(manifiesto)}",
    "Estado: PARTICIONES VERIFICADAS",
    "",
    "La prueba final permanece reservada.",
    "No utilizarla para entrenamiento o ajuste."
]

texto = "\n".join(reporte)
print(texto)

ruta_reporte = (
    EVIDENCIAS / "04_particiones_experimentales.txt"
)

ruta_reporte.write_text(texto, encoding="utf-8")

print("\nManifiesto:", salida)
print("Evidencia:", ruta_reporte)
