# ==========================
# IMPORTS
# ==========================
import re
import pdfplumber
import json
from collections import defaultdict
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import random
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import io
from reportlab.lib.units import inch
import os
import json
import sys
import time
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from datetime import datetime
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
import hashlib
from pymongo.errors import BulkWriteError, DuplicateKeyError

# ==========================
# RUTAS
# ==========================
json_dir = "./jsons"
winners_dir = "./winners"
upload_dir = "./upload"

# ==========================
# Conexión a MongoDB
# ==========================
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["bingo_db"]
mongo_collection_winners = mongo_db["tablas_ganadoras"]
mongo_collection_tables = mongo_db["tablas"]
mongo_collection_students = mongo_db["Estudiantes"]
mongo_collection_participantes = mongo_db["Participantes"]
mongo_collection_users = mongo_db["Users"]
mongo_collection_teachers = mongo_db["Docentes"]

# ==========================
# FUNCIONES
# ==========================

# --- Verificar existencia de tablas ---
def check_tables_exist():
    return mongo_collection_tables.count_documents({}) > 0

# --- Generador de cartón ---
def generate_bingo_card():
    card = []
    ranges = {
        0: range(1, 16),
        1: range(16, 31),
        2: range(31, 46),
        3: range(46, 61),
        4: range(61, 76)
    }
    for col in range(5):
        numbers = random.sample(ranges[col], 5)
        card.append(numbers)
    card = list(map(list, zip(*card)))
    card[2][2] = None  # centro libre
    return card

# --- Valida que no exista tablas duplicadas---
def validar_duplicados(cards_data):
    total_cards = len(cards_data)
    matrices_as_tuples = [tuple(tuple(row) for row in card["matrix"]) for card in cards_data]
    unique_matrices = set(matrices_as_tuples)
    duplicates = total_cards - len(unique_matrices)
    matrix_to_serials = defaultdict(list)
    for card in cards_data:
        key = tuple(tuple(row) for row in card["matrix"])
        matrix_to_serials[key].append(card["serial"])
    duplicated_serials = {key: serials for key, serials in matrix_to_serials.items() if len(serials) > 1}
    return {
        "total": total_cards,
        "unicos": len(unique_matrices),
        "duplicados": duplicates,
        "duplicados_seriales": duplicated_serials
    }

# --- Obtiene la infromacion del json generado ---
def get_current_cards():
    files = [f for f in os.listdir(json_dir) if f.endswith('.json')]
    if not files:
        return []
    # Ordenar por fecha de modificación descendente
    files.sort(key=lambda f: os.path.getmtime(os.path.join(json_dir, f)), reverse=True)
    with open(os.path.join(json_dir, files[0]), "r", encoding="utf-8") as f:
        return json.load(f)
    


# -------------------------
# Utilidades para clustering simple
# -------------------------
def cluster_positions(positions, max_gap=15):
    if not positions:
        return []
    positions = sorted(positions)
    clusters = [[positions[0]]]
    for p in positions[1:]:
        if abs(p - clusters[-1][-1]) <= max_gap:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    centers = [sum(c)/len(c) for c in clusters]
    return centers

def nearest_index(centers, value):
    if not centers:
        return None
    best = min(range(len(centers)), key=lambda i: abs(centers[i] - value))
    return best


def safe_int(val, default=0):
    """Convierte a int de forma segura; si val es None o inválido, devuelve default."""
    try:
        if val is None:
            return default
        return int(val)
    except Exception:
        return default

# -------------------------
# Nueva: extraer_matrices_pdf (soporta 4 cartones/hoja + fallback)
# -------------------------
def extraer_matrices_pdf(pdf_path, output_json):
    serial_pattern = re.compile(r'CARD\d{5}')
    number_pattern = re.compile(r'^\d+$')
    cards_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            # Intento ESTRUCTURADO: asumimos layout generado por tu /generate (4 por página)
            page_w = page.width
            page_h = page.height
            MARGIN_X = 0.5 * inch
            MARGIN_Y = 0.5 * inch
            CARD_WIDTH = (page_w - 2 * MARGIN_X) / 2
            CARD_HEIGHT = (page_h - 2 * MARGIN_Y) / 2

            # Comprobación rápida: si en el texto aparece "BINGO" o "BINGO UETS" o varios "CARD", aplicamos extracción estructurada
            if ("BINGO" in page_text.upper()) or ("CARD" in page_text.upper()):
                # Recorremos la grilla 2x2 (fila, columna) para cada card en la página
                for card_row in range(2):
                    for card_col in range(2):
                        x = MARGIN_X + card_col * CARD_WIDTH
                        y = page_h - MARGIN_Y - (card_row + 1) * CARD_HEIGHT

                        # coordenadas del grid tal como lo generas en /generate
                        grid_top = y + CARD_HEIGHT - 55
                        grid_left = x + 10
                        cell_w = (CARD_WIDTH - 20) / 5
                        cell_h = (CARD_HEIGHT - 60) / 6

                        matrix = []
                        for r in range(5):
                            row = []
                            for c in range(5):
                                if r == 2 and c == 2:
                                    row.append(None)
                                    continue
                                bbox = (
                                    grid_left + c * cell_w,
                                    grid_top - (r + 1) * cell_h,
                                    grid_left + (c + 1) * cell_w,
                                    grid_top - r * cell_h
                                )
                                cropped = page.within_bbox(bbox)
                                txt = (cropped.extract_text() or "").strip()
                                num = None
                                if txt:
                                    m = re.search(r'\d+', txt)
                                    if m:
                                        try:
                                            num = int(m.group())
                                        except:
                                            num = None
                                else:
                                    # intentar con palabras si extract_text no devolvió nada
                                    words = cropped.extract_words()
                                    if words:
                                        center_x = (bbox[0] + bbox[2]) / 2
                                        best = min(words, key=lambda w: abs(float(w.get('x0', 0)) - center_x))
                                        try:
                                            num = int(best.get('text', '').strip())
                                        except:
                                            num = None
                                row.append(num)
                            matrix.append(row)

                        # Buscar serial dentro del área superior del card (donde lo dibujas)
                        header_bbox = (x, y + CARD_HEIGHT - 45, x + CARD_WIDTH, y + CARD_HEIGHT - 10)
                        header_crop = page.within_bbox(header_bbox)
                        header_txt = (header_crop.extract_text() or "") + " " + page_text  # fallback al page_text
                        serial_match = serial_pattern.search(header_txt)
                        if serial_match:
                            serial = serial_match.group()
                        else:
                            serial = f"PAGE{page_number}_R{card_row}C{card_col}"

                        # Asegurar centro libre
                        matrix[2][2] = None
                        cards_data.append({"serial": serial, "matrix": matrix})
                # continuar con la siguiente página
                continue

            # -------------------------
            # FALLBACK (cuando no detectamos el layout): agrupación por palabras/clustering
            # -------------------------
            words = page.extract_words()
            num_words = []
            for w in words:
                txt = w.get('text', '').strip()
                if number_pattern.match(txt):
                    try:
                        num_words.append({'num': int(txt), 'x': float(w.get('x0', 0)), 'y': float(w.get('top', 0)), 'word': w})
                    except:
                        pass

            if not num_words:
                continue

            # Intento agrupar en 5x5 por clustering global
            xs = [w['x'] for w in num_words]
            ys = [w['y'] for w in num_words]
            x_centers = cluster_positions(xs, max_gap=18)
            y_centers = cluster_positions(ys, max_gap=12)
            if len(x_centers) < 5:
                x_centers = cluster_positions(xs, max_gap=30)
            if len(y_centers) < 5:
                y_centers = cluster_positions(ys, max_gap=20)

            # Si clustering no nos dio 5x5, fallback secuencial por texto
            if len(x_centers) < 5 or len(y_centers) < 5:
                # tomar los números del texto en orden y formar n cartones de 24 números
                numbers = [int(n) for n in re.findall(r'\b\d+\b', page_text)]
                serials = serial_pattern.findall(page_text)
                if serials:
                    # eliminar número del serial si aparece como número suelto (ej: 79)
                    try:
                        serial_num = int(serials[0].replace('CARD', ''))
                        numbers = [n for n in numbers if n != serial_num]
                    except:
                        pass
                if len(numbers) >= 24:
                    groups = len(numbers) // 24
                    for i in range(groups):
                        nums = numbers[i*24:(i+1)*24]
                        matrix = []
                        idx = 0
                        for r in range(5):
                            row = []
                            for c in range(5):
                                if r == 2 and c == 2:
                                    row.append(None)
                                else:
                                    row.append(nums[idx] if idx < len(nums) else None)
                                    idx += 1
                            matrix.append(row)
                        s = serials[i] if i < len(serials) else f"PAGE{page_number}_SEQ{i+1}"
                        cards_data.append({"serial": s, "matrix": matrix})
                continue

            # reconstruir grid usando centres
            x_centers = sorted(x_centers)
            y_centers = sorted(y_centers)
            grid = [[None for _ in range(5)] for _ in range(5)]
            for it in num_words:
                col_idx = nearest_index(x_centers, it['x'])
                row_idx = nearest_index(y_centers, it['y'])
                if col_idx is None or row_idx is None:
                    continue
                if 0 <= row_idx < 5 and 0 <= col_idx < 5:
                    if grid[row_idx][col_idx] is None:
                        grid[row_idx][col_idx] = it['num']
            grid[2][2] = None
            serials = serial_pattern.findall(page_text)
            serial = serials[0] if serials else f"PAGE{page_number}_AUTO"
            cards_data.append({"serial": serial, "matrix": grid})

    # Guardar resultado en JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(cards_data, f, indent=2, ensure_ascii=False)

    return cards_data


# --- Busca la tabla ganadora y valida ---
def check_winner_py(marks):
    for row in marks:
        if all(row):
            return True
    for c in range(5):
        if all(marks[r][c] for r in range(5)):
            return True
    if all(marks[i][i] for i in range(5)):
        return True
    if all(marks[i][4-i] for i in range(5)):
        return True
    return False


# --- Validar y corregir contadores de tablas asignadas ---
def validar_y_corregir_tablas_usuario(usuario_id):
    """
    Valida y corrige los contadores de tablas asignadas para un usuario específico.
    
    Retorna:
    - total_asignadas: Número real de tablas asignadas a participantes del usuario
    - used_tables_db: Valor en la BD
    - diferencia: Diferencia entre real y en BD
    - tablas_disponibles: Lista de seriales de tablas disponibles
    - corregido: Si fue corregido o no
    """
    try:
        usuario_obj_id = ObjectId(usuario_id) if isinstance(usuario_id, str) else usuario_id
        
        # Obtener usuario
        usuario = mongo_collection_users.find_one({"_id": usuario_obj_id})
        if not usuario:
            return {"error": "Usuario no encontrado"}
        
        # Contar participantes registrados por este usuario
        participantes = list(mongo_collection_participantes.find({"registrado_por": usuario_obj_id}))
        
        # Contar tablas reales asignadas (sumar tablas de cada participante)
        total_tablas_reales = 0
        for p in participantes:
            tablas = p.get("tablas", [])
            total_tablas_reales += len(tablas)
        
        # Valor en la BD
        used_tables_bd = usuario.get("usedTables", 0)
        
        # Diferencia
        diferencia = used_tables_bd - total_tablas_reales
        
        # Si hay diferencia, corregir
        if diferencia != 0:
            mongo_collection_users.update_one(
                {"_id": usuario_obj_id},
                {"$set": {"usedTables": total_tablas_reales}}
            )
            corregido = True
        else:
            corregido = False
        
        # Obtener tablas disponibles (no asignadas) dentro del rango del usuario
        tablas_disponibles = []
        fromSerial = usuario.get('fromSerial')
        toSerial = usuario.get('toSerial')
        
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
            
            tablas_disp = list(mongo_collection_tables.find(
                query,
                {"serial": 1}
            ).sort("serial", 1))
            
            tablas_disponibles = [t['serial'] for t in tablas_disp]
        
        return {
            "success": True,
            "usuario_id": str(usuario_obj_id),
            "usuario": usuario.get("usuario", "N/A"),
            "nombres_completos": usuario.get("nombres_completos", "N/A"),
            "total_participantes": len(participantes),
            "tablas_reales_asignadas": total_tablas_reales,
            "used_tables_bd_anterior": used_tables_bd,
            "used_tables_bd_nuevo": total_tablas_reales,
            "diferencia": diferencia,
            "corregido": corregido,
            "totalTables": usuario.get("totalTables", 0),
            "disponibles_ahora": usuario.get("totalTables", 0) - total_tablas_reales,
            "rango_tablas": {
                "desde": fromSerial,
                "hasta": toSerial
            },
            "tablas_disponibles": tablas_disponibles
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "success": False
        }


