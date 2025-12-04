# ✅ CAMBIO REALIZADO: Endpoint Actualizado

## Lo que cambió

El endpoint anterior `/api/asignarTablasConsecutivas` **requería el ID del participante** (que aún no existía).

Ahora existe: `/api/obtenerTablasConsecutivas` que **solo obtiene** los códigos sin asignar.

## Nuevo Endpoint: `/api/obtenerTablasConsecutivas`

### ¿Cuándo usarlo?
✅ Cuando estás **creando un participante nuevo**  
✅ Para obtener los códigos que vas a asignarle  
✅ Sin modificar nada en la base de datos  

### Solicitud
```json
POST /api/obtenerTablasConsecutivas
{
  "usuario_id": "ObjectId del usuario",
  "cantidad_tablas": 2
}
```

### Respuesta
```json
{
  "success": true,
  "message": "Tablas disponibles obtenidas correctamente.",
  "tablas_consecutivas": ["CARD004", "CARD005"],
  "cantidad": 2
}
```

## Flujo de uso correcto

### Antes (forma incorrecta)
```
1. Crear participante → Obtener tablas → Error (participante no existe)
```

### Ahora (forma correcta)
```
1. Obtener tablas consecutivas
        ↓
2. Mostrar en el frontend: "Se asignarán: CARD004, CARD005"
        ↓
3. Usuario confirma
        ↓
4. Registrar participante CON esos códigos
        ↓
5. ¡Éxito! Participante creado con las tablas asignadas
```

## Código JavaScript correcto

```javascript
// PASO 1: Obtener tablas disponibles
const respuesta = await fetch('/api/obtenerTablasConsecutivas', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    usuario_id: usuarioLogueado,
    cantidad_tablas: 2
  })
});

const datos = await respuesta.json();

if (datos.success) {
  // PASO 2: Mostrar al usuario
  console.log('Tablas a asignar:', datos.tablas_consecutivas);
  // ["CARD004", "CARD005"]
  
  // PASO 3: Registrar participante con esas tablas
  const respRegistro = await fetch('/api/registrarParticipante', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nombre: "Juan",
      apellido: "Pérez",
      cedula: "1234567",
      tablas: datos.tablas_consecutivas,  // ← USAR ESTOS CÓDIGOS
      registrado_por: usuarioLogueado
    })
  });
}
```

## ¿Qué ventajas tiene?

✅ **Más lógico** - Obtén los códigos ANTES de crear el participante  
✅ **Sin errores** - No necesitas un participante que no existe  
✅ **Seguro** - No modifica la BD hasta que registres el participante  
✅ **Mejor UX** - Puedes mostrar "Se asignarán las tablas X, Y, Z" antes de confirmar  
✅ **Flexible** - Puedes llamarlo varias veces sin afectar nada  

## Archivos actualizados

- ✅ `app.py` - Endpoint `/api/obtenerTablasConsecutivas` añadido
- ✅ `ENDPOINT_TABLAS_CONSECUTIVAS.md` - Documentación actualizada
- ✅ `GUIA_TABLAS_CONSECUTIVAS.md` - Guía visual actualizada
- ✅ `test_asignar_tablas.py` - Script de prueba actualizado

## Próximos pasos

1. En tu frontend, reemplaza la lógica para:
   - Primero llamar a `/api/obtenerTablasConsecutivas`
   - Mostrar los códigos al usuario
   - Luego registrar con `/api/registrarParticipante`

2. Ejecuta el script de prueba:
   ```bash
   python test_asignar_tablas.py
   ```

3. ¡Listo! Tu sistema ahora asigna tablas de forma correcta y consecutiva.
