
from pathlib import Path
import pandas as pd
import re

BASE = Path(__file__).resolve().parent
PILOTO = BASE / "data" / "piloto_privado"
EVIDENCIAS = BASE / "evidencias"

archivo = PILOTO / "piloto_30_desarrollo.csv"

df = pd.read_csv(archivo, encoding="utf-8-sig")

if len(df) != 30:
    raise SystemExit("El piloto debe contener 30 mensajes.")

if df["id_par"].duplicated().any():
    raise SystemExit("Existen identificadores repetidos.")

patrones = {
    "url": r"https?://|www\.",
    "email": r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
    "dominio": (
        r"\b(?:[a-z0-9-]+\.)+"
        r"(?:com|org|net|edu|gov|gt|es|info)\b"
    ),
    "numero_largo": r"\b\d{8,}\b"
}

resultados = []

for _, fila in df.iterrows():
    texto = str(fila["texto_neutralizado"])

    coincidencias = [
        nombre for nombre, patron in patrones.items()
        if re.search(patron, texto, flags=re.I)
    ]

    resultados.append({
        "id_par": fila["id_par"],
        "row_id": fila["row_id"],
        "caracteres": len(texto),
        "patrones_residuales": "; ".join(coincidencias),
        "revision_manual": "PENDIENTE",
        "apto_para_generacion": "NO",
        "observaciones": ""
    })

revision = pd.DataFrame(resultados)

ruta = PILOTO / "revision_piloto_30.csv"

revision.to_csv(
    ruta,
    index=False,
    encoding="utf-8-sig"
)

alertas = revision[
    revision["patrones_residuales"].ne("")
]

reporte = (
    "T16 - REVISION DEL PILOTO\n"
    "========================\n"
    f"Mensajes revisados automaticamente: {len(df)}\n"
    f"Mensajes con patrones residuales: {len(alertas)}\n"
    "Revision manual: PENDIENTE\n"
    "Variantes IA generadas: 0\n"
    "Prueba final: NO UTILIZADA\n"
)

print(reporte)
print("Lista de revision:", ruta)

(EVIDENCIAS / "16_revision_piloto.txt").write_text(
    reporte,
    encoding="utf-8"
)
