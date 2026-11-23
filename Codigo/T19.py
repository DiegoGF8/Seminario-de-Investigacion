
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib
import re
import pandas as pd

# ==================================================
# T19 - AUDITORIA FINAL DEL PILOTO V3
# SEMINARIO DE INVESTIGACION 2
# ==================================================

BASE = Path(__file__).resolve().parent

PILOTO = BASE / "data" / "piloto_privado"
EVIDENCIAS = BASE / "evidencias"

EXCEL = PILOTO / "Revision_Neutralizacion_Piloto_V3.xlsx"
ORIGINAL = PILOTO / "piloto_30_desarrollo.csv"

EVIDENCIAS.mkdir(parents=True, exist_ok=True)

# ==================================================
# 1. VERIFICACION DE ARCHIVOS
# ==================================================

for ruta in [EXCEL, ORIGINAL]:
    if not ruta.is_file():
        raise SystemExit(
            f"ERROR: Archivo no encontrado: {ruta}"
        )

df = pd.read_excel(
    EXCEL,
    dtype=str,
    keep_default_na=False
)

original = pd.read_csv(
    ORIGINAL,
    encoding="utf-8-sig",
    dtype=str,
    keep_default_na=False
)

columnas = [
    "id_par",
    "row_id",
    "texto_v2_referencia",
    "texto_v3_borrador",
    "revision_v3",
    "apto_para_IA",
    "cambios_realizados"
]

if not set(columnas).issubset(df.columns):
    raise SystemExit(
        "ERROR: Faltan columnas obligatorias."
    )

if len(df) != 30 or len(original) != 30:
    raise SystemExit(
        "ERROR: Deben existir exactamente 30 registros."
    )

if df["id_par"].duplicated().any():
    raise SystemExit(
        "ERROR: Identificadores duplicados."
    )

if df["row_id"].duplicated().any():
    raise SystemExit(
        "ERROR: row_id duplicados."
    )

# ==================================================
# 2. VERIFICACION DE CORRESPONDENCIA
# ==================================================

comparacion = df.merge(
    original[
        ["id_par", "row_id", "texto_neutralizado"]
    ],
    on=["id_par", "row_id"],
    how="outer",
    indicator=True,
    validate="one_to_one"
)

if len(comparacion) != 30:
    raise SystemExit(
        "ERROR: La correspondencia esta incompleta."
    )

if not comparacion["_merge"].eq("both").all():
    raise SystemExit(
        "ERROR: Existen registros no coincidentes."
    )


def normalizar(texto):
    return re.sub(
        r"\s+", " ", str(texto)
    ).strip()


referencias_ok = all(
    normalizar(a) == normalizar(b)
    for a, b in zip(
        comparacion["texto_v2_referencia"],
        comparacion["texto_neutralizado"]
    )
)

if not referencias_ok:
    raise SystemExit(
        "ERROR: Se modificaron las referencias V2."
    )

# ==================================================
# 3. ESTADOS VALIDOS DEL EXPERIMENTO
# ==================================================

ESTADOS_VALIDOS = {
    "APROBADO",
    "EXCLUIR_PILOTO",
    "REVISAR_ETIQUETA",
    "REVISAR_ORIGEN",
    "REVISAR",
    "PENDIENTE",
    "CORREGIDO_PENDIENTE_VALIDACION",
    "SIN_CAMBIOS_PENDIENTE_VALIDACION"
}

# ==================================================
# 4. PATRONES DE REVISION
# ==================================================

patrones = {
    "URL real": re.compile(
        r"https?://|www\.", re.I
    ),
    "Correo electronico": re.compile(
        r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        re.I
    ),
    "Telefono potencial": re.compile(
        r"\+\d[\d\s().-]{7,}\d"
    )
}

# ==================================================
# 5. AUDITORIA DE CADA MENSAJE
# ==================================================

incidencias = []
modificados = 0