# ==========================
# JUEGO DE BINGO
# ==========================
app = Flask(__name__)
# Habilitar CORS para las rutas de la API. Permitir específicamente el frontend en localhost:3000
# Ajusta origins si necesitas permitir otros orígenes o usa '*' para permitir todos (menos seguro).
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)


# ==========================
# ENDPOINTS
# ==========================

@app.route('/')
def index():
    """Ruta principal que verifica si existen tablas en la base de datos."""
    has_tables = check_tables_exist()
    return render_template('index.html', has_tables=has_tables)

@app.route('/test_mongo', methods=['GET'])
def test_mongo():
    """Prueba simple de conexión con MongoDB."""
    try:
        if mongo_client is None:
            return jsonify({"success": False, "message": "Cliente MongoDB no inicializado."}), 500
        mongo_client.admin.command('ping')
        dbs = mongo_client.list_database_names()
        return jsonify({
            "success": True,
            "message": "Conexión exitosa a MongoDB.",
            "databases": dbs
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Endpoint para marcar/desmarcar un número en todas las matrices
@app.route('/mark', methods=['POST'])
def mark_number():
    data = request.get_json(silent=True) or {}
    num = data.get('num')
    marcado = data.get('marcado', True)
    files = [f for f in os.listdir(json_dir) if f.endswith('.json')]
    if not files:
        return jsonify({'success': False, 'message': 'No hay cartones'}), 400
    files.sort(reverse=True)
    path = os.path.join(json_dir, files[0])
    with open(path, 'r', encoding='utf-8') as f:
        cards = json.load(f)
    ganadores = []
    for card in cards:
        matrix = card['matrix']
        marks = card.get('marks', [[False]*5 for _ in range(5)])
        for r in range(5):
            for c in range(5):
                if matrix[r][c] == num:
                    marks[r][c] = marcado
        # Centro libre siempre marcado
        marks[2][2] = True
        card['marks'] = marks
        # Validar ganador
        card['won'] = check_winner_py(marks)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)
    return jsonify({'success': True, 'ganadores': ganadores})

# ENDPOINT PARA RUTAS DE RENDERIZADO
# @app.route('/')
# def index():
#     return render_template('index.html')

@app.route('/pages/masterTable.html')
def master_table():
    return render_template('pages/masterTable.html')

# ENDPOINT PARA VALIDAR EL PROGRESO DE CADA CARTÓN
@app.route('/progress', methods=['GET'])
def progress():
    cards = get_current_cards()
    progreso = []
    for card in cards:
        aciertos = 0
        marks = card.get("marks", [[False]*5 for _ in range(5)])
        matrix = card.get("matrix", [[None]*5 for _ in range(5)])
        for r in range(5):
            for c in range(5):
                # Si la casilla está marcada o es null (libre), cuenta como acierto
                if marks[r][c] or matrix[r][c] is None:
                    aciertos += 1
        card["aciertos"] = aciertos
        # Solo es ganador si tiene exactamente 25 aciertos (excluyendo el centro libre)
        card["won"] = (aciertos == 25)
        ganadores = []
        if card['won']:
            ganadores.append(card['serial'])
            try:
                # Guardar en MongoDB solo si ganó
                mongo_collection_winners.update_one(
                    {"serial": card["serial"]},
                    {"$set": {
                        "serial": card["serial"],
                        "matrix": card["matrix"],
                        "won": True,
                        "timestamp": time.time()
                    }},
                    upsert=True
                )
                print(f"✅ Cartón ganador guardado en MongoDB: {card['serial']}")
                # 🔄 Actualizar estado 'won' solo si ganó
                mongo_collection_tables.update_one(
                    {"serial": card["serial"]},
                    {"$set": {
                        "won": True
                    }}
                )
                print(f"🔄 Estado 'won' actualizado en tabla: {card['serial']}")
            except Exception as e:
                print(f"❌ Error al guardar el ganador {card['serial']}: {e}")
        progreso.append({"serial": card["serial"], "aciertos": aciertos, "won": card["won"]})
    progreso.sort(key=lambda x: x["aciertos"], reverse=True)
    top3 = progreso[:3]
    ganadores = [p for p in progreso if p["won"]]
    return jsonify({"top3": top3, "ganadores": ganadores})

# ENDPOINT PARA GENERAR PDF DEL GANADOR
@app.route('/winner_pdf', methods=['POST'])
def winner_pdf():
    data = request.get_json(silent=True) or {}
    serial = data.get('serial')
    matrix = data.get('matrix')
    marks = data.get('marks')
    if not serial:
        return jsonify({"error": "Faltan datos"}), 400
    if not matrix or not marks:
        cards = get_current_cards()
        card = next((c for c in cards if c["serial"] == serial), None)
        if not card:
            return jsonify({"error": "Cartón no encontrado"}), 404
        matrix = card["matrix"]
        marks = card.get("marks", [[False]*5 for _ in range(5)])
    os.makedirs(winners_dir, exist_ok=True)
    filename = f"ganador_{serial}.pdf"
    pdf_path = os.path.join(winners_dir, filename)
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(200, 750, f"Cartón ganador #{serial}")
    # Dibujar matriz ganadora
    x0, y0 = 100, 650
    size = 40
    # Encabezados BINGO
    c.setFont("Helvetica-Bold", 12)
    for i, letra in enumerate(["B", "I", "N", "G", "O"]):
        c.drawString(x0 + i*size + 10, y0 + 20, letra)
    c.setFont("Helvetica", 10)
    for r in range(5):
        for col in range(5):
            x = x0 + col * size
            y = y0 - r * size
            num = matrix[r][col]
            text = "FREE" if (r, col) == (2, 2) else str(num) if num else ""
            # Dibujar celda
            c.rect(x, y, size, size)
            # Si está marcado, tachar el número
            if marks[r][col]:
                c.setFillColorRGB(1, 0, 0)
                c.setFont("Helvetica-Bold", 12)
                c.drawString(x + 12, y + 12, text)
                # Línea de tachado
                c.setLineWidth(2)
                c.line(x + 5, y + size/2, x + size - 5, y + size/2)
                c.setLineWidth(1)
            else:
                c.setFillColorRGB(0, 0, 0)
                c.setFont("Helvetica", 10)
                c.drawString(x + 12, y + 12, text)
    c.save()
    return jsonify({"success": True, "pdf_path": pdf_path, "message": f"PDF ganador guardado en: {pdf_path}"})

# ENDPOINT PARA REINICIAR EL JUEGO
@app.route('/reset', methods=['POST'])
def reset():
    # Reconstruir JSON activo leyendo la colección 'tablas' en MongoDB
    try:
        # Obtener todas las tablas que NO sean ganadoras y que estén asignadas (solo las que participan en el juego)
        # Se filtra por "stateAsigned": True para asegurar que solo juegan las tablas asignadas a participantes
        active_cursor = mongo_collection_tables.find(
            {
                "$and": [
                    {"$or": [{"won": False}, {"won": {"$exists": False}}]},
                    {"stateAsigned": True}
                ]
            },
            {"serial": 1, "matrix": 1, "stateAsigned": 1}
        )
        active_rows = list(active_cursor)
    except Exception as e:
        return jsonify({"success": False, "message": "Error al leer la base de datos", "error": str(e)}), 500

    # Si no hay tablas activas, devolver mensaje
    if not active_rows:
        # crear un JSON vacío para que el frontend no falle
        os.makedirs(json_dir, exist_ok=True)
        output_json = os.path.join(json_dir, f"bingo_cards_active_{int(time.time())}.json")
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)
        return jsonify({"success": True, "message": "No hay cartones activos (todos son ganadores)", "removed_winners": 0, "json_path": output_json})

    # Construir lista de cartones a partir de la BD
    cards = []
    for r in active_rows:
        serial = r.get('serial')
        matrix = r.get('matrix', [[None]*5 for _ in range(5)])
        # asegurarse que el centro esté en None
        try:
            matrix[2][2] = None
        except Exception:
            pass
        card = {
            "serial": serial,
            "matrix": matrix,
            "marks": [[False for _ in range(5)] for _ in range(5)],
            "won": False,
            "aciertos": 0
        }
        # marcar centro libre
        card["marks"][2][2] = True
        cards.append(card)

    # Guardar nuevo JSON con timestamp (el frontend elegirá el archivo más reciente)
    os.makedirs(json_dir, exist_ok=True)
    output_json = os.path.join(json_dir, f"bingo_cards_active_{int(time.time())}.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)

    # Contar ganadores en la colección para información
    try:
        winners_count = mongo_collection_tables.count_documents({"won": True})
    except Exception:
        winners_count = 0

    removed_winners = winners_count

    msg = f"Juego reiniciado — JSON reconstruido desde DB. Cartones activos: {len(cards)}"
    if removed_winners:
        msg += f" — cartones ganadores detectados en DB: {removed_winners}"

    return jsonify({"success": True, "message": msg, "removed_winners": removed_winners, "json_path": output_json, "active_count": len(cards)})

# ENDPOINT PARA GENERAR CARTONES EN PDF
@app.route('/generate', methods=['POST'])
def generate_cards():
    data = request.get_json(silent=True) or {}
    num_cards = safe_int(data.get("num_cards"), 1)
    PAGE_WIDTH, PAGE_HEIGHT = letter
    MARGIN_X = 0.5 * inch
    MARGIN_Y = 0.5 * inch
    CARD_WIDTH = (PAGE_WIDTH - 2*MARGIN_X) / 2
    CARD_HEIGHT = (PAGE_HEIGHT - 2*MARGIN_Y) / 2
    CARDS_PER_PAGE = 4
    os.makedirs(upload_dir, exist_ok=True)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    cards_list = []
    generated = set()

    for i in range(num_cards):
        while True:
            card = generate_bingo_card()

            # Convertir matriz a tupla hashable
            signature = tuple(tuple(row) for row in card)

            if signature not in generated:
                generated.add(signature)
                serial = f"CARD{str(i+1).zfill(5)}"
                cards_list.append((serial, card))
                break
    ##cards_list = [(f"CARD{str(i+1).zfill(5)}", generate_bingo_card()) for i in range(num_cards)]
    cards_data = []
    for idx, (serial, card) in enumerate(cards_list):
        page_pos = idx % CARDS_PER_PAGE
        row = page_pos // 2
        col = page_pos % 2
        x = MARGIN_X + col*CARD_WIDTH
        y = PAGE_HEIGHT - MARGIN_Y - (row+1)*CARD_HEIGHT
        # Dibuja el cartón
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(x + CARD_WIDTH/2, y + CARD_HEIGHT - 15, "BINGO UETS")
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x + CARD_WIDTH/2, y + CARD_HEIGHT - 30, serial)
        grid_top = y + CARD_HEIGHT - 55
        grid_left = x + 10
        cell_w = (CARD_WIDTH - 20) / 5
        cell_h = (CARD_HEIGHT - 60) / 6
        c.setFont("Helvetica-Bold", 10)
        for i, L in enumerate(["B","I","N","G","O"]):
            c.drawCentredString(grid_left + i*cell_w + cell_w/2, grid_top, L)
        extra_space = 15
        c.setFont("Helvetica", 8)
        for r in range(5):
            for col2 in range(5):
                left = grid_left + col2*cell_w
                top = grid_top - extra_space - (r+1)*cell_h
                c.rect(left, top, cell_w, cell_h)
                val = card[r][col2]
                txt = str(val) if val is not None else " "
                c.drawCentredString(left + cell_w/2, top + cell_h/2 - 3, txt)
        if page_pos == CARDS_PER_PAGE-1 or idx == len(cards_list)-1:
            c.showPage()
        cards_data.append({"serial": serial, "matrix": card})
    c.save()
    buffer.seek(0)
    pdf_path = os.path.join(upload_dir, f"bingo_cards_{num_cards}.pdf")
    with open(pdf_path, "wb") as fpdf:
        fpdf.write(buffer.getvalue())
    os.makedirs(json_dir, exist_ok=True)
    output_json = os.path.join(json_dir, f"bingo_cards_{num_cards}.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(cards_data, f, indent=2, ensure_ascii=False)
    
    # 🔥 Guardar todas las tablas generadas en MongoDB
    try:
        for card in cards_data:
            mongo_collection_tables.update_one(
                {"serial": card["serial"]},
                {"$set": {
                    "serial": card["serial"],
                    "matrix": card["matrix"],
                    "timestamp": time.time(),
                    "won": False,
                    "stateAsigned": False
                }},
                upsert=True
            )
        print(f"✅ Todas las tablas generadas guardadas en MongoDB.")
    except Exception as e:
        print(f"❌ Error al guardar las tablas generadas en MongoDB: {e}")

    # 🔥 Nuevo: Validar duplicados automáticamente
    validacion = validar_duplicados(cards_data)

    return jsonify({
        "success": True,
        "pdf_path": pdf_path,
        "json_path": output_json,
        "total_cartones": validacion["total"],
        "cartones_unicos": validacion["unicos"],
        "cartones_duplicados": validacion["duplicados"],
        "duplicados_seriales": validacion["duplicados_seriales"],
        "message": f"PDF guardado en: {pdf_path}, JSON en: {output_json}"
    })

# Endpoint para obtener el JSON actual de cartones
@app.route('/get_cards', methods=['GET'])
def get_cards():
    cards = get_current_cards()
    return jsonify(cards)


# ENDPOINT PARA OBTENER LA/LAS TABLA(S) GANADORA(S) EN JSON
@app.route('/tabla_ganadora', methods=['GET'])
def tabla_ganadora():
    """
    Devuelve todas las tablas ganadoras almacenadas en MongoDB.
    Si no existen registros, devuelve un mensaje apropiado.
    """
    try:
        # Obtener todas las tablas ganadoras de MongoDB
        ganadoras = list(mongo_collection_winners.find({}, {"_id": 0}))  # excluye _id del resultado

        if not ganadoras:
            return jsonify({
                "success": False,
                "message": "No hay tablas ganadoras registradas en la base de datos."
            }), 404

        return jsonify({
            "success": True,
            "count": len(ganadoras),
            "type": "ganadores",
            "cards": ganadoras
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ENDPOINT PARA BUSCAR ESTUDIANTE POR CÉDULA

@app.route('/api/estudiante/<busqueda>', methods=['GET'])
def buscar_estudiante(busqueda):
    """
    Busca un estudiante únicamente por:
    - Cédula (si es numérica)
    - Nombre completo exacto (Primer Apellido, Segundo Apellido, Nombre)
    """

    try:
        # --- Caso 1: Búsqueda por CÉDULA (solo números) ---
        if busqueda.isdigit():
            estudiante = mongo_collection_students.find_one(
                {"Num documento": busqueda},
                {"_id": 0}
            )
            if estudiante:
                return jsonify({"success": True, "estudiante": estudiante})

            return jsonify({
                "success": False,
                "message": f"No se encontró ningún estudiante con la cédula: {busqueda}"
            }), 404

        # --- Caso 2: Búsqueda por NOMBRE COMPLETO EXACTO ---
        palabras = busqueda.strip().upper().split()

        # Verificar formato: 2 apellidos + nombre(s)
        if len(palabras) < 3:
            return jsonify({
                "success": False,
                "message": "Debes enviar el nombre completo: Primer Apellido, Segundo Apellido y Nombre(s)."
            }), 400

        primer_apellido = palabras[0]
        segundo_apellido = palabras[1]
        nombre = " ".join(palabras[2:])   # Restante es el nombre completo

        estudiante = mongo_collection_students.find_one(
            {
                "Primer Apellido": primer_apellido,
                "Segundo Apellido": segundo_apellido,
                "Nombre": nombre
            },
            {"_id": 0}
        )

        if estudiante:
            return jsonify({"success": True, "estudiante": estudiante})

        return jsonify({
            "success": False,
            "message": f"No se encontró ningún estudiante con el nombre completo: {busqueda}"
        }), 404

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al buscar el estudiante en la base de datos"
        }), 500

# ENDPOINT PARA BUSCAR DOCENTE POR CÉDULA O NOMBRE COMPLETO
@app.route('/api/docente/<busqueda>', methods=['GET'])
def buscar_docente(busqueda):
    """
    Busca un docente por:
    - Cédula (si es numérica)
    - Nombre completo exacto (Primer Apellido, Segundo Apellido, Nombre)
    """

    try:
        # Caso 1: Búsqueda por cédula si son solo números
        if busqueda.isdigit():
            docente = mongo_collection_teachers.find_one(
                {"Cedula": busqueda},
                {"_id": 0}
            )

            if docente:
                return jsonify({"success": True, "docente": docente})

            return jsonify({
                "success": False,
                "message": f"No se encontró ningún docente con la cédula: {busqueda}"
            }), 404

        # Caso 2: Búsqueda por NOMBRE COMPLETO EXACTO
        palabras = busqueda.strip().upper().split()

        # Deben existir: 2 apellidos + 1 nombre mínimo
        if len(palabras) < 3:
            return jsonify({
                "success": False,
                "message": "Debes ingresar el nombre completo: Primer Apellido, Segundo Apellido y Nombre(s)."
            }), 400

        primer_apellido = palabras[0]
        segundo_apellido = palabras[1]
        nombre = " ".join(palabras[2:])   # Nombre completo (puede tener varias palabras)

        docente = mongo_collection_teachers.find_one(
            {
                "Primer Apellido": primer_apellido,
                "Segundo Apellido": segundo_apellido,
                "Nombre": nombre
            },
            {"_id": 0}
        )

        if docente:
            return jsonify({"success": True, "docente": docente})

        return jsonify({
            "success": False,
            "message": f"No se encontró ningún docente con el nombre completo: {busqueda}"
        }), 404

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al buscar el docente en la base de datos"
        }), 500


