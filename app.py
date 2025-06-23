from flask import Flask, request, render_template, redirect, url_for, send_from_directory
import os
import threading
from pathlib import Path
import json

from main import (
    load_vendor_codes, wb_get_all, dump_filtered, choose_cat, get_attrs,
    build_ozon_card, ozon_import_batch, ozon_poll
)

UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            return "Файл не выбран", 400

        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filepath)

        threading.Thread(target=run_pipeline, args=(filepath,)).start()
        return redirect(url_for("index"))

    logs = sorted(Path(RESULTS_FOLDER).glob("ozon_result_*.json"), reverse=True)
    return render_template("index.html", logs=logs)

@app.route("/results/<path:filename>")
def download_result(filename):
    return send_from_directory(RESULTS_FOLDER, filename)

def run_pipeline(xlsx_path):
    vcodes = load_vendor_codes(xlsx_path)
    wb_all = wb_get_all()
    wb_need = dump_filtered(wb_all, vcodes)

    if not wb_need:
        return

    for idx in range(0, len(wb_need), 100):
        batch = wb_need[idx:idx+100]
        oz_cards = []
        for wb in batch:
            try:
                desc, typ = choose_cat(wb["title"])
                attrs = get_attrs(desc, typ)
                card = build_ozon_card(wb, desc, typ, attrs)
                oz_cards.append(card)
            except Exception as e:
                print(f"Ошибка в карточке: {e}")
                continue

        task = ozon_import_batch(oz_cards)
        result = ozon_poll(task)

        with open(Path(RESULTS_FOLDER) / f"ozon_result_{task}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
