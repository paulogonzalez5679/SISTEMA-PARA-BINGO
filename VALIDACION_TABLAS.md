# Validación y Corrección de Tablas de Usuarios

## Problema Identificado

El usuario `690cccb58fd0fbff298e9dba` tenía una discrepancia en los contadores:
- **Tablas asignadas según la BD**: 63
- **Tablas realmente asignadas**: 78 (sumando las tablas de todos sus participantes)
- **Diferencia**: -15 tablas (la BD reportaba 15 MENOS)

Esta discrepancia ocurre cuando:
1. Se eliminan participantes pero no se actualiza correctamente el contador `usedTables`
2. Hay errores en la lógica de actualización de contadores en operaciones batch
3. Se modifican datos directamente en la BD sin actualizar los contadores

## Solución Implementada

### 1. Función de Validación (en `app.py`)

Se agregó la función `validar_y_corregir_tablas_usuario()` que:
- Cuenta los participantes registrados por un usuario
- Suma todas las tablas asignadas a esos participantes
- Compara con el valor en la BD (`usedTables`)
- Opcionalmente corrige la discrepancia

### 2. Endpoint de Validación (en `app.py`)

```
GET/POST /api/validar-tablas/<usuario_id>
```

Ejemplo de uso:
```bash
# GET - Solo validar sin corregir
curl http://localhost:5000/api/validar-tablas/690cccb58fd0fbff298e9dba

# POST - Validar y corregir si hay discrepancias
curl -X POST http://localhost:5000/api/validar-tablas/690cccb58fd0fbff298e9dba
```

Respuesta esperada:
```json
{
  "success": true,
  "usuario_id": "690cccb58fd0fbff298e9dba",
  "total_participantes": 26,
  "tablas_reales_asignadas": 78,
  "used_tables_bd_anterior": 63,
  "used_tables_bd_nuevo": 78,
  "diferencia": -15,
  "corregido": true,
  "totalTables": 80,
  "disponibles_ahora": 2
}
```

### 3. Script de Validación Interactivo (en `validar_usuario.py`)

Para validar manualmente desde la línea de comandos:

```bash
# Activar entorno virtual
.\env\Scripts\Activate.ps1

# Ejecutar validación
python validar_usuario.py 690cccb58fd0fbff298e9dba
```

El script proporciona:
- Información detallada del usuario
- Lista de todos los participantes y sus tablas
- Análisis de discrepancias
- Opción interactiva para corregir

## Cómo Prevenir Esto en el Futuro

### ✅ Buenas Prácticas

1. **Al eliminar participantes**, asegúrate que se reste correctamente del contador:
   ```python
   # Restar tablas usadas
   mongo_collection_users.update_one(
       {"_id": usuario_id},
       {"$inc": {"usedTables": -num_tablas}}  # IMPORTANTE: El operador correcto
   )
   ```

2. **Mantener consistencia** en todas las operaciones que afecten tablas

3. **Validar periódicamente** usando el endpoint o script

4. **Revisar cambios** antes de hacer operaciones en batch

### ⚠️ Causas Comunes de Discrepancias

- Eliminar participantes sin actualizar `usedTables`
- Errores en operaciones de actualización (inc vs set)
- Eliminación manual de registros sin mantener la consistencia
- Bugs en endpoints que modifican tablas

## Resumen de Corrección

El usuario `690cccb58fd0fbff298e9dba` ha sido corregido:

| Métrica | Antes | Después |
|---------|-------|---------|
| usedTables (BD) | 63 | **78** ✅ |
| Tablas Reales | 78 | **78** ✅ |
| Disponibles | 17 | **2** ✅ |
| Estado | ❌ Inconsistente | ✅ Correcto |

---

*Última actualización: 1 de diciembre de 2025*
