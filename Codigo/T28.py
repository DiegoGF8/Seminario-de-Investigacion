
from pathlib import Path
from datetime import datetime
import hashlib
import json

import pandas as pd

# ==========================================
# T28 - CONSOLIDACION DE RESULTADOS T27
# SEMINARIO DE INVESTIGACION 2
# ==========================================

BASE = Path(__file__).resolve().parent
EVIDENCIAS = BASE / "evidencias"

EXCEL = EVIDENCIAS / "27_revision_comparacion.xlsx"
ORIGEN = EVIDENCIAS / "27_comparacion_prompts.json"

SALIDA_CSV = EVIDENCIAS / "28_resumen_configuraciones.csv"
SALIDA_JSON = EVIDENCIAS / "28_seleccion_protocolo.json"
SALIDA_TXT = EVIDENCIAS / "28_consolidacion_resultados.txt"

# ==========================================
# 1. COMPROBAR ARCHIVOS
# ==========================================

for archivo in [EXCEL, ORIGEN]:
    if not archivo.is_file():
        raise SystemExit(
            f"ERROR: Archivo no encontrado: {archivo}"
        )

if any(p.exists() for p in [
    SALIDA_CSV, SALIDA_JSON, SALIDA_TXT
]):
    raise SystemExit(
        "Ya existen evidencias T28. "
        "No se sobrescribieron."
    )

df = pd.read_excel(
    EXCEL,
    dtype=str,
    keep_default_na=False
)

datos_t27 = json.loads(
    ORIGEN.read_text(encoding="utf-8")
)

columnas = [
    "id_control",
    "configuracion",
    "texto_original",
    "texto_generado",
    "conserva_significado",
    "reformulacion_real",
    "decision_manual",
    "observaciones"
]

if not set(columnas).issubset(df.columns):
    raise SystemExit(
        "ERROR: Faltan columnas obligatorias."
    )

if len(df) != 6:
    raise SystemExit(
        "ERROR: Deben existir seis evaluaciones."
    )

# ==========================================
# 2. VERIFICAR CORRESPONDENCIA CON T27
# ==========================================

resultados_originales = {}

for item in datos_t27["resultados"]:
    clave = (
        item["id"],
        item["configuracion"]
    )

    if clave in resultados_originales:
        raise SystemExit(
            "ERROR: Resultados duplicados en T27."
        )

    resultados_originales[clave] = item

if len(resultados_originales) != 6:
    raise SystemExit(
        "ERROR: T27 no contiene seis resultados."
    )

claves_revisadas = set()

for _, fila in df.iterrows():

    clave = (
        fila["id_control"].strip(),
        fila["configuracion"].strip()
    )

    if clave in claves_revisadas:
        raise SystemExit(
            f"ERROR: Evaluacion duplicada: {clave}"
        )

    claves_revisadas.add(clave)

    if clave not in resultados_originales:
        raise SystemExit(
            f"ERROR: Control no encontrado: {clave}"
        )

    original = resultados_originales[clave]

    if fila["texto_original"] != original["original"]:
        raise SystemExit(
            f"ERROR: Texto original alterado: {clave}"
        )

    if fila["texto_generado"] != original["generado"]:
        raise SystemExit(
            f"ERROR: Texto generado alterado: {clave}"
        )

    significado = (
        fila["conserva_significado"]
        .strip().upper()
    )

    reformulacion = (
        fila["reformulacion_real"]
        .strip().upper()
    )

    decision = (
        fila["decision_manual"]
        .strip().upper()
    )

    if significado not in {"SI", "NO"}:
        raise SystemExit(
            f"Error de significado: {clave}"
        )

    if reformulacion not in {"SI", "NO"}:
        raise SystemExit(
            f"Error de reformulacion: {clave}"
        )

    if decision not in {"APROBADO", "RECHAZADO"}:
        raise SystemExit(
            f"Decision pendiente o incorrecta: {clave}"
        )

    if decision == "APROBADO":
        if significado != "SI" or reformulacion != "SI":
            raise SystemExit(
                f"Aprobacion inconsistente: {clave}"
            )

        if original["alertas"]:
            raise SystemExit(
                f"Control aprobado con alertas: {clave}"
            )

    if not fila["observaciones"].strip():
        raise SystemExit(
            f"Falta justificacion: {clave}"
        )

if claves_revisadas != set(resultados_originales):
    raise SystemExit(
        "ERROR: Existen controles sin evaluar."
    )

# ==========================================
# 3. RESUMIR RESULTADOS
# ==========================================

df["decision_control"] = (
    df["decision_manual"].str.strip().str.upper()
)

