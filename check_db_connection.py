#!/usr/bin/env python3
"""Script sencillo para validar conexión a MongoDB usada por el proyecto.

Uso:
  env/bin/python check_db_connection.py

El script hace ping al servidor, lista bases y muestra algunas colecciones.
"""
import sys
import traceback
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

MONGO_URI = "mongodb://localhost:27017/"
TIMEOUT_MS = 5000


def main():
    print(f"Probando conexión a: {MONGO_URI} (timeout {TIMEOUT_MS} ms)")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=TIMEOUT_MS)
        # ping
        client.admin.command("ping")
        print("✅ Ping exitoso al servidor MongoDB.")

        # listar bases de datos (puede fallar si permisos restringidos)
        try:
            dbs = client.list_database_names()
            print(f"Bases de datos visibles ({len(dbs)}): {dbs}")
        except Exception as e:
            print(f"⚠️  No se pudo listar bases de datos: {e}")

        # inspeccionar la base `bingo_db` y mostrar colecciones (si existen)
        try:
            db = client['bingo_db']
            cols = db.list_collection_names()
            print(f"Colecciones en 'bingo_db' ({len(cols)}): {cols}")
            # Mostrar conteo aproximado de algunas colecciones si existen
            sample_cols = ['tablas', 'tablas_ganadoras', 'Estudiantes', 'Participantes', 'Users']
            for c in sample_cols:
                if c in cols:
                    try:
                        n = db[c].count_documents({})
                    except Exception:
                        n = 'N/A'
                    print(f"  - {c}: {n}")
        except Exception as e:
            print(f"⚠️  Error accediendo a 'bingo_db': {e}")

        print("Hecho.")
        return 0

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print("❌ No se pudo conectar a MongoDB:", str(e))
        return 2
    except Exception as e:
        print("❌ Error inesperado:")
        traceback.print_exc()
        return 3


if __name__ == '__main__':
    sys.exit(main())