for _, fila in df.iterrows():

    ident = fila["id_par"].strip()
    texto = fila["texto_v3_borrador"]

    estado = (
        fila["revision_v3"]
        .strip()
        .upper()
    )

    apto = (
        fila["apto_para_IA"]
        .strip()
        .upper()
    )

    errores = []

    # Detectar modificaciones V2 vs V3
    if normalizar(texto) != normalizar(
        fila["texto_v2_referencia"]
    ):
        modificados += 1

    # Texto vacio
    if not texto.strip():
        errores.append(
            "Texto V3 vacio"
        )

    # Estado desconocido
    if estado not in ESTADOS_VALIDOS:
        errores.append(
            "Estado de revision desconocido"
        )

    # Valor de aptitud incorrecto
    if apto not in {"SI", "NO"}:
        errores.append(
            "Valor de aptitud desconocido"
        )

    # Aprobacion y aptitud deben coincidir
    if estado == "APROBADO" and apto != "SI":
        errores.append(
            "Mensaje aprobado sin aptitud SI"
        )

    if estado != "APROBADO" and apto == "SI":
        errores.append(
            "Mensaje no aprobado marcado como apto"
        )

    # Exclusiones
    if estado == "EXCLUIR_PILOTO":
        if apto != "NO":
            errores.append(
                "Mensaje excluido marcado como apto"
            )

    # Revisar patrones residuales
    for nombre, patron in patrones.items():
        if patron.search(texto):
            errores.append(
                f"Revisar {nombre}"
            )

    # Documentacion obligatoria
    if not fila["cambios_realizados"].strip():
        errores.append(
            "Falta documentar cambios"
        )

    # ==================================================
    # VERIFICACIONES ESPECIFICAS
    # ==================================================

    if ident == "PILOTO_015":

        if "re[ORGANIZACION]do" in texto:
            errores.append(
                "Sustitucion incorrecta en revisado"
            )

        if "revisadodo" in texto.lower():
            errores.append(
                "Error de redaccion: revisadodo"
            )

        if "sutarjeta" in texto.lower():
            errores.append(
                "Error de redaccion: sutarjeta"
            )

        if re.search(
            r"tarjeta\s+\[ORGANIZACION\]",
            texto,
            re.I
        ):
            errores.append(
                "Revisar marcador de tarjeta"
            )

    if ident == "PILOTO_020":

        if "[ORGANIZACION] T&T" in texto:
            errores.append(
                "Fragmento comercial residual T&T"
            )

    if ident == "PILOTO_023":

        if re.search(
            r"Tel[eé]fono:\s*\+123",
            texto,
            re.I
        ):
            errores.append(
                "Prefijo telefonico residual"
            )

    # ==================================================
    # EXCLUSIONES METODOLOGICAS
    # ==================================================

    if ident == "PILOTO_022":

        if estado not in (
            "REVISAR_ETIQUETA",
            "EXCLUIR_PILOTO"
        ):
            errores.append(
                "Revisar posible ambiguedad de etiqueta"
            )

    if ident == "PILOTO_030":

        if estado not in (
            "REVISAR_ORIGEN",
            "EXCLUIR_PILOTO"
        ):
            errores.append(
                "Documentar texto fuente incompleto"
            )

    # Registrar incidencias
    if errores:
        incidencias.append({
            "id_par": ident,
            "row_id": fila["row_id"],
            "estado": estado,
            "incidencias": "; ".join(errores)
        })

# ==================================================
# 6. RESUMEN DE RESULTADOS
# ==================================================

estados = Counter(
    df["revision_v3"]
    .str.upper()
    .str.strip()
)

aptos = int(
    df["apto_para_IA"]
    .str.upper()
    .str.strip()
    .eq("SI")
    .sum()
)

excluidos = estados.get(
    "EXCLUIR_PILOTO", 0
)

pendientes = (
    len(df) - aptos - excluidos
)


def sha256(ruta):
    return hashlib.sha256(
        ruta.read_bytes()
    ).hexdigest()


# ==================================================
# 7. GENERAR REPORTE
# ==================================================

reporte = [
    "T19 - AUDITORIA FINAL DEL PILOTO V3",
    "===================================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    "",
    f"Total mensajes: {len(df)}",
    f"Referencias V2 correctas: {referencias_ok}",
    f"Textos V3 modificados: {modificados}",
    f"Textos sin cambios: {len(df) - modificados}",
    "",
    f"Mensajes aprobados: {aptos}",
    f"Mensajes excluidos: {excluidos}",
    f"Mensajes pendientes: {pendientes}",
    f"Registros con alertas: {len(incidencias)}",
    "",
    "ESTADOS DE REVISION:"
]

for nombre, total in sorted(estados.items()):
    reporte.append(
        f"{nombre}: {total}"
    )

reporte.extend([
    "",
    "SHA256 DE ARCHIVOS:",
    f"Excel V3: {sha256(EXCEL)}",
    f"Piloto V2: {sha256(ORIGINAL)}",
    "",
    "CONTROL METODOLOGICO:",
    "No se modificaron los datos originales.",
    "No se modificaron los clasificadores.",
    "No se utilizaron los datos de prueba final.",
    "Las exclusiones corresponden al piloto exploratorio.",
    "Las etiquetas originales se conservaron.",
    "Las comprobaciones no certifican anonimato."
])

if len(incidencias) == 0:
    reporte.extend([
        "",
        "ESTADO DE AUDITORIA:",
        "SIN ALERTAS AUTOMATICAS.",
        "Revision humana y protocolo experimental",
        "deben verificarse por separado."
    ])

resultado = "\n".join(reporte)

print(resultado)

ruta_reporte = (
    EVIDENCIAS / "19_auditoria_piloto_v3.txt"
)

ruta_reporte.write_text(
    resultado,
    encoding="utf-8"
)

# ==================================================
# 8. EXPORTAR INCIDENCIAS
# ==================================================

ruta_alertas = (
    EVIDENCIAS / "19_incidencias_piloto.csv"
)

if incidencias:

    tabla_alertas = pd.DataFrame(
        incidencias
    )

    tabla_alertas.to_csv(
        ruta_alertas,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nALERTAS DETECTADAS:")

    for item in incidencias:
        print(
            item["id_par"],
            "-",
            item["incidencias"]
        )

    print(
        "\nArchivo de incidencias:",
        ruta_alertas
    )

else:
    # Eliminar reportes antiguos para evitar
    # confundirlos con una ejecucion actual.
    if ruta_alertas.exists():
        ruta_alertas.unlink()

    print(
        "\nAUDITORIA SIN ALERTAS AUTOMATICAS."
    )

print(
    "\nReporte generado:",
    ruta_reporte
)

print(
    "\nT19 FINALIZADO."
)