resumen = (
    df.groupby("configuracion", sort=True)
    .agg(
        evaluados=("decision_control", "size"),
        aprobados=(
            "decision_control",
            lambda x: int((x == "APROBADO").sum())
        ),
        rechazados=(
            "decision_control",
            lambda x: int((x == "RECHAZADO").sum())
        )
    )
    .reset_index()
)

resumen["tasa_aprobacion"] = (
    resumen["aprobados"] / resumen["evaluados"]
)

esperados = {
    "A_ESTRICTA": (3, 2, 1),
    "B_CON_EJEMPLOS": (3, 3, 0)
}

if set(resumen["configuracion"]) != set(esperados):
    raise SystemExit(
        "ERROR: Configuraciones inesperadas."
    )

for _, fila in resumen.iterrows():

    obtenido = (
        int(fila["evaluados"]),
        int(fila["aprobados"]),
        int(fila["rechazados"])
    )

    if obtenido != esperados[fila["configuracion"]]:
        raise SystemExit(
            "Los resultados no coinciden "
            "con la revision documentada."
        )

# ==========================================
# 4. SELECCION PRELIMINAR
# ==========================================

SELECCION = "B_CON_EJEMPLOS"

def sha256_archivo(ruta):
    return hashlib.sha256(
        ruta.read_bytes()
    ).hexdigest()

configuraciones = datos_t27.get(
    "configuraciones", {}
)

if SELECCION not in configuraciones:
    raise SystemExit(
        "No se encontro el prompt seleccionado."
    )

registro = {
    "fecha": datetime.now().astimezone().isoformat(),
    "fase": "Consolidacion de controles inofensivos",
    "modelo": datos_t27["modelo"],
    "digest_modelo": datos_t27["digest"],
    "parametros": datos_t27["parametros"],
    "controles_evaluados": len(df),
    "configuraciones_comparadas": 2,
    "resultados": resumen.to_dict(orient="records"),
    "configuracion_seleccionada": SELECCION,
    "instrucciones_seleccionadas": configuraciones[
        SELECCION
    ],
    "tipo_seleccion": "PRELIMINAR",
    "justificacion": (
        "La configuracion B obtuvo tres aprobaciones "
        "de tres controles, frente a dos de tres en A. "
        "La muestra es demasiado pequena para "
        "demostrar superioridad generalizable."
    ),
    "sha256_excel_revision": sha256_archivo(EXCEL),
    "sha256_resultados_t27": sha256_archivo(ORIGEN),
    "variantes_dataset_generadas": 0,
    "prueba_final_utilizada": False,
    "protocolo_congelado": False,
    "pendiente": [
        "Evaluar mas controles independientes",
        "Resolver equivalencia de preprocesamiento V2/V3",
        "Definir protocolo definitivo antes de prueba final"
    ]
}

# ==========================================
# 5. GUARDAR EVIDENCIAS
# ==========================================

resumen.to_csv(
    SALIDA_CSV,
    index=False,
    encoding="utf-8-sig"
)

SALIDA_JSON.write_text(
    json.dumps(
        registro,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)

lineas = [
    "T28 - CONSOLIDACION DE RESULTADOS",
    "================================",
    f"Fecha: {registro['fecha']}",
    f"Modelo: {registro['modelo']}",
    "Controles evaluados: 6",
    "",
    "RESULTADOS:"
]

for _, fila in resumen.iterrows():
    lineas.append(
        f"{fila['configuracion']}: "
        f"{int(fila['aprobados'])}/"
        f"{int(fila['evaluados'])} aprobados "
        f"({fila['tasa_aprobacion']:.1%})"
    )

lineas.extend([
    "",
    "CONFIGURACION SELECCIONADA:",
    SELECCION,
    "",
    "Tipo de seleccion: PRELIMINAR",
    "Calidad generalizable: NO DEMOSTRADA",
    "Protocolo congelado: NO",
    "Variantes del dataset: 0",
    "Prueba final: NO UTILIZADA",
    "Clasificadores: SIN MODIFICACIONES",
    "",
    "PENDIENTE:",
    "Ampliar pruebas de calidad del generador.",
    "Resolver equivalencia V2/V3.",
    "Definir criterios de evaluacion final.",
    "",
    "T28 FINALIZADO."
])

reporte = "\n".join(lineas)

SALIDA_TXT.write_text(
    reporte,
    encoding="utf-8"
)

print(reporte)

print("\nARCHIVOS GENERADOS:")
print(SALIDA_CSV)
print(SALIDA_JSON)
print(SALIDA_TXT)
