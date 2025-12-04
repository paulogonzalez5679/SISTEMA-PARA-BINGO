#!/usr/bin/env python3
"""
Script para obtener y mostrar participantes de múltiples usuarios.
Acepta nombres completos (nombres_completos) de usuarios de la colección Users
y muestra los participantes asignados a cada usuario con sus detalles.

Uso:
  python reporte_participantes_por_usuarios.py "BRAVO TACURI DANIELA MARIA" "OTRO USUARIO"
  python reporte_participantes_por_usuarios.py --file usuarios.txt
"""

import sys
import json
from pymongo import MongoClient
from bson import ObjectId

# Conexión a MongoDB
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["bingo_db"]
mongo_collection_users = mongo_db["Users"]
mongo_collection_participantes = mongo_db["Participantes"]
mongo_collection_tables = mongo_db["tablas"]


def obtener_participantes_por_usuario(nombres_usuarios, exportar_txt=False):
    """
    Obtiene y muestra los participantes para una lista de nombres de usuarios.
    
    Args:
        nombres_usuarios (list): Lista de nombres completos (nombres_completos) de usuarios
        exportar_txt (bool): Si True, exporta resultado a "Rangos de usuarios.txt"
    
    Returns:
        dict: Diccionario con resultado de la operación
    """
    
    resultado_general = {
        "usuarios_procesados": 0,
        "usuarios_encontrados": 0,
        "usuarios_no_encontrados": [],
        "total_participantes": 0,
        "detalles_por_usuario": [],
        "lineas_txt": []  # Para almacenar el contenido del txt
    }
    
    print(f"\n{'='*80}")
    print(f"📊 REPORTE DE PARTICIPANTES POR USUARIOS")
    print(f"{'='*80}")
    print(f"\n🔍 Buscando {len(nombres_usuarios)} usuario(s)...\n")
    
    # Agregar encabezado al txt
    resultado_general["lineas_txt"].append("="*80)
    resultado_general["lineas_txt"].append("REPORTE DE PARTICIPANTES POR USUARIOS")
    resultado_general["lineas_txt"].append("="*80)
    resultado_general["lineas_txt"].append("")
    
    for nombre_usuario in nombres_usuarios:
        resultado_general["usuarios_procesados"] += 1
        nombre_usuario = nombre_usuario.strip()
        
        # Buscar usuario por nombres_completos
        usuario = mongo_collection_users.find_one({"nombres_completos": nombre_usuario})
        
        if not usuario:
            print(f"❌ Usuario NO encontrado: '{nombre_usuario}'")
            resultado_general["usuarios_no_encontrados"].append(nombre_usuario)
            continue
        
        resultado_general["usuarios_encontrados"] += 1
        usuario_id = usuario.get("_id")
        
        # Información del usuario
        print(f"\n{'─'*80}")
        print(f"👤 Usuario: {usuario.get('usuario', 'N/A')}")
        print(f"   Nombres: {usuario.get('nombres_completos', 'N/A')}")
        print(f"   ID: {usuario_id}")
        print(f"   Total Tablas: {usuario.get('totalTables', 0)}")
        print(f"   Tablas Usadas: {usuario.get('usedTables', 0)}")
        print(f"{'─'*80}")
        
        # Agregar al txt
        resultado_general["lineas_txt"].append("─" * 80)
        resultado_general["lineas_txt"].append(f"Usuario: {usuario.get('usuario', 'N/A')}")
        resultado_general["lineas_txt"].append(f"Nombres: {usuario.get('nombres_completos', 'N/A')}")
        resultado_general["lineas_txt"].append(f"ID: {usuario_id}")
        resultado_general["lineas_txt"].append(f"Total Tablas: {usuario.get('totalTables', 0)}")
        resultado_general["lineas_txt"].append(f"Tablas Usadas: {usuario.get('usedTables', 0)}")
        resultado_general["lineas_txt"].append("─" * 80)
        
        # Obtener participantes del usuario
        participantes = list(mongo_collection_participantes.find({"registrado_por": usuario_id}))
        
        print(f"\n👥 Participantes Registrados: {len(participantes)}")
        resultado_general["lineas_txt"].append(f"\nParticipantes Registrados: {len(participantes)}")
        
        if len(participantes) == 0:
            print(f"   (Sin participantes)")
            resultado_general["lineas_txt"].append("   (Sin participantes)")
            resultado_general["detalles_por_usuario"].append({
                "nombre_usuario": nombre_usuario,
                "usuario_id": str(usuario_id),
                "total_participantes": 0,
                "participantes": []
            })
            continue
        
        # Procesar participantes
        detalles_participantes = []
        total_tablas_reales = 0
        
        for p in participantes:
            tablas = p.get("tablas", [])
            total_tablas_reales += len(tablas)
            
            # Obtener seriales de las tablas
            seriales = []
            if tablas:
                try:
                    # Convertir a ObjectId si es string
                    tablas_ids = [
                        ObjectId(t) if isinstance(t, str) and len(t) == 24 else t
                        for t in tablas
                    ]
                    tablas_objs = list(mongo_collection_tables.find(
                        {"_id": {"$in": tablas_ids}},
                        {"serial": 1}
                    ))
                    seriales = [t.get("serial", str(t.get("_id"))) for t in tablas_objs]
                except Exception as e:
                    print(f"   ⚠️  Error procesando tablas del participante {p.get('cedula')}: {e}")
            
            detalles_participantes.append({
                "nombre": p.get("nombre", "N/A"),
                "cedula": p.get("cedula", "N/A"),
                "cantidad_tablas": len(tablas),
                "seriales": seriales,
                "id": str(p.get("_id", ""))
            })
        
        # Mostrar detalles de participantes
        print(f"\n📋 Detalles de Participantes:")
        resultado_general["lineas_txt"].append("\nDetalles de Participantes:")
        for i, p in enumerate(detalles_participantes, 1):
            print(f"  {i}. {p['nombre']} (Cédula: {p['cedula']}) - {p['cantidad_tablas']} tabla(s):")
            resultado_general["lineas_txt"].append(f"  {i}. {p['nombre']} (Cédula: {p['cedula']}) - {p['cantidad_tablas']} tabla(s):")
            if p['seriales']:
                for serial in p['seriales']:
                    print(f"     {serial}")
                    resultado_general["lineas_txt"].append(f"     {serial}")
            else:
                print(f"     Sin tablas")
                resultado_general["lineas_txt"].append(f"     Sin tablas")
        
        # Resumen del usuario
        print(f"\n📈 Resumen:")
        print(f"   Total de participantes: {len(participantes)}")
        print(f"   Total de tablas asignadas: {total_tablas_reales}")
        
        resultado_general["lineas_txt"].append(f"\nResumen:")
        resultado_general["lineas_txt"].append(f"   Total de participantes: {len(participantes)}")
        resultado_general["lineas_txt"].append(f"   Total de tablas asignadas: {total_tablas_reales}")
        resultado_general["lineas_txt"].append("")
        
        # Guardar detalles
        resultado_general["detalles_por_usuario"].append({
            "nombre_usuario": nombre_usuario,
            "usuario_id": str(usuario_id),
            "usuario": usuario.get("usuario", "N/A"),
            "total_participantes": len(participantes),
            "total_tablas": total_tablas_reales,
            "participantes": detalles_participantes
        })
        
        resultado_general["total_participantes"] += len(participantes)
    
    # Resumen general
    print(f"\n{'='*80}")
    print(f"📊 RESUMEN GENERAL")
    print(f"{'='*80}")
    print(f"✓ Usuarios procesados: {resultado_general['usuarios_procesados']}")
    print(f"✓ Usuarios encontrados: {resultado_general['usuarios_encontrados']}")
    print(f"✓ Usuarios no encontrados: {len(resultado_general['usuarios_no_encontrados'])}")
    print(f"✓ Total de participantes: {resultado_general['total_participantes']}")
    
    # Agregar resumen general al txt
    resultado_general["lineas_txt"].append("="*80)
    resultado_general["lineas_txt"].append("RESUMEN GENERAL")
    resultado_general["lineas_txt"].append("="*80)
    resultado_general["lineas_txt"].append(f"Usuarios procesados: {resultado_general['usuarios_procesados']}")
    resultado_general["lineas_txt"].append(f"Usuarios encontrados: {resultado_general['usuarios_encontrados']}")
    resultado_general["lineas_txt"].append(f"Usuarios no encontrados: {len(resultado_general['usuarios_no_encontrados'])}")
    resultado_general["lineas_txt"].append(f"Total de participantes: {resultado_general['total_participantes']}")
    
    if resultado_general["usuarios_no_encontrados"]:
        print(f"\n⚠️  Usuarios NO encontrados:")
        resultado_general["lineas_txt"].append("\nUsuarios NO encontrados:")
        for nombre in resultado_general["usuarios_no_encontrados"]:
            print(f"   - {nombre}")
            resultado_general["lineas_txt"].append(f"   - {nombre}")
    
    print(f"\n{'='*80}\n")
    
    return resultado_general


