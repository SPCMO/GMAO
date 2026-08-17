"""Génère un QR code par équipement (pointant vers sa fiche) + une planche imprimable.

La planche imprime, sous chaque QR code, le nom de l'équipement en clair : en cas
d'absence de réseau sur le terrain, l'agent identifie au moins le matériel visuellement.

Usage: venv/Scripts/python.exe scripts/generate_qrcodes.py
"""
import base64
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import qrcode

import config
from app import db

SHEET_HEAD = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>Planche d'étiquettes GMAO</title>
<style>
  body { font-family: system-ui, sans-serif; }
  .grille { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .etiquette { border: 1px dashed #999; padding: 10px; text-align: center; page-break-inside: avoid; }
  .etiquette img { width: 140px; height: 140px; }
  .etiquette .nom { font-weight: 700; margin-top: 4px; }
  .etiquette .id { font-size: .7rem; color: #666; }
  @media print { .etiquette { border: 1px solid #ccc; } }
</style>
</head><body>
<h1>Planche d'étiquettes — Matériel hydrométrique</h1>
<p>Une étiquette par équipement : à découper et coller sur le matériel.</p>
<div class="grille">
"""
SHEET_TAIL = "</div></body></html>"


def main():
    os.makedirs(config.ETIQUETTES_DIR, exist_ok=True)
    sheet_parts = [SHEET_HEAD]

    with db.db_session() as conn:
        equipements = db.list_equipements(conn)
        for e in equipements:
            url = f"{config.FICHE_BASE_URL}/{e['id']}.html"
            img = qrcode.make(url, box_size=8, border=2)

            png_path = os.path.join(config.ETIQUETTES_DIR, f"{e['id']}.png")
            img.save(png_path)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            sheet_parts.append(
                f'<div class="etiquette">'
                f'<img src="data:image/png;base64,{b64}" alt="QR {e["nom"]}">'
                f'<div class="nom">{e["nom"]}</div>'
                f'<div class="id">{e["id"]}</div>'
                f"</div>"
            )

    sheet_parts.append(SHEET_TAIL)
    sheet_path = os.path.join(config.ETIQUETTES_DIR, "planche_etiquettes.html")
    with open(sheet_path, "w", encoding="utf-8") as f:
        f.write("".join(sheet_parts))

    print(f"QR codes et planche générés dans {config.ETIQUETTES_DIR}")


if __name__ == "__main__":
    main()
