#!/usr/bin/env python3
"""World Clock - affiche plusieurs fuseaux horaires sur un afficheur LED HUB75.

Layout par ville (une colonne = matrix.width / N villes) :
    LABEL      (police compacte, en haut)
    HH:MM      (grande police, ':' clignote chaque seconde)
    JJ/MM      (police compacte, en bas)

Le user n'a en principe qu'a lister ses `zones` dans config.json. Toutes les
autres cles ci-dessous (panneau, polices, positions) ont un defaut raisonnable
et ne sont a mettre dans config.json QUE pour surcharger celui-ci.
"""
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "panel": {
        "rows": 32,
        "cols": 64,
        "chain_length": 2,
        "parallel": 1,
        "gpio_slowdown": 2,
        "hardware_mapping": "regular",
        "pixel_mapper_config": "Rotate:180",
        "disable_hardware_pulsing": False,
        "brightness": 70,
    },
    "font": {
        "label": "fonts/5x7.bdf",
        "time": "fonts/7x13.bdf",
        "date": "fonts/5x7.bdf",
    },
    # Baselines Y (rgbmatrix dessine du bas du glyph vers le haut).
    # Empilement label(7) + heure(13) + date(7) sur une matrice 32 px.
    "y_label": 7,
    "y_time": 21,
    "y_date": 31,
    "refresh_seconds": 0.5,
}


def deep_merge(default, override):
    """Merge recursif : les cles de `override` ecrasent celles de `default`."""
    result = dict(default)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config():
    with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
        return deep_merge(DEFAULTS, json.load(f))


def build_matrix(panel):
    o = RGBMatrixOptions()
    o.rows = panel["rows"]
    o.cols = panel["cols"]
    o.chain_length = panel["chain_length"]
    o.parallel = panel["parallel"]
    o.gpio_slowdown = panel["gpio_slowdown"]
    o.hardware_mapping = panel["hardware_mapping"]
    o.brightness = panel["brightness"]
    if panel["pixel_mapper_config"]:
        o.pixel_mapper_config = panel["pixel_mapper_config"]
    if panel["disable_hardware_pulsing"]:
        o.disable_hardware_pulsing = True
    # rgbmatrix passe par defaut de root a `daemon` apres avoir pris les GPIO,
    # ce qui casse la lecture des fichiers dans /home/<user> (mode 700).
    o.drop_privileges = False
    return RGBMatrix(options=o)


def load_font(rel_path):
    font = graphics.Font()
    path = rel_path if os.path.isabs(rel_path) else os.path.join(BASE_DIR, rel_path)
    font.LoadFont(path)
    return font


def font_char_width(rel_path):
    # Nos polices BDF sont monospace : "5x7.bdf" -> largeur 5.
    return int(os.path.basename(rel_path).split("x", 1)[0])


def draw_centered(canvas, font, char_w, y, color, text, col_x, col_w):
    x = col_x + (col_w - len(text) * char_w) // 2
    graphics.DrawText(canvas, font, x, y, color, text)


def format_time(now, blink_on):
    sep = ":" if blink_on else " "
    return f"{now:%H}" + sep + f"{now:%M}"


def format_date(now):
    return f"{now:%d/%m}"


def main():
    cfg = load_config()
    matrix = build_matrix(cfg["panel"])
    canvas = matrix.CreateFrameCanvas()

    font_label = load_font(cfg["font"]["label"])
    font_time = load_font(cfg["font"]["time"])
    font_date = load_font(cfg["font"]["date"])

    w_label = font_char_width(cfg["font"]["label"])
    w_time = font_char_width(cfg["font"]["time"])
    w_date = font_char_width(cfg["font"]["date"])

    zones = cfg["zones"]
    col_w = matrix.width // len(zones)
    refresh = cfg["refresh_seconds"]

    try:
        while True:
            blink_on = int(time.time()) % 2 == 0
            canvas.Clear()
            for i, z in enumerate(zones):
                now = datetime.now(ZoneInfo(z["tz"]))
                color = graphics.Color(*z["color"])
                col_x = i * col_w
                draw_centered(canvas, font_label, w_label, cfg["y_label"],
                              color, z["label"], col_x, col_w)
                draw_centered(canvas, font_time, w_time, cfg["y_time"],
                              color, format_time(now, blink_on), col_x, col_w)
                draw_centered(canvas, font_date, w_date, cfg["y_date"],
                              color, format_date(now), col_x, col_w)
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(refresh)
    except KeyboardInterrupt:
        matrix.Clear()


if __name__ == "__main__":
    main()
