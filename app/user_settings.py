"""ユーザーが選んだ画面設定をローカルファイルへ保存する。"""

import json
from pathlib import Path


SETTINGS_PATH = Path(__file__).parent.parent / "data" / "user_settings.json"


def load_user_settings() -> dict:
    """保存済み設定を返す。"""
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_user_settings(settings: dict) -> dict:
    """設定をアプリ内に永続保存する。"""
    SETTINGS_PATH.parent.mkdir(exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    return settings
