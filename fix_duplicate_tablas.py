from pymongo import MongoClient
from bson import ObjectId
import json
from bson import json_util

client=MongoClient('mongodb://localhost:27017/')
db=client['bingo_db']
part=db['Participantes']
users=db['Users']

def dedupe_participant_by_cedula(cedula):
    """Elimina duplicados en el campo `tablas` de un participante identificado por su cédula.
    Devuelve (before_count, after_count, updated_tablas_list).
    """
    res=part.find_one({'cedula':cedula})
    if not res:
        return None
    before=len(res.get('tablas', []))
    # build unique preserving order
    seen=set()
    new_tablas=[]
    for entry in res.get('tablas', []):
        # normalize to string id
        if isinstance(entry, dict):
            sid = entry.get('$oid') or str(entry)
        else:
            sid = str(entry)
        if sid not in seen:
            seen.add(sid)
            # if looks like ObjectId string convert
            try:
                new_tablas.append(ObjectId(sid))
            except Exception:
                new_tablas.append(sid)
    # update participant
    part.update_one({'_id':res['_id']},{'$set':{'tablas':new_tablas}})
    res2=part.find_one({'cedula':cedula})
    if not res2:
        return (before, 0, [], None)
    after=len(res2.get('tablas', []))
    return (before, after, res2.get('tablas', []), res2)


def dedupe_all_participants_for_user(user_obj_id):
    """Ejecuta dedupe en todos los participantes registrados por un usuario (ObjectId o str)."""
    if isinstance(user_obj_id, str) and len(user_obj_id)==24:
        user_obj_id = ObjectId(user_obj_id)
    participantes = list(part.find({'registrado_por':user_obj_id}))
    # dedupe por cedula única para evitar procesar la misma cédula varias veces
    cedulas = []
    for p in participantes:
        c = p.get('cedula')
        if c and c not in cedulas:
            cedulas.append(c)

    results = []
    for cedula in cedulas:
        r = dedupe_participant_by_cedula(cedula)
        results.append({'cedula': cedula, 'result': r})

    # Recalcular usedTables para el usuario: contar tablas únicas (no sumar duplicados entre documentos)
    unique_table_ids = set()
    for p in part.find({'registrado_por': user_obj_id}):
        for t in p.get('tablas', []):
            # normalizar a string
            try:
                if isinstance(t, ObjectId):
                    sid = str(t)
                elif isinstance(t, dict):
                    sid = t.get('$oid') or str(t)
                else:
                    sid = str(t)
            except Exception:
                sid = str(t)
            unique_table_ids.add(sid)

    total = len(unique_table_ids)
    users.update_one({'_id': user_obj_id}, {'$set': {'usedTables': total}})
    return {'deduped': results, 'usedTables_updated': total}


def recalc_usedTables_for_user(user_obj_id):
    if isinstance(user_obj_id, str) and len(user_obj_id)==24:
        user_obj_id = ObjectId(user_obj_id)
    # contar tablas únicas entre todos los participantes del usuario
    unique_table_ids = set()
    for p in part.find({'registrado_por': user_obj_id}):
        for t in p.get('tablas', []):
            try:
                if isinstance(t, ObjectId):
                    sid = str(t)
                elif isinstance(t, dict):
                    sid = t.get('$oid') or str(t)
                else:
                    sid = str(t)
            except Exception:
                sid = str(t)
            unique_table_ids.add(sid)

    total = len(unique_table_ids)
    users.update_one({'_id': user_obj_id}, {'$set': {'usedTables': total}})
    return total


if __name__=='__main__':
    pass


def merge_duplicate_participants_for_user(user_obj_id, cedula=None, dry_run=True):
    """Consolida participantes con la misma `cedula` registrados por `user_obj_id`.
    Si `dry_run=True` no modifica la BD, solo devuelve un resumen.
    Comportamiento de fusión:
      - Selecciona un documento canónico (el de menor _id) por cédula.
      - Combina todas las `tablas` de los documentos con la misma cédula en una lista única.
      - Actualiza el documento canónico con la lista única y elimina los demás documentos (si dry_run=False).
    Devuelve un dict con el resumen por cédula y el nuevo `usedTables` calculado.
    """
    if isinstance(user_obj_id, str) and len(user_obj_id) == 24:
        user_obj_id = ObjectId(user_obj_id)

    participantes = list(part.find({'registrado_por': user_obj_id}))
    # agrupar por cedula
    groups = {}
    for p in participantes:
        c = p.get('cedula')
        if not c:
            continue
        groups.setdefault(c, []).append(p)

    # si se pasó una cédula, filtrar a ese grupo únicamente
    if cedula:
        groups = {c: docs for c, docs in groups.items() if c == cedula}

    results = []
    for cedula, docs in groups.items():
        if len(docs) <= 1:
            continue

        # reunir tablas únicas entre todos los documentos
        unique_table_ids = set()
        for d in docs:
            for t in d.get('tablas', []):
                try:
                    if isinstance(t, ObjectId):
                        sid = str(t)
                    elif isinstance(t, dict):
                        sid = t.get('$oid') or str(t)
                    else:
                        sid = str(t)
                except Exception:
                    sid = str(t)
                unique_table_ids.add(sid)

        # convertir a ObjectId cuando sea posible
        merged_tablas = []
        for sid in unique_table_ids:
            try:
                merged_tablas.append(ObjectId(sid))
            except Exception:
                merged_tablas.append(sid)

        # elegir canónico: el documento con menor _id (estable)
        docs_sorted = sorted(docs, key=lambda x: str(x.get('_id')))
        canonical = docs_sorted[0]
        others = docs_sorted[1:]

        kept_id = str(canonical.get('_id'))
        deleted_ids = [str(o.get('_id')) for o in others]

        if not dry_run:
            # actualizar canónico
            part.update_one({'_id': canonical['_id']}, {'$set': {'tablas': merged_tablas}})
            # eliminar los duplicados
            ids_to_delete = [o['_id'] for o in others]
            if ids_to_delete:
                part.delete_many({'_id': {'$in': ids_to_delete}})

        results.append({
            'cedula': cedula,
            'kept_id': kept_id,
            'deleted_ids': deleted_ids,
            'merged_tablas_count': len(merged_tablas),
            'dry_run': bool(dry_run)
        })

    # recalcular usedTables (función ya maneja contar tablas únicas)
    total = recalc_usedTables_for_user(user_obj_id)
    return {'merged': results, 'usedTables_updated': total}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Herramientas para dedupe/merge de participantes y recálculo de usedTables')
    parser.add_argument('--user', '-u', help='User ObjectId que registró los participantes', required=True)
    parser.add_argument('--cedula', '-c', help='(Opcional) cédula específica a consolidar')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--dry-run', dest='dry_run', action='store_true', help='Solo mostrar lo que se haría (por defecto)')
    group.add_argument('--apply', dest='dry_run', action='store_false', help='Aplicar cambios en la BD')
    parser.set_defaults(dry_run=True)

    args = parser.parse_args()
    user_id = args.user
    ced = args.cedula
    dry = args.dry_run

    print(f"Ejecutando merge_duplicate_participants_for_user user={user_id} cedula={ced} dry_run={dry}")
    res = merge_duplicate_participants_for_user(user_id, cedula=ced, dry_run=dry)
    try:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    except Exception:
        print(res)
