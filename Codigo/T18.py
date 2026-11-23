
from pathlib import Path
from datetime import datetime
import re
import pandas as pd

BASE = Path(__file__).resolve().parent
PILOTO = BASE / "data" / "piloto_privado"
EVIDENCIAS = BASE / "evidencias"

archivo_excel = (
    PILOTO / "Revision_Neutralizacion_Piloto_V3.xlsx"
)
archivo_original = PILOTO / "piloto_30_desarrollo.csv"

if not archivo_excel.exists():
    raise SystemExit("No se encontro el Excel V3.")

if not archivo_original.exists():
    raise SystemExit("No se encontro el piloto original.")

# Cargar archivos
df = pd.read_excel(archivo_excel)
original = pd.read_csv(
    archivo_original, encoding="utf-8-sig"
)

requeridas = [
    "id_par", "row_id",
    "texto_v2_referencia",
    "texto_v3_borrador",
    "revision_v3",
    "apto_para_IA",
    "cambios_realizados"
]

if not set(requeridas).issubset(df.columns):
    raise SystemExit("Faltan columnas en el Excel.")

if len(df) != 30 or len(original) != 30:
    raise SystemExit("Cantidad de registros incorrecta.")

if df["id_par"].duplicated().any():
    raise SystemExit("Existen IDs duplicados.")

# Verificar correspondencia por identificadores
comparacion = df.merge(
    original[
        ["id_par", "row_id", "texto_neutralizado"]
    ],
    on=["id_par", "row_id"],
    how="outer",
    validate="one_to_one",
    indicator=True
)

if not comparacion["_merge"].eq("both").all():
    raise SystemExit("Los registros no coinciden.")

# Comparar textos ignorando espacios repetidos
def normalizar(texto):
    return re.sub(r"\s+", " ", str(texto)).strip()

referencias_correctas = sum(
    normalizar(a) == normalizar(b)
    for a, b in zip(
        comparacion["texto_v2_referencia"],
        comparacion["texto_neutralizado"]
    )
)

modificados = sum(
    normalizar(a) != normalizar(b)
    for a, b in zip(
        df["texto_v2_referencia"],
        df["texto_v3_borrador"]
    )
)

# Buscar marcadores unidos accidentalmente
# a fragmentos de palabras
MARCADORES = (
    r"PERSONA|ORGANIZACION|DIRECCION|"
    r"IDENTIFICADOR|SERVICIO|PRODUCTO|"
    r"RED_DE_PAGO"
)

patron_error = re.compile(
    rf"\w\[(?:{MARCADORES})\]"
    rf"|\[(?:{MARCADORES})\]\w"
)

problemas = []

for _, fila in df.iterrows():
    texto = str(fila["texto_v3_borrador"])

    if not texto.strip() or texto == "nan":
        problemas.append(
            f"{fila['id_par']}: texto vacio"
        )

    if patron_error.search(texto):
        problemas.append(
            f"{fila['id_par']}: revisar marcador "
            "unido a una palabra"
        )

# Verificar estados
aprobados = int(
    df["apto_para_IA"]
    .astype(str).str.upper().eq("SI").sum()
)

sin_observaciones = int(
    df["cambios_realizados"].isna().sum()
)

reporte = [
    "T18 - VERIFICACION PRELIMINAR V3",
    "================================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    f"Total registros: {len(df)}",
    f"Referencias V2 correctas: {referencias_correctas}",
    f"Textos V3 modificados: {modificados}",
    f"Textos sin cambios: {len(df)-modificados}",
    f"Registros marcados aptos: {aprobados}",
    f"Observaciones vacias: {sin_observaciones}",
    f"Problemas detectados: {len(problemas)}",
    "",
    "DETALLE DE PROBLEMAS:",
    *(problemas or ["Ninguno detectado"]),
    "",
    "La validacion automatica no garantiza",
    "anonimizacion completa.",
    "No se modificaron los modelos.",
    "Prueba final: NO UTILIZADA."
]

resultado = "\n".join(reporte)
print(resultado)

salida = (
    EVIDENCIAS / "18_verificacion_preliminar_v3.txt"
)
salida.write_text(resultado, encoding="utf-8")

print("\nReporte guardado:", salida)
