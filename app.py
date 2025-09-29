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
import io
from reportlab.lib.units import inch
import os
import json
import sys
import time

# ==========================
# RUTAS
# ==========================
# json_dir = "/Users/paulogonzalez/Desktop/bingo uets/jsons"
json_dir = "./jsons"
# winners_dir = "/Users/paulogonzalez/Desktop/bingo uets/winners"
winners_dir = "./winners"
# upload_dir = "/Users/paulogonzalez/Desktop/bingo uets/upload"
upload_dir = "./upload"

# ==========================
# FUNCIONES
# ==========================

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

# --- Obtiene la infromacion del PDF subido y extrae en un JSON---
def extraer_matrices_pdf(pdf_path, output_json):
    serial_pattern = re.compile(r'CARD\d{5}')
    number_pattern = re.compile(r'\b\d+\b')
    cards_data = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            serials = serial_pattern.findall(text)
            numbers = [int(n) for n in number_pattern.findall(text)]
            for i, serial in enumerate(serials):
                card_numbers = numbers[i*24:(i+1)*24]
                matrix = []
                idx = 0
                for r in range(5):
                    row = []
                    for c in range(5):
                        if r==2 and c==2:
                            row.append(None)
                        else:
                            row.append(card_numbers[idx])
                            idx += 1
                    matrix.append(row)
                cards_data.append({"serial": serial, "matrix": matrix})
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(cards_data, f, indent=2, ensure_ascii=False)
    return cards_data

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


# ==========================
# JUEGO DE BINGO
# ==========================
app = Flask(__name__)

# ==========================
# ENDPOINTS
# ==========================

# Endpoint para marcar/desmarcar un número en todas las matrices
@app.route('/mark', methods=['POST'])
def mark_number():
    data = request.json
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
        if card['won']:
            ganadores.append(card['serial'])
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)
    return jsonify({'success': True, 'ganadores': ganadores})

# ENDPOINT PARA RUTAS DE RENDERIZADO
@app.route('/')
def index():
    return render_template('index.html')

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
        progreso.append({"serial": card["serial"], "aciertos": aciertos, "won": card["won"]})
    progreso.sort(key=lambda x: x["aciertos"], reverse=True)
    top3 = progreso[:3]
    ganadores = [p for p in progreso if p["won"]]
    return jsonify({"top3": top3, "ganadores": ganadores})

# ENDPOINT PARA GENERAR PDF DEL GANADOR
@app.route('/winner_pdf', methods=['POST'])
def winner_pdf():
    data = request.json
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
    files = [f for f in os.listdir(json_dir) if f.endswith('.json')]
    if not files:
        return jsonify({"success": False, "message": "No hay cartones"})
    files.sort(reverse=True)
    path = os.path.join(json_dir, files[0])
    with open(path, "r", encoding="utf-8") as f:
        cards = json.load(f)
    for card in cards:
        card["marks"] = [[False for _ in range(5)] for _ in range(5)]
        card["marks"][2][2] = True
        card["won"] = False
        card["aciertos"] = 0
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)
    return jsonify({"success": True, "message": "Juego reiniciado"})

# ENDPOINT PARA GENERAR CARTONES EN PDF
@app.route('/generate', methods=['POST'])
def generate_cards():
    data = request.json
    num_cards = int(data.get("num_cards", 1))
    PAGE_WIDTH, PAGE_HEIGHT = letter
    MARGIN_X = 0.5 * inch
    MARGIN_Y = 0.5 * inch
    CARD_WIDTH = (PAGE_WIDTH - 2*MARGIN_X) / 2
    CARD_HEIGHT = (PAGE_HEIGHT - 2*MARGIN_Y) / 2
    CARDS_PER_PAGE = 4
    os.makedirs(upload_dir, exist_ok=True)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    cards_list = [(f"CARD{str(i+1).zfill(5)}", generate_bingo_card()) for i in range(num_cards)]
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

# ENDPOINT PARA SUBIR Y PROCESAR PDF
# -------------------------
# Endpoint /upload usando la extracción por coordenadas
# -------------------------
@app.route('/upload', methods=['POST'])
def upload_pdf():
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

    # Validaciones finales
    validacion = validar_duplicados(cards_data)
    repetidos_internos = {}
    for card in cards_data:
        nums = [n for row in card['matrix'] for n in row if n is not None]
        if len(nums) != len(set(nums)):
            repetidos_internos[card['serial']] = {
                "nums": nums,
                "duplicates": [n for n in set(nums) if nums.count(n) > 1]
            }

    # Sobrescribir JSON final con resultado completo
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cards_data, f, indent=2, ensure_ascii=False)

    return jsonify({
        "cards": cards_data,
        "json_path": json_path,
        "total_cartones": validacion["total"],
        "cartones_unicos": validacion["unicos"],
        "cartones_duplicados": validacion["duplicados"],
        "duplicados_seriales": validacion["duplicados_seriales"],
        "repetidos_internos": repetidos_internos,
        "message": f"Cartones guardados en {json_path}"
    })

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
            cards_list = [(f"CARD{str(i+1).zfill(5)}", generate_bingo_card()) for i in range(num_cards)]
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
        # Si no hay argumentos, inicia el servidor Flask
        app.run(debug=True)

if __name__ == '__main__':
    main()
