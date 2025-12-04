# Endpoint: Obtener Tablas Consecutivas Disponibles

## Descripción
Endpoint que **solo obtiene** los códigos de tablas consecutivas disponibles sin asignarlas. 
Es perfecto para usar al crear un participante nuevo, ya que solo necesitas saber qué tablas asignarle.

Respeta:
1. El rango de tablas asignado al usuario
2. Las tablas ya asignadas (las salta automáticamente)
3. Solo tablas disponibles (no asignadas a ningún participante)

## Ruta
```
POST /api/obtenerTablasConsecutivas
```

## Parámetros (JSON)

```json
{
  "usuario_id": "ObjectId del usuario",
  "cantidad_tablas": número de tablas consecutivas que necesitas (ej: 2, 3, 5)
}
```

## Ejemplo de solicitud

```bash
curl -X POST http://localhost:5000/api/obtenerTablasConsecutivas \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "507f1f77bcf86cd799439012",
    "cantidad_tablas": 2
  }'
```

## Respuesta exitosa (200)

```json
{
  "success": true,
  "message": "Tablas disponibles obtenidas correctamente.",
  "tablas_consecutivas": ["CARD004", "CARD005"],
  "cantidad": 2
}
```

## Ejemplos de error

### No hay suficientes tablas disponibles (400)
```json
{
  "success": false,
  "message": "No hay suficientes tablas disponibles. Se encontraron 1 de 3 solicitadas."
}
```

### Usuario no tiene rango asignado (400)
```json
{
  "success": false,
  "message": "El usuario no tiene un rango de tablas asignado."
}
```

## Flujo de uso

### Paso 1: Obtener tablas consecutivas
```javascript
const response = await fetch('/api/obtenerTablasConsecutivas', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    usuario_id: usuarioLogueado,
    cantidad_tablas: 2
  })
});

const data = await response.json();
// data.tablas_consecutivas = ["CARD004", "CARD005"]
```

### Paso 2: Crear participante con esas tablas
```javascript
const response = await fetch('/api/registrarParticipante', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    nombre: "Juan",
    apellido: "Pérez",
    cedula: "1234567",
    tablas: ["CARD004", "CARD005"],  // ← Usar los que obtuviste en el paso anterior
    registrado_por: usuarioLogueado
  })
});
```

## Ventajas

✅ **No requiere ID del participante** - Ya que el participante aún no existe  
✅ **Solo lectura** - No modifica nada en la BD  
✅ **Permite planificación** - Obtén los códigos antes de registrar  
✅ **Automático y consecutivo** - Los códigos se devuelven en orden  
✅ **Respeta permisos** - Solo devuelve tablas del rango del usuario  

## Lógica de búsqueda

Supongamos este escenario:
- **Usuario A** tiene asignado: CARD001 - CARD010
- **CARD001** está asignado a otro participante
- **CARD002** está asignado a otro participante  
- **CARD003** está asignado a otro participante
- **CARD004, CARD005** están libres

### Solicitud:
```json
{
  "usuario_id": "...",
  "cantidad_tablas": 2
}
```

### Respuesta:
```json
{
  "success": true,
  "tablas_consecutivas": ["CARD004", "CARD005"],
  "cantidad": 2
}
```

El endpoint salta automáticamente las tablas asignadas y encuentra las siguientes 2 consecutivas disponibles.

## Notas importantes

- Solo obtiene tablas dentro del rango `fromSerial` - `toSerial` del usuario
- No modifica la BD, es seguro llamarlo múltiples veces
- Los códigos se devuelven en orden consecutivo
- La respuesta es un array de strings (seriales) listo para usar en `/api/registrarParticipante`
