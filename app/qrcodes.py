"""Génère les QR codes (pointant vers la fiche de chaque équipement) + une planche imprimable
(HTML, avec bouton d'impression) et un PDF téléchargeable.

La planche imprime, sous chaque QR code, le nom de l'équipement en clair : en cas
d'absence de réseau sur le terrain, l'agent identifie au moins le matériel visuellement.

Utilisé à la fois par le script CLI (scripts/generate_qrcodes.py, tous les équipements)
et par la route Flask de génération ciblée (sélection depuis le dashboard).
"""
import base64
import io
import os

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

import config
from app import db

SHEET_HEAD = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>Planche d'étiquettes GMAO</title>
<style>
  body {{ font-family: system-ui, sans-serif; }}
  .barre-actions {{ margin-bottom: 1rem; }}
  .barre-actions button, .barre-actions a {{
    display: inline-block; background: #14314f; color: #fff; padding: .5rem 1rem;
    border-radius: 6px; text-decoration: none; font-size: .9rem; border: none;
    cursor: pointer; font-family: inherit; margin-right: .5rem;
  }}
  .grille {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
  .etiquette {{ border: 1px dashed #999; padding: 10px; text-align: center; page-break-inside: avoid; }}
  .etiquette img {{ width: 140px; height: 140px; }}
  .etiquette .nom {{ font-weight: 700; margin-top: 4px; }}
  .etiquette .id {{ font-size: .7rem; color: #666; }}
  @media print {{ .etiquette {{ border: 1px solid #ccc; }} .barre-actions {{ display: none; }} }}
</style>
</head><body>
<h1>{titre}</h1>
<p>Une étiquette par équipement : à découper et coller sur le matériel.</p>
<div class="barre-actions">
  <a href="/">🏠 Accueil</a>
  <button onclick="window.print()">🖨️ Imprimer</button>
  <a href="{pdf_filename}">📄 Télécharger en PDF</a>
</div>
<div class="grille">
"""
SHEET_TAIL = "</div></body></html>"


def _get_equipements(conn, equipement_ids):
    if equipement_ids is None:
        return db.list_equipements(conn)
    return db.list_equipements_by_ids(conn, equipement_ids)


def _ensure_png(equipement):
    url = f"{config.FICHE_BASE_URL}/{equipement['id']}.html"
    img = qrcode.make(url, box_size=8, border=2)
    png_path = os.path.join(config.ETIQUETTES_DIR, f"{equipement['id']}.png")
    img.save(png_path)
    return png_path, img


def generate(equipement_ids=None):
    """Génère les PNG des QR codes + une planche imprimable HTML + un PDF.

    equipement_ids=None -> tous les équipements (planche_etiquettes.*).
    equipement_ids=[...] -> uniquement cette sélection (planche_selection.*).
    Retourne (nombre généré, chemin de la planche HTML, chemin du PDF).
    """
    os.makedirs(config.ETIQUETTES_DIR, exist_ok=True)
    suffixe = "etiquettes" if equipement_ids is None else "selection"
    titre = "Planche d'étiquettes — Matériel hydrométrique" if equipement_ids is None else "Planche d'étiquettes — Sélection"
    pdf_filename = f"planche_{suffixe}.pdf"
    sheet_parts = [SHEET_HEAD.format(titre=titre, pdf_filename=pdf_filename)]

    with db.db_session() as conn:
        equipements = _get_equipements(conn, equipement_ids)

        count = 0
        for e in equipements:
            png_path, img = _ensure_png(e)

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
            count += 1

    sheet_parts.append(SHEET_TAIL)
    html_filename = f"planche_{suffixe}.html"
    sheet_path = os.path.join(config.ETIQUETTES_DIR, html_filename)
    with open(sheet_path, "w", encoding="utf-8") as f:
        f.write("".join(sheet_parts))

    pdf_path = _generate_pdf(equipements, pdf_filename)

    return count, sheet_path, pdf_path


def _generate_pdf(equipements, pdf_filename):
    pdf_path = os.path.join(config.ETIQUETTES_DIR, pdf_filename)
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    margin = 15 * mm
    cols = 3
    cell_w = (width - 2 * margin) / cols
    cell_h = 55 * mm
    img_size = 35 * mm

    col = 0
    x = margin
    y = height - margin - cell_h

    for e in equipements:
        png_path = os.path.join(config.ETIQUETTES_DIR, f"{e['id']}.png")
        c.roundRect(x + 2 * mm, y, cell_w - 4 * mm, cell_h - 4 * mm, 3 * mm)
        img_x = x + (cell_w - img_size) / 2
        img_y = y + cell_h - 4 * mm - img_size - 4 * mm
        c.drawImage(png_path, img_x, img_y, width=img_size, height=img_size)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(x + cell_w / 2, img_y - 10, e["nom"])
        c.setFont("Helvetica", 6)
        c.drawCentredString(x + cell_w / 2, img_y - 20, e["id"])

        col += 1
        x += cell_w
        if col == cols:
            col = 0
            x = margin
            y -= cell_h
            if y < margin:
                c.showPage()
                y = height - margin - cell_h

    c.save()
    return pdf_path
