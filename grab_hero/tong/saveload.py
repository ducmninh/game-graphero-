"""Persistent save: gold + character upgrades + owned guns + owned pets.

Stored in ``save.json`` next to settings.py. Loaded once at game start and
written every time the player visits the Hub or completes a level.

The save is intentionally permissive: missing fields fall back to defaults
so older saves still work after we add more upgrades / weapons / pets.
"""
from __future__ import annotations
import json
from pathlib import Path

from settings import SAVE_FILE, CHAR_UPGRADES, PETS


# --------------------------------------------------------------
DEFAULT_SAVE = {
    "gold": 1000,                      # persistent gold (kept across runs)
    "upgrades": {                    # character upgrade levels
        k: 0 for k in CHAR_UPGRADES
    },
    "owned_guns": ["pistol"],        # weapons unlocked in hub
    "owned_pets": [],                # pet ids unlocked in hub
    "equipped_pet": None,            # pet id currently following the player
    "best_level": 0,                 # highest level cleared
    "version": 2,
}


def _coerce(data):
    """Merge user data over defaults so missing fields are filled in."""
    out = json.loads(json.dumps(DEFAULT_SAVE))  # deep copy
    if not isinstance(data, dict):
        return out
    out["gold"] = int(data.get("gold", out["gold"]))
    up = data.get("upgrades", {}) or {}
    for k in CHAR_UPGRADES:
        out["upgrades"][k] = int(up.get(k, 0))
    owned = data.get("owned_guns") or ["pistol"]
    if "pistol" not in owned:
        owned = ["pistol"] + list(owned)
    out["owned_guns"] = list(dict.fromkeys(owned))  # de-dup preserve order
    pets_owned = data.get("owned_pets") or []
    out["owned_pets"] = [p for p in pets_owned if p in PETS]
    eq = data.get("equipped_pet")
    if eq in out["owned_pets"]:
        out["equipped_pet"] = eq
    else:
        out["equipped_pet"] = None
    out["best_level"] = int(data.get("best_level", 0))
    return out


def load_save() -> dict:
    """Return the save dict, creating defaults if no file exists."""
    path = Path(SAVE_FILE).resolve()
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_SAVE))
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return json.loads(json.dumps(DEFAULT_SAVE))
    return _coerce(raw)


def write_save(data: dict) -> None:
    path = Path(SAVE_FILE)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def reset_save() -> dict:
    """Wipe progress and return defaults."""
    fresh = json.loads(json.dumps(DEFAULT_SAVE))
    write_save(fresh)
    return fresh
