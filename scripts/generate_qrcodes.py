"""Génère les QR codes de tous les équipements + la planche imprimable complète.

Usage: venv/Scripts/python.exe scripts/generate_qrcodes.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from app.qrcodes import generate


def main():
    count, sheet_path = generate()
    print(f"{count} QR code(s) générés dans {config.ETIQUETTES_DIR}")
    print(f"Planche : {sheet_path}")


if __name__ == "__main__":
    main()
