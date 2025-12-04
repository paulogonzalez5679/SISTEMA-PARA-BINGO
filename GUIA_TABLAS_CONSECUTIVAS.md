# 📋 RESUMEN: Endpoint de Obtención de Tablas Consecutivas

## ¿Qué hace?

Obtiene (sin asignar) códigos de tablas consecutivas disponibles. Perfecto para usar al **crear un participante nuevo**.

## 🎯 Ejemplo práctico

```
USUARIO A: Rango CARD001 - CARD010
├─ CARD001, CARD002, CARD003 → Ya asignadas ❌
├─ CARD004, CARD005, CARD006, CARD007, CARD008, CARD009, CARD010 → Disponibles ✅

Solicito: 2 tablas consecutivas
Respuesta: ["CARD004", "CARD005"]
```

## 📤 Petición

```http
POST /api/obtenerTablasConsecutivas
Content-Type: application/json

{
  "usuario_id": "ObjectId",
  "cantidad_tablas": 2
}
```

## 📥 Respuesta exitosa

```json
{
  "success": true,
  "message": "Tablas disponibles obtenidas correctamente.",
  "tablas_consecutivas": ["CARD004", "CARD005"],
  "cantidad": 2
}
```

## ✨ Ventajas

✅ No requiere ID del participante (aún no existe)  
✅ No modifica nada en la BD (solo lectura)  
✅ Permite planificar antes de crear participante  
✅ Devuelve códigos en orden consecutivo  
✅ Salta automáticamente tablas asignadas  
✅ Respeta el rango del usuario  

## 🔄 Flujo de uso

```mermaid
1. Obtener tablas consecutivas
   ↓
2. Mostrar códigos en el frontend
   ↓
3. Usuario crea participante con esos códigos
   ↓
4. El participante se registra exitosamente
```

## 💻 Código JavaScript

```javascript
// Paso 1: Obtener tablas disponibles
const respuestaTablas = await fetch('/api/obtenerTablasConsecutivas', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    usuario_id: usuarioId,
    cantidad_tablas: 2
  })
});

const datosTablas = await respuestaTablas.json();
console.log(datosTablas.tablas_consecutivas); // ["CARD004", "CARD005"]

// Paso 2: El usuario ve los códigos en el formulario
// Paso 3: Al crear el participante, envía esos códigos
const respuestaParticipante = await fetch('/api/registrarParticipante', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    nombre: "Juan",
    apellido: "Pérez",
    cedula: "1234567",
    tablas: datosTablas.tablas_consecutivas,  // ← Usa los que obtuviste
    registrado_por: usuarioId
  })
});
```

## 📊 Diferencia con otros endpoints

| Endpoint | Propósito |
|----------|-----------|
| `/api/obtenerTablasConsecutivas` | ⭐ **Solo obtiene códigos** (no asigna) |
| `/api/registrarParticipante` | Registra participante CON tablas |
| `/api/participante/.../tablas` | Agrega tablas a participante EXISTENTE |

## 🔍 Validaciones

- Usuario debe existir ✓
- Usuario debe tener rango asignado ✓
- Cantidad debe ser > 0 ✓
- Debe haber suficientes tablas disponibles ✓

## 📝 Nota importante

Este endpoint **NO modifica la BD**. Solo devuelve los códigos.
Los códigos se "reservan" cuando registras el participante en `/api/registrarParticipante`.
