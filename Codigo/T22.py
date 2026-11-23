
from pathlib import Path
from datetime import datetime
import hashlib
import json
import pandas as pd

# T22 - PREPARACION DEL PROTOCOLO DE GENERACION
# SEMINARIO DE INVESTIGACION 2

BASE = Path(__file__).resolve().parent
PILOTO = BASE / "data" / "piloto_privado"
EVIDENCIAS = BASE / "evidencias"

EXCEL = PILOTO / "Revision_Neutralizacion_Piloto_V3.xlsx"
MANIFIESTO = PILOTO / "manifiesto_piloto_aprobado.csv"
INVENTARIO = EVIDENCIAS / "21_insumos_piloto.json"

SALIDA_EXCEL = PILOTO / "22_bitacora_generacion.xlsx"
SALIDA_JSON = EVIDENCIAS / "22_protocolo_generacion.json"
SALIDA_TXT = EVIDENCIAS / "22_preparacion_generacion.txt"

for ruta in [EXCEL, MANIFIESTO, INVENTARIO]:
    if not ruta.is_file():
        raise SystemExit(f"Archivo faltante: {ruta}")

if SALIDA_EXCEL.exists() or SALIDA_JSON.exists():
    raise SystemExit(
        "Ya existe una salida de T22. "
        "No se sobrescribieron archivos."
    )

# 1. Cargar registros
df = pd.read_excel(
    EXCEL, dtype=str, keep_default_na=False
)

manifest = pd.read_csv(
    MANIFIESTO,
    dtype=str,
    encoding="utf-8-sig",
    keep_default_na=False
)

inventario = json.loads(
    INVENTARIO.read_text(encoding="utf-8")
)

# 2. Seleccionar aprobados
aprobados = df[
    df["revision_v3"].str.strip().str.upper().eq("APROBADO")
    & df["apto_para_IA"].str.strip().str.upper().eq("SI")
].copy()

if len(df) != 30 or len(aprobados) != 26:
    raise SystemExit("Distribucion inesperada.")

# 3. Verificar manifiesto
verificacion = aprobados.merge(
    manifest[[
        "id_par", "row_id", "sha256_texto_v3"
    ]],
    on=["id_par", "row_id"],
    how="outer",
    indicator=True,
    validate="one_to_one"
)

if len(verificacion) != 26:
    raise SystemExit("Cantidad incorrecta.")

if not verificacion["_merge"].eq("both").all():
    raise SystemExit("Inconsistencia de identificadores.")

def sha_texto(texto):
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()

for _, fila in verificacion.iterrows():
    if sha_texto(
        fila["texto_v3_borrador"]
    ) != fila["sha256_texto_v3"]:
        raise SystemExit(
            f"Hash diferente: {fila['id_par']}"
        )

hashes_inventario = {
    item["id_par"]: item["sha256"]
    for item in inventario["mensajes"]
}

for _, fila in verificacion.iterrows():
    if hashes_inventario.get(
        fila["id_par"]
    ) != fila["sha256_texto_v3"]:
        raise SystemExit(
            f"Diferencia con T21: {fila['id_par']}"
        )

# 4. Crear bitacora sin textos privados
bitacora = verificacion[[
    "id_par", "row_id", "sha256_texto_v3"
]].copy()

bitacora = bitacora.rename(columns={
    "sha256_texto_v3": "sha256_referencia"
})

bitacora["estado_generacion"] = "NO_INICIADA"
bitacora["generador"] = ""
bitacora["version_generador"] = ""
bitacora["configuracion_id"] = ""
bitacora["sha256_variante"] = ""
bitacora["revision_variante"] = "PENDIENTE"
bitacora["apta_para_evaluacion"] = "NO"
bitacora["observaciones"] = ""

with pd.ExcelWriter(
    SALIDA_EXCEL, engine="openpyxl"
) as writer:

    bitacora.to_excel(
        writer,
        sheet_name="Bitacora",
        index=False
    )

    hoja = writer.sheets["Bitacora"]
    hoja.freeze_panes = "D2"
    hoja.auto_filter.ref = hoja.dimensions

    for columna in hoja.columns:
        letra = columna[0].column_letter
        hoja.column_dimensions[letra].width = (
            72 if letra in ("C", "G") else 24
        )

# 5. Registrar protocolo preliminar
protocolo = {
    "fecha": datetime.now().astimezone().isoformat(),
    "fase": "Piloto exploratorio",
    "estado": "PREPARACION",
    "mensajes_referencia": 26,
    "origen": "entrenamiento",
    "neutralizacion_referencia": "V3",
    "modelos_clasificacion": [
        "detector_clasico_v2.joblib",
        "detector_semantico_v2.joblib"
    ],
    "generador": "PENDIENTE",
    "version_generador": "PENDIENTE",
    "parametros": "PENDIENTE",
    "variantes_generadas": 0,
    "comparacion": "Pares original y variante",
    "control": [
        "Mismos criterios de preprocesamiento",
        "Una referencia por pareja",
        "Registrar el hash de cada variante",
        "Conservar archivos originales",
        "No utilizar enlaces funcionales",
        "No incluir credenciales reales",
        "No optimizar variantes para evadir detectores",
        "Revisar cada variante antes de evaluarla"
    ],
    "prueba_final_utilizada": False,
    "protocolo_congelado": False
}

SALIDA_JSON.write_text(
    json.dumps(
        protocolo,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)

# 6. Evidencia
reporte = [
    "T22 - PREPARACION DE GENERACION",
    "================================",
    f"Fecha: {protocolo['fecha']}",
    f"Mensajes verificados: {len(verificacion)}",
    "Hashes T20/T21: COINCIDENTES",
    "Bitacora: GENERADA",
    "Generador IA: PENDIENTE",
    "Variantes IA: 0",
    "Clasificadores: SIN MODIFICACIONES",
    "Prueba final: NO UTILIZADA",
    "Protocolo congelado: NO",
    "",
    "T22 FINALIZADO."
]

resultado = "\n".join(reporte)
print(resultado)

SALIDA_TXT.write_text(
    resultado,
    encoding="utf-8"
)

print("\nArchivos generados:")
print(SALIDA_EXCEL)
print(SALIDA_JSON)
print(SALIDA_TXT)
