
from pathlib import Path
from datetime import datetime
import hashlib

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

BASE = Path(__file__).resolve().parent
PILOTO = BASE / "data" / "piloto_privado"
EVIDENCIAS = BASE / "evidencias"

# Archivos que ya preparaste
archivo_textos = PILOTO / "piloto_30_desarrollo.csv"
archivo_revision = PILOTO / "Revision_Final_Piloto_30_SI2.xlsx"

for archivo in [archivo_textos, archivo_revision]:
    if not archivo.is_file():
        raise SystemExit(f"No se encontro: {archivo}")

# 1. Leer los textos del piloto
textos = pd.read_csv(
    archivo_textos,
    encoding="utf-8-sig"
)

# 2. Leer las decisiones del Excel
revision = pd.read_excel(
    archivo_revision,
    engine="openpyxl"
)

columnas = [
    "id_par", "row_id", "estado_revision",
    "apto_para_generacion", "observaciones"
]

if not set(columnas).issubset(revision.columns):
    raise SystemExit(
        "Faltan columnas en el Excel de revision."
    )

# 3. Verificar que los registros coincidan
datos = textos[
    ["id_par", "row_id", "texto_neutralizado"]
].merge(
    revision[columnas],
    on=["id_par", "row_id"],
    how="outer",
    validate="one_to_one",
    indicator=True
)

if len(datos) != 30 or not datos["_merge"].eq("both").all():
    raise SystemExit(
        "Los 30 registros no coinciden entre archivos."
    )

if not datos["apto_para_generacion"].eq("NO").all():
    raise SystemExit(
        "Existen aprobaciones que requieren verificacion."
    )

# 4. Crear una COPIA editable
salida = pd.DataFrame({
    "id_par": datos["id_par"],
    "row_id": datos["row_id"],
    "estado_preliminar": datos["estado_revision"],
    "observacion_preliminar": datos["observaciones"],
    "texto_v2_referencia": datos["texto_neutralizado"],
    "texto_v3_borrador": datos["texto_neutralizado"],
    "revision_v3": "PENDIENTE",
    "apto_para_IA": "NO",
    "cambios_realizados": ""
})

# Ninguna neutralizacion adicional se aplica
# automaticamente. Los textos V3 son borradores.

destino = PILOTO / "Revision_Neutralizacion_Piloto_V3.xlsx"

if destino.exists():
    raise SystemExit(
        "El archivo de salida ya existe. "
        "No se sobrescribio."
    )

# 5. Guardar con formato legible
with pd.ExcelWriter(destino, engine="openpyxl") as writer:
    salida.to_excel(
        writer, sheet_name="Revision", index=False
    )

    ws = writer.sheets["Revision"]
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = ws.dimensions

    anchos = {
        "A": 16, "B": 12, "C": 20,
        "D": 65, "E": 85, "F": 85,
        "G": 18, "H": 18, "I": 55
    }

    for columna, ancho in anchos.items():
        ws.column_dimensions[columna].width = ancho

    for celda in ws[1]:
        celda.fill = PatternFill(
            "solid", fgColor="176B55"
        )
        celda.font = Font(
            bold=True, color="FFFFFF"
        )

    for fila in ws.iter_rows(min_row=2):
        for celda in fila:
            celda.alignment = Alignment(
                vertical="top",
                wrap_text=True
            )
        ws.row_dimensions[fila[0].row].height = 65

# 6. Documentar el procedimiento
def sha256(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()

conteos = datos["estado_revision"].value_counts()

reporte = [
    "T17 - PREPARACION DE REVISION V3",
    "================================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    f"Mensajes preparados: {len(datos)}",
    f"REVISAR: {conteos.get('REVISAR', 0)}",
    f"PENDIENTE: {conteos.get('PENDIENTE', 0)}",
    "Aprobados para IA: 0",
    "",
    f"SHA256 textos originales: {sha256(archivo_textos)}",
    f"SHA256 revision: {sha256(archivo_revision)}",
    "",
    "Los textos originales permanecen intactos.",
    "Se creo una copia editable del piloto.",
    "No se aplicaron sustituciones adicionales.",
    "No se generaron variantes IA.",
    "No se modificaron los modelos.",
    "Prueba final: NO UTILIZADA."
]

texto = "\n".join(reporte)
print(texto)

(EVIDENCIAS / "17_preparacion_revision_v3.txt").write_text(
    texto, encoding="utf-8"
)

print("\nArchivo generado:", destino)