def exportar_a_json(resultado, archivo_salida="reporte_participantes.json"):
    """Exporta el resultado a un archivo JSON."""
    try:
        with open(archivo_salida, 'w', encoding='utf-8') as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)
        print(f"✅ Reporte exportado a: {archivo_salida}")
    except Exception as e:
        print(f"❌ Error al exportar JSON: {e}")


def exportar_a_txt(resultado, archivo_salida="Rangos de usuarios.txt"):
    """Exporta el resultado a un archivo TXT."""
    try:
        with open(archivo_salida, 'w', encoding='utf-8') as f:
            for linea in resultado.get("lineas_txt", []):
                f.write(linea + "\n")
        print(f"✅ Reporte exportado a: {archivo_salida}")
        return True
    except Exception as e:
        print(f"❌ Error al exportar TXT: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python reporte_participantes_por_usuarios.py 'NOMBRE USUARIO 1' 'NOMBRE USUARIO 2' ...")
        print("  python reporte_participantes_por_usuarios.py --file usuarios.txt")
        print("\nEjemplos:")
        print("  python reporte_participantes_por_usuarios.py 'BRAVO TACURI DANIELA MARIA'")
        print("  python reporte_participantes_por_usuarios.py 'USUARIO 1' 'USUARIO 2' 'USUARIO 3'")
        print("  python reporte_participantes_por_usuarios.py --file usuarios.txt --json salida.json")
        sys.exit(1)
    
    nombres = []
    archivo_entrada = None
    archivo_salida = None
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        if arg == "--file":
            if i + 1 < len(sys.argv):
                archivo_entrada = sys.argv[i + 1]
                i += 2
            else:
                print("❌ Error: --file requiere un nombre de archivo")
                sys.exit(1)
        elif arg == "--json":
            if i + 1 < len(sys.argv):
                archivo_salida = sys.argv[i + 1]
                i += 2
            else:
                print("❌ Error: --json requiere un nombre de archivo")
                sys.exit(1)
        else:
            nombres.append(arg)
            i += 1
    
    # Si se proporcionó un archivo de entrada
    if archivo_entrada:
        try:
            with open(archivo_entrada, 'r', encoding='utf-8') as f:
                nombres = [linea.strip() for linea in f if linea.strip()]
        except Exception as e:
            print(f"❌ Error al leer archivo: {e}")
            sys.exit(1)
    
    if not nombres:
        print("❌ Error: No se proporcionaron nombres de usuarios")
        sys.exit(1)
    
    # Ejecutar reporte
    resultado = obtener_participantes_por_usuario(nombres)
    
    # Si se leyó desde archivo, exportar automáticamente a txt
    if archivo_entrada:
        exportar_a_txt(resultado, "Rangos de usuarios.txt")
    
    # Exportar a JSON si se solicitó
    if archivo_salida:
        exportar_a_json(resultado, archivo_salida)