# ENDPOINT PARA VALIDAR LA EXISTENCIA DE LAS TABLAS INGRESADAS PARA PARTICIPAR 
@app.route('/api/validarTabla/<tabla>', methods=['POST'])
def validar_tabla(tabla):
    """
    Busca un estudiante por su número de cédula en la base de datos.
    
    Args:
        cedula (str): Número de cédula del estudiante a buscar.
        
    Returns:
        JSON con la información del estudiante o un mensaje de error si no se encuentra.
    """
    try:
        # Buscar el estudiante en la colección
        estudiante = mongo_collection_students.find_one({"Num documento": tabla}, {"_id": 0})
        
        if estudiante:
            return jsonify({
                "success": True,
                "estudiante": estudiante
            })
        else:
            return jsonify({
                "success": False,
                "message": f"No se encontró ningún estudiante con la cédula: {tabla}"
            }), 404
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al buscar el estudiante en la base de datos"
        }), 500
    
# -------------------------
# ENDPOINT PARA GENERAR PARTICIPANTES POST /api/participantes (alias de registrarParticipante)
# -------------------------
@app.route('/api/CreateParticipantes', methods=['POST'])
def crear_participante():
    """Alias para /api/CreateParticipantes"""
    return registrar_participante()

def calcular_total(num_tablas):
    # 1. Cobro por grupos de 5 → 10 dólares
    grupos_5 = num_tablas // 5
    resto = num_tablas % 5

    total = grupos_5 * 10

    # 2. Cobro por el resto:
    #    Cada 2 → 5 dólares
    #    Si queda 1 → 3 dólares
    total += (resto // 2) * 5
    total += (resto % 2) * 3

    return total

# ENDPOINT PARA REGISTRAR PARTICIPANTES
@app.route('/api/registrarParticipante', methods=['POST'])
def registrar_participante():
    try:
        participante_data = request.get_json(silent=True) or {}

        if not participante_data:
            return jsonify({"success": False, "message": "No se proporcionaron datos del participante."}), 400

        # =======================
        # CAMPOS DEL PARTICIPANTE
        # =======================
        nombre = participante_data.get("nombre")
        apellido = participante_data.get("apellido", "")
        cedula = participante_data.get("cedula", "")
        tablas_seriales = participante_data.get("tablas", [])
        registrado_por = participante_data.get("registrado_por")

        # ================================
        # VALIDAR Y CONVERTIR REGISTRADO POR
        # ================================
        if not registrado_por:
            return jsonify({
                "success": False,
                "message": "Debe incluir el campo 'registrado_por' (usuario que realiza el registro)."
            }), 400

        try:
            registrado_por = ObjectId(registrado_por)
        except:
            return jsonify({
                "success": False,
                "message": "El campo 'registrado_por' debe ser un ID de usuario válido."
            }), 400

        # ================================
        # OBTENER USUARIO LOGUEADO
        # ================================
        user_doc = mongo_collection_users.find_one({"_id": registrado_por})

        if not user_doc:
            return jsonify({"success": False, "message": "Usuario no encontrado."}), 404

        totalTables = user_doc.get("totalTables", 0)
        usedTables = user_doc.get("usedTables", 0)
        fromSerial = user_doc.get("fromSerial")
        toSerial = user_doc.get("toSerial")

        remaining = totalTables - usedTables
        num_tablas = len(tablas_seriales)

        # ================================
        # VALIDACIONES DE TABLAS DISPONIBLES
        # ================================
        if totalTables > 0 and remaining <= 0:
            return jsonify({"success": False, "message": "Ya no tienes tablas disponibles."}), 400

        if num_tablas > remaining:
            return jsonify({
                "success": False,
                "message": f"No puedes asignar {num_tablas} tablas. Solo tienes {remaining} disponibles."
            }), 400

        # ================================
        # VALIDACIONES DE CAMPOS OBLIGATORIOS
        # ================================
        if not nombre:
            return jsonify({"success": False, "message": "El campo 'nombre' es obligatorio."}), 400

        if not cedula:
            return jsonify({"success": False, "message": "El campo 'cedula' es obligatorio."}), 400

        if not tablas_seriales:
            return jsonify({"success": False, "message": "Debe asignarse al menos una tabla al participante."}), 400

        # ================================
        # VALIDAR DUPLICADO POR CÉDULA
        # ================================
        participante_existente = mongo_collection_participantes.find_one({"cedula": cedula})
        if participante_existente:
            animador_nombre = "desconocido"

            if participante_existente.get("registrado_por"):
                usuario_reg = mongo_collection_users.find_one(
                    {"_id": participante_existente["registrado_por"]},
                    {"nombres_completos": 1}
                )
                if usuario_reg and usuario_reg.get("nombres_completos"):
                    animador_nombre = usuario_reg["nombres_completos"]

            return jsonify({
                "success": False,
                "message": f"El participante con cédula {cedula} ya fue registrado por {animador_nombre}."
            }), 409

        # ================================
        # VALIDAR TABLAS
        # ================================
        tablas_validas = []
        for t in tablas_seriales:
            try:
                tablas_validas.append(ObjectId(t))
            except:
                # Validar serial dentro del rango permitido
                if fromSerial and toSerial:
                    # manejar rangos ascendentes o descendentes (admin reserva desde el final)
                    if fromSerial <= toSerial:
                        in_range = fromSerial <= t <= toSerial
                    else:
                        in_range = toSerial <= t <= fromSerial
                    if not in_range:
                        return jsonify({
                            "success": False,
                            "message": f"La tabla {t} está fuera del rango permitido ({fromSerial} a {toSerial})."
                        }), 400
                

                tabla = mongo_collection_tables.find_one({"serial": t})
                if not tabla:
                    return jsonify({"success": False, "message": f"Tabla '{t}' no encontrada."}), 404
                tablas_validas.append(tabla["_id"])

        # Verificar que no estén asignadas
        tablas_existentes = list(mongo_collection_tables.find(
            {"_id": {"$in": tablas_validas}}, {"stateAsigned": 1}
        ))

        if any(t.get("stateAsigned") for t in tablas_existentes):
            return jsonify({"success": False, "message": "Una o más tablas ya están asignadas."}), 400

        # ================================
        # CALCULAR TOTAL
        # ================================
        total_pagar = calcular_total(num_tablas)

        # ================================
        # INSERTAR PARTICIPANTE
        # ================================
        nuevo_participante = {
            "nombre": nombre,
            "apellido": apellido,
            "cedula": cedula,
            "celular": participante_data.get("celular", ""),
            "telefono": participante_data.get("telefono", participante_data.get("celular", "")),
            "tipo": participante_data.get("tipo", "alumno"),
            "nivelCurso": participante_data.get("nivelCurso", ""),
            "paralelo": participante_data.get("paralelo", ""),
            "animador": participante_data.get("animador", ""),
            "tablas": tablas_validas,
            "grupoAdetitss": participante_data.get("grupoAdetitss", ""),
            "fecha_registro": datetime.now().isoformat(),
            "registrado_por": registrado_por,
            "total_pagar": total_pagar
        }

        result = mongo_collection_participantes.insert_one(nuevo_participante)

        # Marcar tablas como asignadas
        mongo_collection_tables.update_many(
            {"_id": {"$in": tablas_validas}},
            {"$set": {"stateAsigned": True}}
        )

        # Actualizar contadores del usuario
        mongo_collection_users.update_one(
            {"_id": registrado_por},
            {"$inc": {
                "usedTables": num_tablas,
                "total_vendido": total_pagar
            }}
        )

        # Formato JSON serializable
        nuevo_participante["_id"] = str(result.inserted_id)
        nuevo_participante["registrado_por"] = str(registrado_por)
        nuevo_participante["tablas"] = [str(t) for t in tablas_validas]

        return jsonify({
            "success": True,
            "message": "Participante registrado exitosamente.",
            "participante": nuevo_participante
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al registrar el participante."
        }), 500

# -------------------------
# ENDPOINT PARA OBTENER TABLAS CONSECUTIVAS DISPONIBLES
# -------------------------
@app.route('/api/obtenerTablasConsecutivas', methods=['POST'])
def obtener_tablas_consecutivas():
    """
    Obtiene los códigos de tablas consecutivas disponibles para asignarlas a un participante.
    No asigna ni modifica, solo devuelve los códigos que se pueden usar.
    
    JSON esperado:
    {
        "usuario_id": "ObjectId del usuario",
        "cantidad_tablas": número de tablas que necesitas
    }
    
    Respuesta:
    {
        "success": true,
        "message": "Tablas disponibles obtenidas correctamente",
        "tablas_consecutivas": ["CARD004", "CARD005"],
        "cantidad": 2
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        usuario_id = data.get("usuario_id")
        cantidad_tablas = safe_int(data.get("cantidad_tablas"), 0)
        
        # Validaciones básicas
        if not usuario_id:
            return jsonify({
                "success": False,
                "message": "usuario_id es obligatorio."
            }), 400
        
        if cantidad_tablas <= 0:
            return jsonify({
                "success": False,
                "message": "La cantidad de tablas debe ser mayor a 0."
            }), 400
        
        # Convertir a ObjectId
        try:
            usuario_obj_id = ObjectId(usuario_id)
        except:
            return jsonify({
                "success": False,
                "message": "usuario_id inválido."
            }), 400
        
        # Obtener usuario
        usuario = mongo_collection_users.find_one({"_id": usuario_obj_id})
        if not usuario:
            return jsonify({
                "success": False,
                "message": "Usuario no encontrado."
            }), 404
        
        from_serial = usuario.get("fromSerial")
        to_serial = usuario.get("toSerial")
        
        if not from_serial or not to_serial:
            return jsonify({
                "success": False,
                "message": "El usuario no tiene un rango de tablas asignado."
            }), 400
        
        # Extraer números de los seriales (ej: "CARD001" -> 1)
        def extraer_numero(serial):
            match = re.search(r'\d+', serial)
            return int(match.group()) if match else 0
        
        from_num = extraer_numero(from_serial)
        to_num = extraer_numero(to_serial)
        
        if from_num <= 0 or to_num <= 0:
            return jsonify({
                "success": False,
                "message": "No se pudo extraer los números de los seriales del usuario."
            }), 400
        
        # Obtener todas las tablas del rango del usuario, ordenadas
        tablas_rango = list(mongo_collection_tables.find({
            "serial": {"$regex": f"^CARD", "$options": "i"}
        }).sort("serial", 1))
        
        # Filtrar solo las del rango del usuario
        tablas_usuario = []
        for tabla in tablas_rango:
            num = extraer_numero(tabla.get("serial", ""))
            if from_num <= to_num:
                # Rango ascendente
                if from_num <= num <= to_num:
                    tablas_usuario.append(tabla)
            else:
                # Rango descendente
                if to_num <= num <= from_num:
                    tablas_usuario.append(tabla)
        
        if not tablas_usuario:
            return jsonify({
                "success": False,
                "message": "No hay tablas en el rango asignado al usuario."
            }), 400
        
        # Encontrar tablas disponibles en orden consecutivo
        tablas_disponibles = []
        for tabla in tablas_usuario:
            # Si no está asignada a nadie
            if not tabla.get("stateAsigned", False):
                tablas_disponibles.append(tabla)
            
            # Si ya encontramos suficientes, detener
            if len(tablas_disponibles) >= cantidad_tablas:
                break
        
        # Verificar que hay suficientes tablas disponibles
        if len(tablas_disponibles) < cantidad_tablas:
            return jsonify({
                "success": False,
                "message": f"No hay suficientes tablas disponibles. Se encontraron {len(tablas_disponibles)} de {cantidad_tablas} solicitadas."
            }), 400
        
        # Extraer solo los seriales
        seriales_consecutivos = [t["serial"] for t in tablas_disponibles]
        
        return jsonify({
            "success": True,
            "message": "Tablas disponibles obtenidas correctamente.",
            "tablas_consecutivas": seriales_consecutivos,
            "cantidad": len(seriales_consecutivos)
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al obtener tablas consecutivas."
        }), 500

# -------------------------
# ENDPOINT PARA OBTENER TABLAS DE UN PARTICIPANTE
@app.route('/api/obtenerTablasParticipante/<string:participante_id>', methods=['GET'])
def obtener_tablas_participante(participante_id):
    """
    Recupera las tablas asignadas a un participante por su ID.
    Devuelve el serial y la matriz de cada tabla asignada.
    """
    try:
        # Buscar participante por ID
        participante = mongo_collection_participantes.find_one({"_id": ObjectId(participante_id)})
        if not participante:
            return jsonify({
                "success": False,
                "message": "Participante no encontrado."
            }), 404

        # Verificar si el participante tiene tablas asignadas
        if "tablas" not in participante or not participante["tablas"]:
            return jsonify({
                "success": True,
                "message": "El participante no tiene tablas asignadas.",
                "tablas": []
            })

        # Obtener los IDs de las tablas asignadas (son ObjectIds)
        tablas_ids = participante["tablas"]

        # Buscar las tablas por _id en la colección 'tablas'
        tablas_encontradas = list(mongo_collection_tables.find({"_id": {"$in": tablas_ids}}))

        # Si no hay tablas, devolver lista vacía (no es error)
        if not tablas_encontradas:
            return jsonify({
                "success": True,
                "message": "El participante no tiene tablas asignadas.",
                "tablas": []
            })

        # Formatear la respuesta
        resultado = []
        for tabla in tablas_encontradas:
            resultado.append({
                "_id": str(tabla["_id"]),
                "serial": tabla.get("serial", ""),
                "matrix": tabla.get("matrix", []),
                "won": tabla.get("won", False),
                "stateAsigned": tabla.get("stateAsigned", False)
            })

        return jsonify({
            "success": True,
            "message": "Tablas recuperadas correctamente.",
            "tablas": resultado
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al recuperar las tablas del participante."
        }), 500


# ENDPOINT: Buscar participante por cédula y devolver info + tablas asignadas
@app.route('/api/participante/cedula/<string:cedula>', methods=['GET'])
def participante_por_cedula(cedula):
    """
    Busca un participante por su número de cédula y devuelve nombre, apellido, curso, nivel y tablas asignadas.
    """
    try:
        participante = mongo_collection_participantes.find_one({"cedula": cedula})
        if not participante:
            return jsonify({"success": False, "message": f"Participante con cédula {cedula} no encontrado."}), 404

        # Campos de interés
        participante_info = {
            "_id": str(participante.get("_id")),
            "nombre": participante.get("nombre", ""),
            "apellido": participante.get("apellido", ""),
            "cedula": participante.get("cedula", ""),
            "nivelCurso": participante.get("nivelCurso", ""),
            "paralelo": participante.get("paralelo", ""),
            "tablas": []
        }

        tablas_ids = participante.get("tablas", [])
        if tablas_ids:
            tablas_encontradas = list(mongo_collection_tables.find({"_id": {"$in": tablas_ids}}))
            for tabla in tablas_encontradas:
                participante_info["tablas"].append({
                    "_id": str(tabla.get("_id")),
                    "serial": tabla.get("serial", ""),
                    "matrix": tabla.get("matrix", []),
                    "won": tabla.get("won", False),
                    "stateAsigned": tabla.get("stateAsigned", False)
                })

        return jsonify({"success": True, "participante": participante_info}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e), "message": "Error al buscar participante por cédula."}), 500


# ENDPOINT: Descargar PDF con las tablas asignadas a un participante (por cédula)
@app.route('/api/participante/cedula/<string:cedula>/tablas_pdf', methods=['GET'])
def participante_tablas_pdf(cedula):
    """
    Genera y devuelve un PDF con las tablas asignadas al participante identificado por cédula.
    """
    try:
        participante = mongo_collection_participantes.find_one({"cedula": cedula})
        if not participante:
            return jsonify({"success": False, "message": f"Participante con cédula {cedula} no encontrado."}), 404

        tablas_ids = participante.get("tablas", [])
        if not tablas_ids:
            return jsonify({"success": True, "message": "El participante no tiene tablas asignadas.", "tablas": []}), 200

        tablas_encontradas = list(mongo_collection_tables.find({"_id": {"$in": tablas_ids}}))

        # Generar PDF en memoria
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        PAGE_WIDTH, PAGE_HEIGHT = letter
        MARGIN_X = 0.5 * inch
        MARGIN_Y = 0.5 * inch
        CARD_WIDTH = (PAGE_WIDTH - 2*MARGIN_X) / 2
        CARD_HEIGHT = (PAGE_HEIGHT - 2*MARGIN_Y) / 2
        CARDS_PER_PAGE = 4

        for idx, tabla in enumerate(tablas_encontradas):
            matrix = tabla.get("matrix", [[None]*5 for _ in range(5)])
            serial = tabla.get("serial", "")

            page_pos = idx % CARDS_PER_PAGE
            row = page_pos // 2
            col = page_pos % 2
            x = MARGIN_X + col*CARD_WIDTH
            y = PAGE_HEIGHT - MARGIN_Y - (row+1)*CARD_HEIGHT

            # Título y serial
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(x + CARD_WIDTH/2, y + CARD_HEIGHT - 15, "BINGO UETS")
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(x + CARD_WIDTH/2, y + CARD_HEIGHT - 30, serial)

            grid_top = y + CARD_HEIGHT - 55
            grid_left = x + 10
            cell_w = (CARD_WIDTH - 20) / 5
            cell_h = (CARD_HEIGHT - 60) / 6

            c.setFont("Helvetica-Bold", 10)
            for i, L in enumerate(["B","I","N","G","O"]):
                c.drawCentredString(grid_left + i*cell_w + cell_w/2, grid_top, L)

            extra_space = 15
            c.setFont("Helvetica", 8)
            for r in range(5):
                for col2 in range(5):
                    left = grid_left + col2*cell_w
                    top = grid_top - extra_space - (r+1)*cell_h
                    c.rect(left, top, cell_w, cell_h)
                    val = matrix[r][col2]
                    txt = str(val) if val is not None else " "
                    c.drawCentredString(left + cell_w/2, top + cell_h/2 - 3, txt)

            if page_pos == CARDS_PER_PAGE-1 or idx == len(tablas_encontradas)-1:
                c.showPage()

        c.save()
        buffer.seek(0)

        filename = f"tablas_{cedula}.pdf"
        return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({"success": False, "error": str(e), "message": "Error generando PDF de tablas."}), 500


# ENDPOINT PARA ELIMINAR LA ASIGNACIÓN DE UNA TABLA A UN PARTICIPANTE
@app.route('/api/eliminarTablaAsignada', methods=['POST'])
def eliminar_tabla_asignada():
    """
    Elimina la asignación de una tabla de un participante.
    Cambia el estado stateAsigned a False en la colección de tablas.
    
    Request JSON:
    {
        "participante_id": "<id del participante>",
        "serial": "CARD00001"
    }
    """
    try:
        data = request.get_json(silent=True) or {}

        participante_id = data.get("participante_id")
        serial = data.get("serial")

        if not participante_id or not serial:
            return jsonify({
                "success": False,
                "message": "Se requieren 'participante_id' y 'serial'."
            }), 400

        # Verificar que el participante exista
        participante = mongo_collection_participantes.find_one({"_id": ObjectId(participante_id)})
        if not participante:
            return jsonify({
                "success": False,
                "message": "Participante no encontrado."
            }), 404

        # Verificar que el serial esté asignado al participante
        if "tablas" not in participante or serial not in participante["tablas"]:
            return jsonify({
                "success": False,
                "message": f"La tabla {serial} no está asignada a este participante."
            }), 400

        # Eliminar el serial de la lista de tablas del participante
        mongo_collection_participantes.update_one(
            {"_id": ObjectId(participante_id)},
            {"$pull": {"tablas": serial}}
        )

        # Actualizar la tabla para marcarla como no asignada
        resultado_tabla = mongo_collection_tables.update_one(
            {"serial": serial},
            {"$set": {"stateAsigned": False}}
        )

        if resultado_tabla.modified_count == 0:
            return jsonify({
                "success": False,
                "message": f"No se encontró o actualizó la tabla con serial {serial}."
            }), 404

        return jsonify({
            "success": True,
            "message": f"La tabla {serial} fue removida correctamente del participante y su estado actualizado."
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al eliminar la tabla asignada."
        }), 500




# -------------------------
# ENDPOINT PARA GENERAR USUARIOS ADMINISTRADORES
@app.route('/api/users/announcer', methods=['POST'])
def create_announcer():
    data = request.get_json()

    # Si se envía una lista de animadores
    if isinstance(data, list):
        resultados = []
        for item in data:
            nombres_completos = item.get('profesor') or item.get('tutor')
            curso = item.get('curso')
            especialidad = item.get('especialidad')
            nivel = item.get('nivel')
            paralelo = item.get('paralelo')

            if not all([nombres_completos, curso, especialidad, nivel, paralelo]):
                continue  # O puedes retornar error

            partes = nombres_completos.strip().split()
            iniciales = ''.join([p[0].upper() for p in partes])
            password_plano = f"{iniciales}2025"
            password_hash = generate_password_hash(password_plano)

            nuevo_usuario = {
                "usuario": iniciales.upper(),
                "nombres_completos": nombres_completos,
                "curso": curso,
                "especialidad": especialidad,
                "nivel": nivel,
                "paralelo": paralelo,
                "tipo_usuario": 1,
                "password": password_hash
            }

            mongo_collection_users.insert_one(nuevo_usuario)

            resultados.append({
                "nombres_completos": nombres_completos,
                "USUARIO": iniciales.upper(),
                "password_generado": password_plano
            })

        return jsonify({
            "message": "Usuarios anunciadores creados correctamente",
            "usuarios_creados": resultados
        }), 201

    else:
        return jsonify({"error": "Formato JSON no válido"}), 400

# -------------------------

# ENPOINT PARA LOGEAR
@app.route('/api/login', methods=['POST'])
def login_user():
    data = request.get_json()

    usuario = data.get('usuario').upper()
    password = data.get('password')

    if not usuario or not password:
        return jsonify({"error": "Debe ingresar usuario y contraseña"}), 400

    # Buscar usuario por campo 'usuario'
    user = mongo_collection_users.find_one({"usuario": usuario})

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    # Verificar la contraseña hasheada
    if not check_password_hash(user['password'], password):
        return jsonify({"error": "Contraseña incorrecta"}), 401

    # Login exitoso
    return jsonify({
        "message": "Inicio de sesión exitoso",
        "usuario": {
            "id": str(user["_id"]),
            "usuario": user.get("usuario"),
            "nombres": user.get("nombres_completos"),
            "tipo_usuario": user.get("tipo_usuario"),
            "curso": user.get("curso"),
            "especialidad": user.get("especialidad"),
            "nivel": user.get("nivel"),
            "paralelo": user.get("paralelo")
        }
    }), 200


# -------------------------
# ENDPOINT PARA VALIDAR Y CORREGIR TABLAS DE UN USUARIO
# -------------------------
@app.route('/api/validar-tablas/<usuario_id>', methods=['GET', 'POST'])
def validar_tablas_usuario(usuario_id):
    """
    Valida y opcionalmente corrige los contadores de tablas asignadas para un usuario.
    
    GET: Solo valida sin corregir
    POST: Valida y corrige si hay discrepancias
    
    Retorna:
    - tablas_reales_asignadas: número de tablas realmente asignadas
    - used_tables_bd: valor actual en la BD
    - diferencia: diferencia entre lo real y lo reportado
    - corregido: si fue corregido (solo en POST)
    """
    try:
        resultado = validar_y_corregir_tablas_usuario(usuario_id)
        
        if "error" in resultado:
            return jsonify({"success": False, "error": resultado["error"]}), 400
        
        return jsonify(resultado), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al validar tablas del usuario"
        }), 500


# -------------------------
# ENDPOINT PARA OBTENER LISTA DE PARTIPICIPANTES POR ANIMADOR
def serialize_mongo_doc(doc):
    """Convierte ObjectIds a strings en un documento MongoDB"""
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, list):
                result[key] = [str(v) if isinstance(v, ObjectId) else v for v in value]
            elif isinstance(value, dict):
                result[key] = serialize_mongo_doc(value)
            else:
                result[key] = value
        return result
    return doc

@app.route('/api/participantes/por-usuario/<usuario_id>', methods=['GET'])
def participantes_por_usuario_con_info(usuario_id):
    try:
        try:
            usuario_obj_id = ObjectId(usuario_id)
        except Exception:
            return jsonify({"success": False, "message": "El ID del usuario no es válido."}), 400

        usuario_doc = mongo_collection_users.find_one({"_id": usuario_obj_id}, {"password": 0})
        if not usuario_doc:
            return jsonify({"success": False, "message": "Usuario no encontrado."}), 404

        # Convertir TODO el documento de usuario
        usuario_doc = serialize_mongo_doc(usuario_doc)
        usuario_doc["_id"] = str(usuario_doc["_id"])

        # Verificar si el usuario es administrador (tipo_usuario = 0)
        tipo_usuario_val = safe_int(usuario_doc.get("tipo_usuario"), 1)
        es_admin = (tipo_usuario_val == 0)
        print(f"[DEBUG] tipo_usuario: {tipo_usuario_val}, es_admin: {es_admin}")
        # DEBUG: Log para verificar
        print(f"[DEBUG] Usuario ID: {usuario_id}, tipo_usuario: {tipo_usuario_val}, es_admin: {es_admin}")

        # Si es admin, obtener TODOS los participantes; si no, solo los del usuario
        if es_admin:
            print(f"[DEBUG] Obteniendo TODOS los participantes (admin)")
            # Materializar el cursor a lista para evitar problemas de agotamiento
            participantes_list = list(mongo_collection_participantes.find({}))
            print(f"[DEBUG] Documentos encontrados en BD: {len(participantes_list)}")
        else:
            print(f"[DEBUG] Obteniendo participantes solo del usuario: {usuario_obj_id}")
            participantes_list = list(mongo_collection_participantes.find(
                {"registrado_por": usuario_obj_id}
            ))
            print(f"[DEBUG] Documentos encontrados en BD: {len(participantes_list)}")

        participantes = []
        for p in participantes_list:
            p_serialized = serialize_mongo_doc(p)
            p_serialized["_id"] = str(p_serialized["_id"])
            participantes.append(p_serialized)

        print(f"[DEBUG] Total de participantes serializados: {len(participantes)}")

        return jsonify({
            "success": True,
            "usuario": usuario_doc,
            "participantes": participantes,
            "es_admin": es_admin,
            "tipo_usuario": tipo_usuario_val,
            "total_participantes": len(participantes)
        }), 200

    except Exception as e:
        print(f"[ERROR] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al obtener participantes por usuario"
        }), 500


# -------------------------
# ENDPOINT PARA OBTENER TODOS LOS PARTICIPANTES (SOLO ADMIN)
# -------------------------
@app.route('/api/participantes/todos/admin', methods=['GET'])
def obtener_todos_participantes_admin():
    """
    Obtiene TODOS los participantes registrados en el sistema.
    Solo debe ser accesible para administradores.
    
    Query params:
    - usuario_id: ID del usuario administrador (para validación)
    """
    try:
        usuario_id = request.args.get('usuario_id')
        
        # Si se proporciona usuario_id, validar que sea admin
        if usuario_id:
            try:
                usuario_obj_id = ObjectId(usuario_id)
                usuario = mongo_collection_users.find_one({"_id": usuario_obj_id}, {"password": 0})
                if not usuario:
                    return jsonify({"success": False, "message": "Usuario no encontrado."}), 404
                
                # Verificar que sea admin
                if safe_int(usuario.get("tipo_usuario"), 1) != 0:
                    return jsonify({
                        "success": False,
                        "message": "Acceso denegado. Solo administradores pueden ver todos los participantes."
                    }), 403
            except:
                return jsonify({"success": False, "message": "ID de usuario inválido."}), 400
        
        # Obtener TODOS los participantes
        participantes_cursor = mongo_collection_participantes.find({})
        
        participantes = []
        for p in participantes_cursor:
            p = serialize_mongo_doc(p)
            p["_id"] = str(p["_id"])
            participantes.append(p)
        
        return jsonify({
            "success": True,
            "participantes": participantes,
            "total_participantes": len(participantes)
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al obtener todos los participantes."
        }), 500


# -------------------------
# ENDPOINT PARA ELIMINAR PARTICIPANTE POR ANIMADOR
@app.route('/api/participante/<participante_id>/<tipo_usuario>', methods=['DELETE'])
def eliminar_participante(participante_id, tipo_usuario):
    try:
        data = request.get_json(silent=True) or {}
        usuario_id = data.get("usuario_id")

        if not usuario_id:
            return jsonify({"success": False, "message": "Debe proporcionar el ID del usuario."}), 400

        try:
            participante_obj_id = ObjectId(participante_id)
            usuario_obj_id = ObjectId(usuario_id)
        except Exception:
            return jsonify({"success": False, "message": "ID de usuario o participante inválido."}), 400

        # Buscar participante
        participante = mongo_collection_participantes.find_one({"_id": participante_obj_id})
        if not participante:
            return jsonify({"success": False, "message": "Participante no encontrado."}), 404

        # Verificar si pertenece al usuario (excepto admin tipo 0)
        if str(participante.get("registrado_por")) != str(usuario_obj_id) and tipo_usuario != '0':
            return jsonify({
                "success": False,
                "message": "No tiene permiso para eliminar este participante."
            }), 403

        # TABLAS ASIGNADAS
        tablas = participante.get("tablas", [])
        num_tablas = len(tablas)

        # Convertir a ObjectId las tablas
        tablas_obj_ids = []
        for tid in tablas:
            try:
                tablas_obj_ids.append(ObjectId(tid))
            except:
                pass

        # 1️⃣ LIBERAR TABLAS DEL PARTICIPANTE
        if tablas_obj_ids:
            mongo_collection_tables.update_many(
                {"_id": {"$in": tablas_obj_ids}},
                {"$set": {"stateAsigned": False}}
            )

        # 2️⃣ RESTAR USED TABLES AL USUARIO REGISTRADOR
        mongo_collection_users.update_one(
            {"_id": participante.get("registrado_por")},
            {"$inc": {"usedTables": -num_tablas}}
        )

        # 3️⃣ ELIMINAR PARTICIPANTE
        mongo_collection_participantes.delete_one({"_id": participante_obj_id})

        return jsonify({
            "success": True,
            "message": "Participante eliminado correctamente. Tablas liberadas.",
            "tablas_liberadas": num_tablas
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al intentar eliminar el participante."
        }), 500


# -------------------------
# ENDPOINT PARA BORRAR UNA TABLA DE UN PARTICIPANTE POR USUARIO 
@app.route('/api/participante/<participante_id>/tabla/<tabla_id>/<tipo_usuario>', methods=['DELETE'])
def eliminar_tabla_de_participante(participante_id, tabla_id, tipo_usuario):
    try:
        data = request.get_json(silent=True) or {}
        usuario_id = data.get("usuario_id")

        if not usuario_id:
            return jsonify({"success": False, "message": "Debe proporcionar el ID del usuario."}), 400

        try:
            participante_obj_id = ObjectId(participante_id)
            tabla_obj_id = ObjectId(tabla_id)
            usuario_obj_id = ObjectId(usuario_id)
        except Exception:
            return jsonify({
                "success": False,
                "message": "ID de participante, tabla o usuario inválido."
            }), 400

        participante = mongo_collection_participantes.find_one({"_id": participante_obj_id})
        if not participante:
            return jsonify({"success": False, "message": "Participante no encontrado."}), 404

        # Validar permisos
        if str(participante.get("registrado_por")) != str(usuario_obj_id) and tipo_usuario != '0':
            return jsonify({
                "success": False,
                "message": "No tiene permiso para modificar este participante."
            }), 403

        # Verificar si la tabla está realmente asignada
        if tabla_obj_id not in [ObjectId(t) for t in participante.get("tablas", [])]:
            return jsonify({
                "success": False,
                "message": "La tabla no pertenece a este participante."
            }), 404

        # 1️⃣ QUITAR TABLA DEL PARTICIPANTE
        mongo_collection_participantes.update_one(
            {"_id": participante_obj_id},
            {"$pull": {"tablas": tabla_obj_id}}
        )

        # 2️⃣ MARCAR TABLA COMO DESASIGNADA
        mongo_collection_tables.update_one(
            {"_id": tabla_obj_id},
            {"$set": {"stateAsigned": False}}
        )

        # 3️⃣ RESTAR SOLO 1 TABLA AL USUARIO
        mongo_collection_users.update_one(
            {"_id": participante.get("registrado_por")},
            {"$inc": {"usedTables": -1}}
        )

        return jsonify({
            "success": True,
            "message": "Tabla eliminada correctamente del participante."
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al eliminar la tabla del participante."
        }), 500

# -------------------------
# ENDPOINT PARA OBTENER LISTA DE PARTICIPANTES
# -------------------------
@app.route('/api/participantes', methods=['GET'])
def obtener_participantes():
    """
    Obtiene la lista de participantes.
    Si el usuario es tipo 0, obtiene todos los participantes.
    Si no es tipo 0, obtiene solo los participantes registrados por ese usuario.
    
    Query params:
    - usuario_id: ID del usuario (opcional, se puede obtener del header o query)
    - tipo_usuario: Tipo de usuario (0 = admin, otros = animador)
    """
    try:
        usuario_id = request.args.get('usuario_id')
        tipo_usuario = request.args.get('tipo_usuario')
        
        # Si es tipo 0, obtener todos los participantes
        if tipo_usuario and (tipo_usuario == '0' or tipo_usuario == 0):
            participantes = list(mongo_collection_participantes.find({}))
        elif usuario_id:
            # Obtener solo participantes del usuario
            try:
                usuario_obj_id = ObjectId(usuario_id)
                participantes = list(mongo_collection_participantes.find({"registrado_por": usuario_obj_id}))
            except:
                return jsonify({"success": False, "message": "ID de usuario inválido."}), 400
        else:
            # Si no se especifica, obtener todos (para tipo 0)
            participantes = list(mongo_collection_participantes.find({}))
        
        # Convertir ObjectIds a strings
        for p in participantes:
            p["_id"] = str(p["_id"])
            if isinstance(p.get("registrado_por"), ObjectId):
                p["registrado_por"] = str(p["registrado_por"])
            # Convertir tablas ObjectId a strings
            tablas = p.get("tablas", [])
            p["tablas"] = [str(t) if isinstance(t, ObjectId) else t for t in tablas]
        
        return jsonify({
            "success": True,
            "participantes": participantes,
            "count": len(participantes)
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al obtener participantes."
        }), 500


# -------------------------
# ENDPOINT PARA OBTENER TABLAS DISPONIBLES
# -------------------------
@app.route('/api/tablas', methods=['GET'])
def obtener_tablas():
    """
    Obtiene las tablas disponibles.
    Query params:
    - disponible: true/false - filtrar por disponibilidad
    - serial: buscar por serial
    - search: buscar por serial o participante
    """
    try:
        disponible = request.args.get('disponible')
        serial = request.args.get('serial')
        search = request.args.get('search', '').strip()
        
        query = {}
        
        if disponible == 'true':
            query["stateAsigned"] = False
        elif disponible == 'false':
            query["stateAsigned"] = True
            
        if serial:
            query["serial"] = {"$regex": serial, "$options": "i"}
        
        tablas = list(mongo_collection_tables.find(query))
        
        # Si hay búsqueda, filtrar también por participante
        if search:
            # Buscar participantes que coincidan
            participantes = list(mongo_collection_participantes.find({
                "$or": [
                    {"nombre": {"$regex": search, "$options": "i"}},
                    {"cedula": {"$regex": search, "$options": "i"}},
                ]
            }))
            participante_ids = [p["_id"] for p in participantes]
            
            # Filtrar tablas que coincidan con serial o estén asignadas a participantes encontrados
            tablas_filtradas = []
            for tabla in tablas:
                if search.lower() in tabla.get("serial", "").lower():
                    tablas_filtradas.append(tabla)
                elif tabla.get("_id") in participante_ids or any(tabla.get("_id") in p.get("tablas", []) for p in participantes):
                    tablas_filtradas.append(tabla)
            tablas = tablas_filtradas
        
        # Convertir ObjectIds y agregar información de participante
        resultado = []
        for tabla in tablas:
            tabla_dict = {
                "_id": str(tabla["_id"]),
                "serial": tabla.get("serial", ""),
                "matrix": tabla.get("matrix", []),
                "won": tabla.get("won", False),
                "stateAsigned": tabla.get("stateAsigned", False),
                "timestamp": tabla.get("timestamp", 0)
            }
            
            # Buscar participante asignado
            if tabla.get("stateAsigned"):
                participante = mongo_collection_participantes.find_one({"tablas": tabla["_id"]})
                if participante:
                    tabla_dict["participante"] = {
                        "_id": str(participante["_id"]),
                        "nombre": participante.get("nombre", ""),
                        "apellido": participante.get("apellido", ""),
                        "cedula": participante.get("cedula", ""),
                        "nivelCurso": participante.get("nivelCurso", ""),
                        "paralelo": participante.get("paralelo", "")
                    }
            
            resultado.append(tabla_dict)
        
        return jsonify({
            "success": True,
            "tablas": resultado,
            "count": len(resultado)
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al obtener tablas."
        }), 500

# -------------------------
# ENDPOINT PARA OBTENER UNA TABLA ESPECÍFICA
# -------------------------
@app.route('/api/tablas/<tabla_id>', methods=['GET'])
def obtener_tabla_especifica(tabla_id):
    """
    Obtiene una tabla específica por su ID.
    """
    try:
        try:
            tabla_obj_id = ObjectId(tabla_id)
        except:
            # Si no es ObjectId, buscar por serial
            tabla = mongo_collection_tables.find_one({"serial": tabla_id})
            if not tabla:
                return jsonify({"success": False, "message": "Tabla no encontrada."}), 404
        else:
            tabla = mongo_collection_tables.find_one({"_id": tabla_obj_id})
            if not tabla:
                return jsonify({"success": False, "message": "Tabla no encontrada."}), 404
        
        # Buscar participante asignado
        participante = None
        if tabla.get("stateAsigned"):
            participante = mongo_collection_participantes.find_one({"tablas": tabla["_id"]})
        
        resultado = {
            "_id": str(tabla["_id"]),
            "serial": tabla.get("serial", ""),
            "matrix": tabla.get("matrix", []),
            "won": tabla.get("won", False),
            "stateAsigned": tabla.get("stateAsigned", False),
            "timestamp": tabla.get("timestamp", 0)
        }
        
        if participante:
            resultado["participante"] = {
                "_id": str(participante["_id"]),
                "nombre": participante.get("nombre", ""),
                "apellido": participante.get("apellido", ""),
                "cedula": participante.get("cedula", ""),
                "nivelCurso": participante.get("nivelCurso", ""),
                "paralelo": participante.get("paralelo", "")
            }
        
        return jsonify({
            "success": True,
            "tabla": resultado
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al obtener la tabla."
        }), 500
    
# ==========================
#  ASIGNAR TABLAS A UN USUARIO (RESERVA)
# ==========================
@app.route('/api/users/<user_id>/assign_tables', methods=['POST'])
def assign_tables_to_user(user_id):
    try:
        data = request.get_json(silent=True) or {}
        # Verificar que el campo totalTables esté presente y no nulo
        if 'totalTables' not in data or data.get('totalTables') is None:
            return jsonify({"success": False, "message": "Se requiere totalTables en el body"}), 400
        total = safe_int(data.get('totalTables'), 0)
        # Se espera que el frontend envíe el id del usuario que hace la solicitud
        requesting_user_id = data.get('requesting_user_id')

        if not requesting_user_id:
            return jsonify({"success": False, "message": "Se requiere el ID del usuario solicitante"}), 400

        # Log de depuración pequeño para ver qué valor llegó
        print(f"[assign_tables] total received: {data.get('totalTables')}, parsed total: {total}, requesting_user_id: {requesting_user_id}")
        if total <= 0:
            return jsonify({"success": False, "message": "Debe ingresar una cantidad válida"}), 400

        # validar ObjectId
        try:
            user_obj_id = ObjectId(user_id)
        except:
            return jsonify({"success": False, "message": "ID de usuario inválido"}), 400

        user = mongo_collection_users.find_one({"_id": user_obj_id})
        if not user:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

        # Validar que el que solicita la reserva sea admin (tipo_usuario == 0)
        try:
            requesting_user_obj_id = ObjectId(requesting_user_id)
        except:
            return jsonify({"success": False, "message": "ID del usuario solicitante inválido"}), 400

        requesting_user = mongo_collection_users.find_one({"_id": requesting_user_obj_id})
        if not requesting_user:
            return jsonify({"success": False, "message": "Usuario solicitante no encontrado"}), 404

        # Solo admin puede auto-reservar tablas
        # Nota: esta validación se basa en el campo 'tipo_usuario' del documento del usuario.
        # En una implementación segura debería validarse con un token de sesión o JWT para evitar spoofing.
        if safe_int(requesting_user.get("tipo_usuario"), 1) != 0:
            return jsonify({"success": False, "message": "Solo usuario admin puede reservar tablas desde el último código."}), 403

        # Si ya tiene tablas asignadas previamente
        if user.get("totalTables"):
            return jsonify({
                "success": False,
                "message": "Este usuario ya tiene tablas reservadas."
            }), 400

        # Buscar tablas libres (sin asignar y sin reservar)
        # Si la reserva la solicita un admin, tomar las tablas desde el final (orden descendente)
        # Esto permite que el admin "autoasigne" sus tablas desde el último código disponible (ej CARD02000 → CARD01999 ...)
        sort_direction = -1 if safe_int(requesting_user.get("tipo_usuario"), 1) == 0 else 1

        available_cursor = mongo_collection_tables.find({
            "$or": [{"stateAsigned": False}, {"stateAsigned": {"$exists": False}}],
            "$or": [{"stateReserved": False}, {"stateReserved": {"$exists": False}}]
        }).sort("serial", sort_direction).limit(total)

        available = list(available_cursor)

        if len(available) < total:
            return jsonify({
                "success": False,
                "message": "No hay suficientes tablas disponibles."
            }), 400

        table_ids = [t["_id"] for t in available]
        from_serial = available[0]["serial"]
        to_serial = available[-1]["serial"]

        # Marcar tablas como reservadas
        mongo_collection_tables.update_many(
            {"_id": {"$in": table_ids}},
            {"$set": {
                "stateReserved": True,
                "reservedTo": user_obj_id
            }}
        )

        # Guardar info en Users
        mongo_collection_users.update_one(
            {"_id": user_obj_id},
            {"$set": {
                "totalTables": total,
                "usedTables": 0,
                "fromSerial": from_serial,
                "toSerial": to_serial,
                "reserved_table_ids": table_ids
            }}
        )

        return jsonify({
            "success": True,
            "message": "Tablas reservadas exitosamente",
            "from": from_serial,
            "to": to_serial
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500



# ==========================
#  REGISTRAR PARTICIPANTE AUTOMÁTICO (USA RESERVA)
# ==========================
@app.route('/api/registrarParticipanteAuto', methods=['POST'])
def registrar_participante_auto():
    try:
        data = request.get_json(silent=True) or {}

        nombre = data.get("nombre")
        apellido = data.get("apellido", "")
        cedula = data.get("cedula")
        celular = data.get("celular", "")
        registrado_por = data.get("registrado_por")
        cantidad = safe_int(data.get("cantidad_tablas"), 1)

        if not nombre or not cedula or not registrado_por:
            return jsonify({"success": False, "message": "Nombre, cédula y registrado_por son obligatorios"}), 400

        try:
            user_obj_id = ObjectId(registrado_por)
        except:
            return jsonify({"success": False, "message": "ID de usuario inválido"}), 400

        user = mongo_collection_users.find_one({"_id": user_obj_id})
        if not user:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

        total = safe_int(user.get("totalTables"), 0)
        used = safe_int(user.get("usedTables"), 0)
        reserved_ids = user.get("reserved_table_ids", [])

        remaining = total - used
        if remaining <= 0:
            return jsonify({"success": False, "message": "Ya no tienes tablas disponibles"}), 400

        if cantidad > remaining:
            return jsonify({"success": False, "message": f"Sólo quedan {remaining} tablas disponibles"}), 400

        # Obtener las tablas a asignar en orden
        assign_ids = reserved_ids[used: used + cantidad]

        # Validar que no estén asignadas ya
        for tid in assign_ids:
            tabla = mongo_collection_tables.find_one({"_id": tid})
            if tabla.get("stateAsigned"): # type: ignore
                return jsonify({
                    "success": False,
                    "message": f"La tabla {tabla['serial']} ya fue asignada previamente" # type: ignore
                }), 400

        # Insertar participante
        participante_data = {
            "nombre": nombre,
            "apellido": apellido,
            "cedula": cedula,
            "celular": celular,
            "tablas": assign_ids,
            "registrado_por": user_obj_id,
            "fecha_registro": datetime.now().isoformat()
        }

        insert_result = mongo_collection_participantes.insert_one(participante_data)
        participante_id = insert_result.inserted_id

        # Marcar tablas como asignadas
        mongo_collection_tables.update_many(
            {"_id": {"$in": assign_ids}},
            {"$set": {
                "stateAsigned": True,
                "assignedToParticipant": participante_id
            }}
        )

        # Incrementar usado
        mongo_collection_users.update_one(
            {"_id": user_obj_id},
            {"$inc": {"usedTables": cantidad}}
        )

        return jsonify({
            "success": True,
            "message": "Participante registrado correctamente",
            "participante_id": str(participante_id)
        }), 201

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# -------------------------
# ENDPOINT PARA AGREGAR TABLAS A UN PARTICIPANTE
# -------------------------
@app.route('/api/participante/<participante_id>/tablas/<tipo_usuario>', methods=['POST'])
def agregar_tablas_participante(participante_id, tipo_usuario):
    """
    Agrega tablas a un participante existente.
    JSON esperado:
    {
        "tablas": ["serial1", "serial2", ...] o ["ObjectId1", "ObjectId2", ...],
        "usuario_id": "ObjectId del usuario que realiza la acción"
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        tablas_seriales = data.get("tablas", [])
        usuario_id = data.get("usuario_id")
        
        if not tablas_seriales:
            return jsonify({"success": False, "message": "Debe proporcionar al menos una tabla."}), 400
        
        if not usuario_id:
            return jsonify({"success": False, "message": "Debe proporcionar el ID del usuario."}), 400
        
        try:
            participante_obj_id = ObjectId(participante_id)
            usuario_obj_id = ObjectId(usuario_id)
        except:
            return jsonify({"success": False, "message": "ID inválido."}), 400
        
        # Verificar que el participante existe y pertenece al usuario
        participante = mongo_collection_participantes.find_one({"_id": participante_obj_id})
        if not participante:
            return jsonify({"success": False, "message": "Participante no encontrado."}), 404
        
        if str(participante.get("registrado_por")) != str(usuario_obj_id) and tipo_usuario != '0':
            return jsonify({"success": False, "message": "No tiene permiso para modificar este participante."}), 403
        
        # Buscar tablas por serial o ObjectId
        tablas_obj_ids = []
        for t in tablas_seriales:
            # Intentar como ObjectId primero
            try:
                tablas_obj_ids.append(ObjectId(t))
            except:
                # Si no es ObjectId, buscar por serial
                tabla = mongo_collection_tables.find_one({"serial": t})
                if tabla:
                    tablas_obj_ids.append(tabla["_id"])
                else:
                    return jsonify({"success": False, "message": f"Tabla '{t}' no encontrada."}), 404
        
        # Verificar que las tablas existan y no estén asignadas
        tablas_existentes = list(mongo_collection_tables.find(
            {"_id": {"$in": tablas_obj_ids}},
            {"_id": 1, "stateAsigned": 1}
        ))
        
        if len(tablas_existentes) != len(tablas_obj_ids):
            return jsonify({"success": False, "message": "Una o más tablas no existen."}), 404
        
        # Verificar que no estén asignadas
        tablas_asignadas = [t for t in tablas_existentes if t.get("stateAsigned")]
        if tablas_asignadas:
            return jsonify({"success": False, "message": "Una o más tablas ya están asignadas."}), 400
        
        # Agregar tablas al participante
        mongo_collection_participantes.update_one(
            {"_id": participante_obj_id},
            {"$addToSet": {"tablas": {"$each": tablas_obj_ids}}}
        )
        
        # Marcar tablas como asignadas
        mongo_collection_tables.update_many(
            {"_id": {"$in": tablas_obj_ids}},
            {"$set": {"stateAsigned": True}}
        )
                # Calcular el total a pagar
        cantidad_tablas = len(tablas_obj_ids)
        pares = cantidad_tablas // 2
        sobrante = cantidad_tablas % 2
        total_pagar = pares * 5 + sobrante * 3

        # Actualizar el total del participante
        mongo_collection_participantes.update_one(
            {"_id": participante_obj_id},
            {"$inc": {"total_pagado": total_pagar}}
        )

        # Actualizar el total de ventas del usuario que registró el participante
        usuario_registro_id = participante.get("registrado_por")
        if usuario_registro_id:
            mongo_collection_users = mongo_db["Users"]
            mongo_collection_users.update_one(
                {"_id": usuario_registro_id},
                {"$inc": {"total_vendido": total_pagar}}
            )
        
        return jsonify({
            "success": True,
            "message": "Tablas agregadas correctamente."
        }), 200
        
    
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al agregar tablas."
        }), 500

