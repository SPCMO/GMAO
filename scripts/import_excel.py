"""Importe les équipements initiaux depuis le classeur Excel fourni par l'utilisateur.

Usage: venv/Scripts/python.exe scripts/import_excel.py <chemin_vers_bdd_gmao.xlsx>
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl
import config
from app.db import init_db, db_session, create_equipement


def main(xlsx_path):
    init_db()
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb.worksheets[0]  # "BDD temps réel"

    imported = 0
    with db_session() as conn:
        for row in ws.iter_rows(min_row=2, values_only=True):
            nom, _qr_eq, site, _qr_site, date_installation = row[:5]
            if not nom or not site or not date_installation:
                continue
            date_str = date_installation.date().isoformat() if hasattr(date_installation, "date") else str(date_installation)
            create_equipement(conn, nom, date_str, site, date_debut=date_str)
            imported += 1

    print(f"{imported} équipement(s) importé(s) dans {config.DB_PATH}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: import_excel.py <chemin_vers_bdd_gmao.xlsx>")
        sys.exit(1)
    main(sys.argv[1])
