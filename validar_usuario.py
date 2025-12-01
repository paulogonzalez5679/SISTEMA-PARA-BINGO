#!/usr/bin/env python3
"""
Script para validar y corregir los contadores de tablas de un usuario.
Uso: python validar_usuario.py <usuario_id>
"""

import sys
from pymongo import MongoClient
from bson import ObjectId

# Conexión a MongoDB
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["bingo_db"]
mongo_collection_users = mongo_db["Users"]
mongo_collection_participantes = mongo_db["Participantes"]

def validar_usuario(usuario_id_str):
    """Valida y corrige los contadores de un usuario."""
    
    try:
        usuario_id = ObjectId(usuario_id_str)
    except Exception as e:
        print(f"❌ Error: ID de usuario inválido: {e}")
        return
    
    # Obtener usuario
    usuario = mongo_collection_users.find_one({"_id": usuario_id})
    if not usuario:
        print(f"❌ Usuario no encontrado: {usuario_id_str}")
        return
    
    print(f"\n{'='*70}")
    print(f"📊 VALIDACIÓN DE TABLAS PARA USUARIO: {usuario_id_str}")
    print(f"{'='*70}")
    
    # Información básica del usuario
    print(f"\n📋 Información del Usuario:")
    print(f"  - Usuario: {usuario.get('usuario', 'N/A')}")
    print(f"  - Nombres: {usuario.get('nombres_completos', 'N/A')}")
    print(f"  - Total Tablas: {usuario.get('totalTables', 0)}")
    print(f"  - Tablas Usadas (BD): {usuario.get('usedTables', 0)}")
    print(f"  - Tablas Disponibles: {usuario.get('totalTables', 0) - usuario.get('usedTables', 0)}")
    
    # Obtener participantes del usuario
    participantes = list(mongo_collection_participantes.find({"registrado_por": usuario_id}))
    
    print(f"\n👥 Participantes Registrados: {len(participantes)}")
    
    # Contar tablas reales
    total_tablas_reales = 0
    detalles_participantes = []
    
    for p in participantes:
        tablas = p.get("tablas", [])
        total_tablas_reales += len(tablas)
        detalles_participantes.append({
            "nombre": p.get("nombre", "N/A"),
            "cedula": p.get("cedula", "N/A"),
            "tablas": len(tablas),
            "id": str(p["_id"])
        })
    
    # Mostrar detalles
    print(f"\n📋 Detalles de Participantes:")
    for i, p in enumerate(detalles_participantes, 1):
        print(f"  {i}. {p['nombre']} (Cédula: {p['cedula']}) - {p['tablas']} tabla(s)")
    
    # Análisis
    print(f"\n{'='*70}")
    print(f"📈 ANÁLISIS:")
    print(f"{'='*70}")
    
    used_tables_bd = usuario.get("usedTables", 0)
    diferencia = used_tables_bd - total_tablas_reales
    
    print(f"\n✓ Total de Tablas Reales Asignadas: {total_tablas_reales}")
    print(f"✓ Total en BD (usedTables): {used_tables_bd}")
    print(f"✓ Diferencia: {diferencia}")
    
    if diferencia == 0:
        print(f"\n✅ ¡Los contadores están CORRECTOS!")
    else:
        print(f"\n⚠️  ¡HAY UNA DISCREPANCIA DE {abs(diferencia)} TABLA(S)!")
        
        if diferencia > 0:
            print(f"   → En la BD se reportan {diferencia} tablas MÁS de las que realmente hay")
            print(f"   → Se necesita RESTAR {diferencia} a usedTables")
        else:
            print(f"   → En la BD se reportan {abs(diferencia)} tablas MENOS de las que realmente hay")
            print(f"   → Se necesita SUMAR {abs(diferencia)} a usedTables")
    
    # Opción de corregir
    print(f"\n{'='*70}")
    
    if diferencia != 0:
        print(f"\n🔧 Opción de CORRECCIÓN:")
        print(f"   Cambiar usedTables de {used_tables_bd} a {total_tablas_reales}")
        
        respuesta = input(f"\n¿Deseas CORREGIR los contadores? (S/N): ").strip().upper()
        
        if respuesta == 'S':
            # Realizar corrección
            mongo_collection_users.update_one(
                {"_id": usuario_id},
                {"$set": {"usedTables": total_tablas_reales}}
            )
            print(f"\n✅ ¡CORRECCIÓN COMPLETADA!")
            print(f"   usedTables actualizado a: {total_tablas_reales}")
            print(f"   Tablas disponibles ahora: {usuario.get('totalTables', 0) - total_tablas_reales}")
        else:
            print(f"\n⏸️  Corrección cancelada.")
    else:
        print(f"\nNo se requiere corrección.")
    
    print(f"\n{'='*70}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validar_usuario.py <usuario_id>")
        print("\nEjemplo:")
        print("  python validar_usuario.py 690cccb58fd0fbff298e9dba")
        sys.exit(1)
    
    usuario_id = sys.argv[1]
    validar_usuario(usuario_id)
