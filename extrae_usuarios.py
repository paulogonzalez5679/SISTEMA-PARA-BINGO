#!/usr/bin/env python3
"""
Script para extraer nombres de usuarios del JSON y generar comando de ejecución
"""

import json

# Leer el JSON
with open(r"C:\Users\USUARIO\Downloads\bingo_db.Users.json", "r", encoding="utf-8") as f:
    usuarios = json.load(f)

# Extraer nombres completos (excluyendo admin y secretaria)
nombres = []
for usuario in usuarios:
    # Excluir usuarios del sistema
    if usuario.get("tipo_usuario") != 0:  # tipo_usuario 0 = admin/secretaria
        nombre = usuario.get("nombres_completos", "").strip()
        if nombre:
            nombres.append(nombre)

print(f"\n✅ Se encontraron {len(nombres)} usuarios\n")
print("=" * 80)
print("COMANDO PARA EJECUTAR EL REPORTE:")
print("=" * 80)

# Construir comando
cmd_args = ' '.join([f'"{nombre}"' for nombre in nombres])
print(f"\npython reporte_participantes_por_usuarios.py {cmd_args}\n")

print("=" * 80)
print("USUARIOS A PROCESAR:")
print("=" * 80)
for i, nombre in enumerate(nombres, 1):
    print(f"{i}. {nombre}")

print(f"\n✅ Total: {len(nombres)} usuarios")
print("\nPuedes copiar el comando de arriba y ejecutarlo en la terminal.")
