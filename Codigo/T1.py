
import sys
from pathlib import Path

print("PROYECTO: SEMINARIO DE INVESTIGACION 2")
print("-----------------------------------")
print("Estado: entorno de investigacion")
print("Version de Python:", sys.version.split()[0])
print("Carpeta del proyecto:", Path.cwd())

if sys.version_info[:2] == (3, 12):
    print("RESULTADO: Python 3.12 configurado correctamente")
else:
    print("ADVERTENCIA: verificar version de Python")
