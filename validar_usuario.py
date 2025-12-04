#!/usr/bin/env python3
"""
Script para validar y corregir los contadores de tablas de un usuario.
Uso: python validar_usuario.py <usuario_id>
"""

import sys
from pymongo import MongoClient
from bson import ObjectId

# Importar utilidades de corrección
try:
    from fix_duplicate_tablas import dedupe_all_participants_for_user, recalc_usedTables_for_user, merge_duplicate_participants_for_user
except Exception:
    dedupe_all_participants_for_user = None
    recalc_usedTables_for_user = None
    merge_duplicate_participants_for_user = None

try:
    from corregir_stateAsigned import corregir_stateAsigned
except Exception:
    corregir_stateAsigned = None

# Conexión a MongoDB
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["bingo_db"]
mongo_collection_users = mongo_db["Users"]
mongo_collection_participantes = mongo_db["Participantes"]
mongo_collection_tables = mongo_db["tablas"]

def validar_usuario(usuario_id_str, auto_corregir=False):
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
    
    # Obtener rango de tablas del usuario
    fromSerial = usuario.get('fromSerial')
    toSerial = usuario.get('toSerial')
    
    print(f"  - Rango de Tablas: {fromSerial} a {toSerial}")
    print(f"  - Tablas Disponibles: {usuario.get('totalTables', 0) - usuario.get('usedTables', 0)}")
    
    # Obtener tablas disponibles (no asignadas) dentro del rango del usuario
    if fromSerial and toSerial:
        # Determinar el rango (puede ser ascendente o descendente)
        if fromSerial <= toSerial:
            query = {
                "serial": {"$gte": fromSerial, "$lte": toSerial},
                "stateAsigned": False
            }
        else:
            query = {
                "serial": {"$lte": fromSerial, "$gte": toSerial},
                "stateAsigned": False
            }
        
        tablas_disponibles = list(mongo_collection_tables.find(
            query,
            {"serial": 1}
        ).sort("serial", 1))
        
        print(f"\n📦 Tablas Disponibles ({len(tablas_disponibles)}):")
        if tablas_disponibles:
            # Mostrar las primeras 20 y el resto en formato compacto
            for i, tabla in enumerate(tablas_disponibles[:20]):
                print(f"    {tabla['serial']}", end="")
                if (i + 1) % 5 == 0:
                    print()  # Nueva línea cada 5 tablas
                else:
                    print("  ", end="")
            
            if len(tablas_disponibles) > 200:
                print(f"\n    ... y {len(tablas_disponibles) - 20} más")
            else:
                print()  # Nueva línea al final
    
    print()

    # ---- ORQUESTADOR: dedupe, sincronizar stateAsigned y recalcular usedTables ----
    if dedupe_all_participants_for_user or corregir_stateAsigned:
        do_orquestar = False
        if auto_corregir:
            do_orquestar = True
        else:
            try:
                resp = input('\n¿Deseas ejecutar el ORQUESTADOR (dedupe participantes, sync stateAsigned, recalc usedTables) para este usuario? (S/N): ').strip().upper()
            except:
                resp = 'N'
            do_orquestar = (resp == 'S')

        if do_orquestar:
            print('\n🔄 Iniciando orquestación de correcciones...')
            # Dedupe participantes registrados por el usuario (limpia listas internas de tablas)
            if dedupe_all_participants_for_user:
                try:
                    res_dedupe = dedupe_all_participants_for_user(usuario_id)
                    print(f"\n✅ Dedupe completado. usedTables recalculado a: {res_dedupe.get('usedTables_updated')}")
                except Exception as e:
                    print(f"⚠️ Error en dedupe_all_participants_for_user: {e}")
            else:
                print('⚠️ Módulo fix_duplicate_tablas no disponible. Omite dedupe.')

            # Merge (consolidar documentos duplicados por cédula)
            if merge_duplicate_participants_for_user:
                try:
                    if auto_corregir:
                        # Si se solicitó auto_corregir, aplicar los cambios directamente
                        print('\n🔧 Ejecutando MERGE de participantes duplicados (aplicando cambios)...')
                        res_merge = merge_duplicate_participants_for_user(usuario_id, dry_run=False)
                        print('\n✅ Merge aplicado. Resumen:')
                        print(res_merge)
                    else:
                        # En modo interactivo, mostrar dry-run y no aplicar automáticamente
                        print('\n🔍 Ejecutando MERGE en modo dry-run (no aplica cambios).')
                        res_merge = merge_duplicate_participants_for_user(usuario_id, dry_run=True)
                        print('\n🔎 Resultado (dry-run):')
                        print(res_merge)
                        print('\nPara aplicar los cambios, vuelve a ejecutar con --auto-corregir o ajusta el flujo.')
                except Exception as e:
                    print(f"⚠️ Error en merge_duplicate_participants_for_user: {e}")
            else:
                print('⚠️ merge_duplicate_participants_for_user no disponible. Omite consolidación de documentos.')

            # Corregir stateAsigned (este script preguntará internamente si debe aplicar cambios)
            if corregir_stateAsigned:
                try:
                    # pasar id de usuario como referencia opcional
                    corregir_stateAsigned(str(usuario_id))
                except Exception as e:
                    print(f"⚠️ Error al ejecutar corregir_stateAsigned: {e}")
            else:
                print('⚠️ Módulo corregir_stateAsigned no disponible. Omite sincronización de stateAsigned.')

            # Recalcular usedTables por seguridad
            if recalc_usedTables_for_user:
                try:
                    total_after = recalc_usedTables_for_user(usuario_id)
                    print(f"\n🔁 Recalculo final de usedTables: {total_after}")
                except Exception as e:
                    print(f"⚠️ Error en recalc_usedTables_for_user: {e}")
            else:
                print('⚠️ Función recalc_usedTables_for_user no disponible. Omite recálculo final.')

            # Refrescar el usuario desde BD para continuar con la validación
            usuario = mongo_collection_users.find_one({"_id": usuario_id})
            if not usuario:
                print("⚠️ Usuario no encontrado tras orquestación. Abortando.")
                return
            print('🔍 Orquestación finalizada. Continuando con validación...')
        else:
            print('\n⏭️ Orquestador omitido por usuario.')
    
    # Obtener participantes del usuario
    participantes = list(mongo_collection_participantes.find({"registrado_por": usuario_id}))
    print(f"\n👥 Participantes Registrados: {len(participantes)}")

    # Contar tablas reales y recolectar seriales asignados
    total_tablas_reales = 0
    detalles_participantes = []
    seriales_asignados = set()

    for p in participantes:
        tablas = p.get("tablas", [])
        total_tablas_reales += len(tablas)
        # Obtener seriales de las tablas
        seriales = []
        if tablas:
            # Buscar los seriales en la colección tablas
            tablas_objs = list(mongo_collection_tables.find({"_id": {"$in": [ObjectId(t) if isinstance(t, str) and len(t) == 24 else t for t in tablas]}}))
            seriales = [t.get("serial", str(t.get("_id"))) for t in tablas_objs]
            seriales_asignados.update(seriales)
        detalles_participantes.append({
            "nombre": p.get("nombre", "N/A"),
            "cedula": p.get("cedula", "N/A"),
            "tablas": len(tablas),
            "seriales": seriales,
            "id": str(p["_id"])
        })

    # Mostrar detalles
    print(f"\n📋 Detalles de Participantes:")
    for i, p in enumerate(detalles_participantes, 1):
        seriales_str = ', '.join(p['seriales']) if p['seriales'] else 'Sin tablas'
        print(f"  {i}. {p['nombre']} (Cédula: {p['cedula']}) - {p['tablas']} tabla(s): {seriales_str}")

    # Buscar tarjetas huérfanas en el rango del usuario (solo para reportar, NO para cambiar el contador)
    huérfanas = []
    if fromSerial and toSerial:
        # Buscar todas las tablas del rango
        if fromSerial <= toSerial:
            query = {"serial": {"$gte": fromSerial, "$lte": toSerial}}
        else:
            query = {"serial": {"$lte": fromSerial, "$gte": toSerial}}
        todas_tablas_rango = list(mongo_collection_tables.find(query, {"serial": 1, "stateAsigned": 1}))
        for t in todas_tablas_rango:
            serial = t.get("serial")
            if t.get("stateAsigned") is False and serial not in seriales_asignados:
                huérfanas.append(serial)
    if huérfanas:
        print(f"\n⚠️  ALERTA: Tablas HUÉRFANAS en el rango del usuario (no asignadas a participantes):")
        print('   ' + ', '.join(huérfanas))
        print(f"   NOTA: Estas tablas no se cuentan en el total. Investiga por qué están sin asignar.")
    else:
        if fromSerial and toSerial:
            print(f"\n✅ No hay tablas huérfanas en el rango del usuario.")
    
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
        
        # Leer entrada con timeout o valor por defecto
        try:
            if auto_corregir:
                respuesta = 'S'
            else:
                respuesta = input(f"\n¿Deseas CORREGIR los contadores? (S/N): ").strip().upper()
        except:
            respuesta = 'N'
        
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
        print("Uso: python validar_usuario.py <usuario_id> [--auto-corregir]")
        print("\nEjemplos:")
        print("  python validar_usuario.py 690cccb58fd0fbff298e9dba")
        print("  python validar_usuario.py 690cccb58fd0fbff298e9dba --auto-corregir")
        sys.exit(1)
    
    usuario_id = sys.argv[1]
    auto_corregir = "--auto-corregir" in sys.argv
    
    validar_usuario(usuario_id, auto_corregir=auto_corregir)
