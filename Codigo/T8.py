
from pathlib import Path
from datetime import datetime
import hashlib
import json
import pandas as pd
from importlib.metadata import version

BASE = Path(__file__).resolve().parent
MODELOS = BASE / "modelos"
DATOS = BASE / "data" / "processed"
EVIDENCIAS = BASE / "evidencias"
CONFIG = BASE / "config"

CONFIG.mkdir(exist_ok=True)

def sha256_archivo(ruta):
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()

# Verificar archivos fundamentales
archivos = {
    "detector_clasico": MODELOS / "detector_clasico.joblib",
    "detector_semantico": MODELOS / "detector_semantico.joblib",
    "config_semantico": MODELOS / "config_semantico.json",
    "particiones": DATOS / "manifiesto_particiones.csv",
    "dependencias": BASE / "requirements_instalados.txt",
    "script_clasico": BASE / "T6.py",
    "script_semantico": BASE / "T7.py",
}

for nombre, ruta in archivos.items():
    if not ruta.is_file():
        raise SystemExit(f"Falta: {nombre} - {ruta}")

hashes = {
    nombre: sha256_archivo(ruta)
    for nombre, ruta in archivos.items()
}

manifest = pd.read_csv(archivos["particiones"])

distribucion = pd.crosstab(
    manifest["particion"],
    manifest["Label"]
)

cruces = (
    manifest.groupby("cluster_id")["particion"]
    .nunique()
    .gt(1)
    .sum()
)

if cruces != 0:
    raise SystemExit("ERROR: clusters cruzados.")

with archivos["config_semantico"].open(
    encoding="utf-8"
) as f:
    configuracion_semantica = json.load(f)

dependencias = {}
for paquete in [
    "pandas",
    "numpy",
    "scikit-learn",
    "scipy",
    "torch",
    "sentence-transformers"
]:
    dependencias[paquete] = version(paquete)

registro = {
    "fecha": datetime.now().astimezone().isoformat(),
    "semilla": 20261121,
    "estado": "Revision previa a prueba final",
    "registros": len(manifest),
    "clusters_cruzados": int(cruces),
    "distribucion": distribucion.to_dict(),
    "hashes_sha256": hashes,
    "dependencias": dependencias,
    "configuracion_semantica": configuracion_semantica,
    "limitaciones": [
        "Encoder limitado a 128 tokens",
        "337 de 476 textos de entrenamiento truncables",
        "75 de 119 textos de validacion truncables",
        "Neutralizacion inicial limitada a URL y emails"
    ],
    "prueba_final": "No ejecutada"
}

ruta_json = CONFIG / "revision_metodologica_T8.json"

ruta_json.write_text(
    json.dumps(registro, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

reporte = [
    "REVISION METODOLOGICA - SEMINARIO 2",
    "=================================",
    f"Fecha: {registro['fecha']}",
    f"Registros: {len(manifest)}",
    f"Clusters cruzados: {cruces}",
    "",
    "DISTRIBUCION:",
    distribucion.to_string(),
    "",
    "SHA256 DE ARCHIVOS:",
]

for nombre, hash_valor in hashes.items():
    reporte.append(f"{nombre}: {hash_valor}")

reporte.extend([
    "",
    "LIMITACIONES IDENTIFICADAS:",
    *registro["limitaciones"],
    "",
    "ESTADO: REVISION PREVIA A PRUEBA FINAL",
    "No se modificaron ni entrenaron modelos."
])

texto = "\n".join(map(str, reporte))
print(texto)

ruta_txt = EVIDENCIAS / "07_revision_metodologica.txt"
ruta_txt.write_text(texto, encoding="utf-8")

print("\nArchivos generados correctamente.")
