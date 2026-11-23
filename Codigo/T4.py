
from pathlib import Path
from collections import Counter
import pandas as pd
import re

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
EVIDENCIAS = BASE / "evidencias"

PROCESSED.mkdir(exist_ok=True)
EVIDENCIAS.mkdir(exist_ok=True)

archivo = next(RAW.glob("*.csv"))

df = pd.read_csv(
    archivo,
    sep=",",
    encoding="utf-8-sig",
    low_memory=False
)

# Construir texto sin modificar los datos originales
textos = (
    df["subject"].fillna("").astype(str)
    + " "
    + df["body"].fillna("").astype(str)
)

def obtener_shingles(texto):
    palabras = re.findall(r"\w+", texto.casefold())

    if len(palabras) < 5:
        return {tuple(palabras)} if palabras else set()

    return {
        tuple(palabras[i:i+5])
        for i in range(len(palabras) - 4)
    }

shingles = [obtener_shingles(t) for t in textos]

# Estructura para agrupar mensajes relacionados
padres = list(range(len(df)))

def raiz(x):
    while padres[x] != x:
        padres[x] = padres[padres[x]]
        x = padres[x]
    return x

def unir(a, b):
    ra, rb = raiz(a), raiz(b)
    if ra != rb:
        padres[rb] = ra

# Comparacion exacta de Jaccard entre pares candidatos
pares_similares = 0

for i in range(len(shingles)):
    a = shingles[i]

    for j in range(i + 1, len(shingles)):
        b = shingles[j]

        if not a or not b:
            continue

        # Filtro matematico: evita comparaciones
        # que no pueden alcanzar Jaccard >= 0.90
        if min(len(a), len(b)) / max(len(a), len(b)) < 0.90:
            continue

        interseccion = len(a & b)
        union = len(a) + len(b) - interseccion
        similitud = interseccion / union

        if similitud >= 0.90:
            unir(i, j)
            pares_similares += 1

    if (i + 1) % 200 == 0:
        print(f"Revisados: {i + 1}/{len(df)} registros")

# Crear identificadores estables de cluster
mapa = {}
ids = []

for i in range(len(df)):
    r = raiz(i)
    if r not in mapa:
        mapa[r] = f"CL{len(mapa)+1:04d}"
    ids.append(mapa[r])

conteos = Counter(ids)
grupos_multiples = {
    k: v for k, v in conteos.items() if v > 1
}

resultado = pd.DataFrame({
    "row_id": range(len(df)),
    "cluster_id": ids,
    "Label": df["Label"]
})

conflictos = (
    resultado.groupby("cluster_id")["Label"]
    .nunique()
    .gt(1)
    .sum()
)

reporte = [
    "AUDITORIA DE CASI DUPLICADOS - SPAPHISH",
    "======================================",
    f"Registros analizados: {len(df)}",
    "Metodo: shingles de 5 palabras",
    "Similitud: Jaccard >= 0.90",
    f"Pares similares identificados: {pares_similares}",
    f"Clusters totales: {len(conteos)}",
    f"Clusters con mas de un registro: {len(grupos_multiples)}",
    f"Registros en clusters multiples: {sum(grupos_multiples.values())}",
    f"Clusters con etiquetas diferentes: {conflictos}",
    "",
    "DISTRIBUCION DE TAMANOS DE CLUSTERS:",
    str(Counter(conteos.values()))
]

ruta_csv = PROCESSED / "mapa_clusters.csv"
resultado.to_csv(ruta_csv, index=False)

ruta_reporte = EVIDENCIAS / "03_auditoria_clusters.txt"
ruta_reporte.write_text(
    "\n".join(reporte),
    encoding="utf-8"
)

print("\n".join(reporte))
print("\nMapa guardado en:", ruta_csv)
print("Evidencia guardada en:", ruta_reporte)
