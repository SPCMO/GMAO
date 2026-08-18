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


DEFAULT_SMTP = {"smtp_host": "", "smtp_port": 587, "smtp_user": "", "smtp_password": ""}


def get_smtp_config():
    data = _read()
    return {k: data.get(k, v) for k, v in DEFAULT_SMTP.items()}


def set_smtp_config(smtp_host, smtp_port, smtp_user, smtp_password):
    data = _read()
    data["smtp_host"] = smtp_host
    data["smtp_port"] = smtp_port
    data["smtp_user"] = smtp_user
    if smtp_password:
        # Un champ mot de passe laissé vide dans le formulaire ne l'efface pas.
        data["smtp_password"] = smtp_password
    os.makedirs(os.path.dirname(SETTINGS_PATH) or ".", exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


DEFAULT_APPS_SCRIPT = {"apps_script_url": "", "apps_script_token": ""}


def get_apps_script_config():
    data = _read()
    return {k: data.get(k, v) for k, v in DEFAULT_APPS_SCRIPT.items()}


def set_apps_script_config(url, token):
    data = _read()
    data["apps_script_url"] = url
    if token:
        data["apps_script_token"] = token
    os.makedirs(os.path.dirname(SETTINGS_PATH) or ".", exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
