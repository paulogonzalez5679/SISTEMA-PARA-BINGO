"""
Script de prueba para el endpoint /api/obtenerTablasConsecutivas
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_obtener_tablas_consecutivas():
    """Prueba el endpoint de obtención de tablas consecutivas"""
    
    # Datos de prueba - CAMBIA ESTOS IDS CON VALORES REALES
    payload = {
        "usuario_id": "507f1f77bcf86cd799439012",  # REEMPLAZAR CON ID REAL
        "cantidad_tablas": 2
    }
    
    print("🔍 Probando endpoint: POST /api/obtenerTablasConsecutivas")
    print(f"📊 Datos enviados: {json.dumps(payload, indent=2)}")
    print("-" * 60)
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/obtenerTablasConsecutivas",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"✅ Status Code: {response.status_code}")
        print(f"📄 Respuesta:\n{json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"\n✨ Tablas consecutivas disponibles: {data.get('tablas_consecutivas')}")
                print(f"📈 Cantidad: {data.get('cantidad')}")
                print("\n💡 Usa estos códigos al crear el participante:")
                print(f"   {json.dumps({'tablas': data.get('tablas_consecutivas')})}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar al servidor. ¿Está corriendo app.py?")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    test_obtener_tablas_consecutivas()
