"""Réglages propres à ce poste (jamais publiés sur GitHub — voir .gitignore).

Permet de pointer la base SQLite vers un chemin réseau partagé (usage multi-postes)
sans jamais faire apparaître ce chemin interne dans le dépôt public.
"""
import json
import os

import config

SETTINGS_PATH = os.path.join(config.BASE_DIR, "settings.json")
DEFAULT_DB_PATH = os.path.join(config.BASE_DIR, "data", "gmao.db")


def _read():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def get_db_path():
    return _read().get("db_path") or DEFAULT_DB_PATH


def set_db_path(path):
    data = _read()
    data["db_path"] = path
    os.makedirs(os.path.dirname(SETTINGS_PATH) or ".", exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
