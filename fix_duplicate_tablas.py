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
    results = []
    for p in participantes:
        cedula = p.get('cedula')
        if cedula:
            r = dedupe_participant_by_cedula(cedula)
            results.append({'cedula':cedula, 'result': r})
    # Recalcular usedTables para el usuario
    total = sum(len(p.get('tablas', [])) for p in part.find({'registrado_por':user_obj_id}))
    users.update_one({'_id':user_obj_id},{'$set':{'usedTables':total}})
    return {'deduped': results, 'usedTables_updated': total}


def recalc_usedTables_for_user(user_obj_id):
    if isinstance(user_obj_id, str) and len(user_obj_id)==24:
        user_obj_id = ObjectId(user_obj_id)
    total = sum(len(p.get('tablas', [])) for p in part.find({'registrado_por':user_obj_id}))
    users.update_one({'_id':user_obj_id},{'$set':{'usedTables':total}})
    return total


if __name__=='__main__':
    # comportamiento por defecto: ejecutar dedupe para la cédula hardcodeada si se desea
    print('Uso: importar funciones desde este módulo: dedupe_participant_by_cedula, dedupe_all_participants_for_user')