# -------------------------
# ENDPOINT PARA OBTENER REPORTES
# -------------------------
from bson import ObjectId

@app.route('/api/reportes', methods=['GET'])
def obtener_reportes():
    """
    Reportes corregido:
    - total_vendido calculado por participante (según cantidad de tablas)
    - ventas_por_usuario usando nombres (no ObjectId)
    - usuario_top y grupo_top con nombre y total
    - conteo de participantes por nivelCurso, curso, paralelo, especialidad
    """
    try:
        # Totales generales
        total_tablas = mongo_collection_tables.count_documents({})
        tablas_ganadoras = mongo_collection_tables.count_documents({"won": True})
        total_participantes = mongo_collection_participantes.count_documents({})

        tablas_ganadoras_ids = [t["_id"] for t in mongo_collection_tables.find({"won": True}, {"_id": 1})]
        participantes_con_ganadores = mongo_collection_participantes.count_documents({
            "tablas": {"$in": tablas_ganadoras_ids}
        })

        tasa_ganadores = (tablas_ganadoras / total_tablas * 100) if total_tablas > 0 else 0

        # Recolectar participantes
        participantes = list(mongo_collection_participantes.find({}))

        # Recolectar todos los user_ids para consulta por lote
        user_obj_ids = set()
        for p in participantes:
            rp = p.get("registrado_por")
            if rp:
                try:
                    # rp puede ser ObjectId ya o string
                    uid = rp if isinstance(rp, ObjectId) else ObjectId(str(rp))
                    user_obj_ids.add(uid)
                except:
                    pass

        # Buscar usuarios por lote y crear mapa id -> nombre
        usuarios_map = {}
        if user_obj_ids:
            usuarios_cursor = mongo_collection_users.find({"_id": {"$in": list(user_obj_ids)}},
                                                         {"nombres_completos": 1, "usuario": 1, "curso":1, "especialidad":1, "nivel":1, "paralelo":1})
            for u in usuarios_cursor:
                usuarios_map[str(u["_id"])] = {
                    "nombre": u.get("nombres_completos") or u.get("usuario") or "Desconocido",
                    "usuario": u.get("usuario"),
                    "curso": u.get("curso"),
                    "especialidad": u.get("especialidad"),
                    "nivel": u.get("nivel"),
                    "paralelo": u.get("paralelo")
                }

        # Agregadores
        total_vendido = 0
        ventas_por_usuario = {}   # key: nombre_usuario, value: total $
        ventas_por_grupo = {}     # key: grupoAdetitss, value: total $
        conteo_por_nivel = {}     # key: nivelCurso, value: count participants
        conteo_por_curso = {}     # key: curso, value: count participants
        conteo_por_paralelo = {}  # key: paralelo, value: count participants
        conteo_por_especialidad = {} # key: especialidad, value: count participants

        for p in participantes:
            # cantidad de tablas asignadas
            tablas = p.get("tablas") or []
            # tablas puede contener ObjectIds; contar elemento por elemento
            num_tablas = len(tablas)

            # calcular total por la regla (pares $5, suelta $3)
            pares = num_tablas // 2
            resto = num_tablas % 2
            total_participante = pares * 5 + resto * 3 if num_tablas > 0 else 0

            # se puede saber el total vendido de cada grupo
            #total_vendido += total_participante

            total_vendido += num_tablas

            # obtener nombre del usuario registrador
            rp = p.get("registrado_por")
            nombre_usuario = "Desconocido"
            usuario_id_str = None
            try:
                if rp:
                    uid = rp if isinstance(rp, ObjectId) else ObjectId(str(rp))
                    usuario_id_str = str(uid)
                    nombre_usuario = usuarios_map.get(usuario_id_str, {}).get("nombre", nombre_usuario)
            except:
                nombre_usuario = "Desconocido"

            # ventas por usuario (usar nombre)
            ventas_por_usuario[nombre_usuario] = ventas_por_usuario.get(nombre_usuario, 0) + total_participante

            # ventas por grupo (campo en participante: "grupoAdetitss" según tus ejemplos)
            grupo = p.get("grupoAdetitss") or p.get("grupoAdetiss") or "Sin grupo"
            ventas_por_grupo[grupo] = ventas_por_grupo.get(grupo, 0) + total_participante

            # conteos de participantes (aquí contamos participantes, no la suma de tablas)
            nivel = p.get("nivelCurso") or usuarios_map.get(usuario_id_str, {}).get("nivel") or "Sin nivel"
            curso = p.get("curso") or usuarios_map.get(usuario_id_str, {}).get("curso") or "Sin curso"
            paralelo = p.get("paralelo") or usuarios_map.get(usuario_id_str, {}).get("paralelo") or "Sin paralelo"
            especialidad = p.get("especialidad") or usuarios_map.get(usuario_id_str, {}).get("especialidad") or "Sin especialidad"

            conteo_por_nivel[nivel] = conteo_por_nivel.get(nivel, 0) + 1
            conteo_por_curso[curso] = conteo_por_curso.get(curso, 0) + 1
            conteo_por_paralelo[paralelo] = conteo_por_paralelo.get(paralelo, 0) + 1
            conteo_por_especialidad[especialidad] = conteo_por_especialidad.get(especialidad, 0) + 1

        # determinar usuario_top (nombre y total) y su id si se quiere
        usuario_top = None
        if ventas_por_usuario:
            nombre_top = max(ventas_por_usuario.items(), key=lambda x: x[1])[0]
            total_top = ventas_por_usuario[nombre_top]
            # intentar buscar id por nombre en usuarios_map (puede haber nombres repetidos)
            usuario_id_encontrado = None
            for uid_str, udata in usuarios_map.items():
                if udata.get("nombre") == nombre_top:
                    usuario_id_encontrado = uid_str
                    break
            usuario_top = {
                "id": usuario_id_encontrado,
                "nombre": nombre_top,
                "total": total_top
            }

        # determinar grupo_top
        grupo_top = None
        if ventas_por_grupo:
            nombre_gt = max(ventas_por_grupo.items(), key=lambda x: x[1])[0]
            total_gt = ventas_por_grupo[nombre_gt]
            grupo_top = {"nombre": nombre_gt, "total": total_gt}

        # top por conteos
        def obtener_top(dic):
            if not dic:
                return None
            return max(dic.items(), key=lambda x: x[1])[0]

        top_nivel = obtener_top(conteo_por_nivel)
        top_curso = obtener_top(conteo_por_curso)
        top_paralelo = obtener_top(conteo_por_paralelo)
        top_especialidad = obtener_top(conteo_por_especialidad)

        # Respuesta final
        return jsonify({
            "success": True,
            "reportes": {
                "total_tablas": total_tablas,
                "tablas_ganadoras": tablas_ganadoras,
                "total_participantes": total_participantes,
                "participantes_con_ganadores": participantes_con_ganadores,
                "tasa_ganadores": round(tasa_ganadores, 2),
                "total_vendido": total_vendido,
                "ventas_por_usuario": ventas_por_usuario,           # nombres -> total
                "usuario_top": usuario_top,
                "ventas_por_grupo": ventas_por_grupo,
                "grupo_top": grupo_top,
                "conteo_por_nivel": conteo_por_nivel,
                "conteo_por_curso": conteo_por_curso,
                "conteo_por_paralelo": conteo_por_paralelo,
                "conteo_por_especialidad": conteo_por_especialidad,
                "top_nivel": top_nivel,
                "top_curso": top_curso,
                "top_paralelo": top_paralelo,
                "top_especialidad": top_especialidad
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al obtener reportes."
        }), 500

# -------------------------
# ENDPOINT PARA VALIDAR TABLA POR SERIAL
# -------------------------
@app.route('/api/validarTabla/<serial>', methods=['GET'])
def validar_tabla_serial(serial):
    """
    Valida si una tabla existe por su serial y si está disponible.
    """
    try:
        tabla = mongo_collection_tables.find_one({"serial": serial})
        
        if not tabla:
            return jsonify({
                "success": False,
                "message": f"Tabla con serial '{serial}' no encontrada."
            }), 404
        
        disponible = not tabla.get("stateAsigned", False)
        
        return jsonify({
            "success": True,
            "tabla": {
                "_id": str(tabla["_id"]),
                "serial": tabla.get("serial", ""),
                "disponible": disponible,
                "won": tabla.get("won", False)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al validar la tabla."
        }), 500

# ENDPOINT PARA SUBIR Y PROCESAR PDF
# -------------------------
# Endpoint /upload usando la extracción por coordenadas
# -------------------------
@app.route('/upload', methods=['POST'])
def upload_pdf():
    """
    Sube un PDF, extrae las matrices de bingo, valida duplicados,
    guarda los cartones en MongoDB y genera un archivo JSON con los resultados.
    """
    try:
        file = request.files.get('pdf')
        if not file:
            return jsonify({"error": "No se envió PDF"}), 400

        os.makedirs(json_dir, exist_ok=True)
        os.makedirs(upload_dir, exist_ok=True)

        timestamp = int(time.time())
        temp_pdf_path = os.path.join(upload_dir, f"tmp_upload_{timestamp}.pdf")
        file.save(temp_pdf_path)

        json_filename = f"bingo_cards_uploaded_{timestamp}.json"
        json_path = os.path.join(json_dir, json_filename)

        # ------------------------
        # 1️⃣ Procesar el PDF
        # ------------------------
        try:
            cards_data = extraer_matrices_pdf(temp_pdf_path, json_path)
        except Exception as e:
            try:
                os.remove(temp_pdf_path)
            except:
                pass
            return jsonify({"error": "Error al procesar PDF", "detail": str(e)}), 500

        try:
            os.remove(temp_pdf_path)
        except:
            pass

        # ------------------------
        # 2️⃣ Validar duplicados
        # ------------------------
        validacion = validar_duplicados(cards_data)
        repetidos_internos = {}

        for card in cards_data:
            nums = [n for row in card['matrix'] for n in row if n is not None]
            if len(nums) != len(set(nums)):
                repetidos_internos[card['serial']] = {
                    "nums": nums,
                    "duplicates": [n for n in set(nums) if nums.count(n) > 1]
                }

        # ------------------------
        # 3️⃣ Insertar o actualizar en MongoDB
        # ------------------------
        insertados = 0
        actualizados = 0

        for card in cards_data:
            try:
                result = mongo_collection_tables.update_one(
                    {"serial": card["serial"]},
                    {"$set": {
                        "serial": card["serial"],
                        "matrix": card["matrix"],
                        "timestamp": time.time(),
                        "won": False,
                        "stateAsigned": False
                    }},
                    upsert=True
                )
                if result.upserted_id is not None:
                    insertados += 1
                elif result.modified_count > 0:
                    actualizados += 1
            except Exception as e:
                print(f"❌ Error guardando serial {card.get('serial')}: {e}")

        # ------------------------
        # 4️⃣ Función auxiliar para evitar error JSON
        # ------------------------
        def stringify_keys(obj):
            """Convierte todas las claves no-string en cadenas para evitar TypeError al jsonify."""
            if isinstance(obj, dict):
                return {str(k): stringify_keys(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [stringify_keys(i) for i in obj]
            else:
                return obj

        cards_data = stringify_keys(cards_data)
        repetidos_internos = stringify_keys(repetidos_internos)
        validacion = stringify_keys(validacion)

        # ------------------------
        # 5️⃣ Guardar JSON final
        # ------------------------
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(cards_data, f, indent=2, ensure_ascii=False)

        # ------------------------
        # 6️⃣ Respuesta final
        # ------------------------
        return jsonify({
            "success": True,
            "cards": cards_data,
            "json_path": json_path,
            "total_cartones": validacion.get("total"),
            "cartones_unicos": validacion.get("unicos"),
            "cartones_duplicados": validacion.get("duplicados"),
            "duplicados_seriales": validacion.get("duplicados_seriales"),
            "repetidos_internos": repetidos_internos,
            "insertados_en_mongo": insertados,
            "actualizados_en_mongo": actualizados,
            "message": f"✅ Cartones procesados y guardados en MongoDB ({insertados} nuevos, {actualizados} actualizados)"
        }), 200

    except Exception as e:
        # Error general
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error inesperado al subir el PDF."
        }), 500
    
def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.endswith('.pdf'):
            pdf_path = arg
            output_json = "bingo_cards.json"
            cards_data = extraer_matrices_pdf(pdf_path, output_json)
            validacion = validar_duplicados(cards_data)
            print(f"Se extrajeron {validacion['total']} cartones.")
            print(f"Cartones únicos: {validacion['unicos']}")
            print(f"Cartones duplicados: {validacion['duplicados']}")
            if validacion['duplicados_seriales']:
                print("Cartones duplicados encontrados (seriales):")
                for serials in validacion['duplicados_seriales'].values():
                    print(serials)
            else:
                print("No se encontraron duplicados.")
            iniciar_bingo(output_json)
        elif arg.isdigit():
            num_cards = int(arg)
            # --- Generación SIN DUPLICADOS para CLI ---
            cards_list = []
            generated = set()
            for i in range(num_cards):
                while True:
                    card = generate_bingo_card()
                    signature = tuple(tuple(row) for row in card)

                    if signature not in generated:
                        generated.add(signature)
                        serial = f"CARD{str(i+1).zfill(5)}"
                        cards_list.append((serial, card))
                        break            
            ##cards_list = [(f"CARD{str(i+1).zfill(5)}", generate_bingo_card()) for i in range(num_cards)]
            cards_data = []
            for serial, matrix in cards_list:
                cards_data.append({"serial": serial, "matrix": matrix})
            output_json = "bingo_cards.json"
            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(cards_data, f, indent=2, ensure_ascii=False)
            validacion = validar_duplicados(cards_data)
            print(f"Se generaron {validacion['total']} cartones.")
            print(f"Cartones únicos: {validacion['unicos']}")
            print(f"Cartones duplicados: {validacion['duplicados']}")
            if validacion['duplicados_seriales']:
                print("Cartones duplicados encontrados (seriales):")
                for serials in validacion['duplicados_seriales'].values():
                    print(serials)
            else:
                print("No se encontraron duplicados.")
            iniciar_bingo(output_json)
        else:
            print("Argumento no reconocido. Usa un número de tablas o un PDF.")
    else:
        # Si no hay argumentos, reconstruir el JSON activo (solo tablas asignadas) y luego iniciar el servidor Flask
        try:
            # Llamar a la función reset() para crear el JSON activo desde la BD
            # reset() ya filtra por `stateAsigned = True` (ver modificación previa)
            try:
                reset()
            except Exception as e:
                print(f"Advertencia: fallo al reconstruir JSON inicial desde DB: {e}")
        finally:
            app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == '__main__':
    main()


# Stub para compatibilidad: iniciar_bingo puede ser llamada desde main cuando se ejecuta en modo CLI
def iniciar_bingo(json_path=None):
    """Stub simple para iniciar el juego de bingo desde CLI. Actualmente solo muestra información mínima.
    Esto evita errores si el script es invocado con argumentos en modo no servidor.
    """
    if json_path:
        print(f"Iniciando bingo con archivo: {json_path}")
    else:
        print("Iniciando bingo (sin archivo especificado)")
    # Implementación real puede lanzar la lógica del juego si se necesita.
    return None
