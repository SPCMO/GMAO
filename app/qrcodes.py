"""Génère les QR codes (pointant vers la fiche de chaque équipement) + une planche imprimable.

La planche imprime, sous chaque QR code, le nom de l'équipement en clair : en cas
d'absence de réseau sur le terrain, l'agent identifie au moins le matériel visuellement.

Utilisé à la fois par le script CLI (scripts/generate_qrcodes.py, tous les équipements)
et par la route Flask de génération ciblée (sélection depuis le dashboard).
"""
import base64
import io
import os

import qrcode

import config
from app import db

SHEET_HEAD = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>Planche d'étiquettes GMAO</title>
<style>
  body {{ font-family: system-ui, sans-serif; }}
  .grille {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
  .etiquette {{ border: 1px dashed #999; padding: 10px; text-align: center; page-break-inside: avoid; }}
  .etiquette img {{ width: 140px; height: 140px; }}
  .etiquette .nom {{ font-weight: 700; margin-top: 4px; }}
  .etiquette .id {{ font-size: .7rem; color: #666; }}
  @media print {{ .etiquette {{ border: 1px solid #ccc; }} }}
</style>
</head><body>
<h1>{titre}</h1>
<p>Une étiquette par équipement : à découper et coller sur le matériel.</p>
<div class="grille">
"""
SHEET_TAIL = "</div></body></html>"


def generate(equipement_ids=None):
    """Génère les PNG des QR codes + une planche imprimable.

    equipement_ids=None -> tous les équipements (planche_etiquettes.html).
    equipement_ids=[...] -> uniquement cette sélection (planche_selection.html).
    Retourne (nombre généré, chemin de la planche générée).
    """
    os.makedirs(config.ETIQUETTES_DIR, exist_ok=True)
    titre = "Planche d'étiquettes — Matériel hydrométrique" if equipement_ids is None else "Planche d'étiquettes — Sélection"
    sheet_parts = [SHEET_HEAD.format(titre=titre)]

    with db.db_session() as conn:
        if equipement_ids is None:
            equipements = db.list_equipements(conn)
        else:
            equipements = db.list_equipements_by_ids(conn, equipement_ids)

        count = 0
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
            count += 1

    sheet_parts.append(SHEET_TAIL)
    filename = "planche_etiquettes.html" if equipement_ids is None else "planche_selection.html"
    sheet_path = os.path.join(config.ETIQUETTES_DIR, filename)
    with open(sheet_path, "w", encoding="utf-8") as f:
        f.write("".join(sheet_parts))

    return count, sheet_path
