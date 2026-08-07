#!/usr/bin/env python3
"""World Clock - affiche plusieurs fuseaux horaires sur un afficheur LED HUB75.

Toute la configuration (panneaux, fuseaux, couleurs, police) se fait dans
config.json, a cote de ce fichier. Aucun besoin de modifier ce script.
"""
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config():
    with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def build_matrix(panel):
    o = RGBMatrixOptions()
    o.rows = panel.get("rows", 32)
    o.cols = panel.get("cols", 64)
    o.chain_length = panel.get("chain_length", 1)
    o.parallel = panel.get("parallel", 1)
    o.gpio_slowdown = panel.get("gpio_slowdown", 2)
    o.hardware_mapping = panel.get("hardware_mapping", "regular")
    o.brightness = panel.get("brightness", 70)
    if panel.get("disable_hardware_pulsing", False):
        o.disable_hardware_pulsing = True
    return RGBMatrix(options=o)


def main():
    cfg = load_config()
    matrix = build_matrix(cfg["panel"])
    canvas = matrix.CreateFrameCanvas()

    font = graphics.Font()
    font_path = cfg["font"]
    if not os.path.isabs(font_path):
        font_path = os.path.join(BASE_DIR, font_path)
    font.LoadFont(font_path)

    zones = cfg["zones"]
    refresh = cfg.get("refresh_seconds", 0.5)
    line_height = max(9, (matrix.height // max(1, len(zones))))
    top = line_height - 2

    try:
        while True:
            canvas.Clear()
            y = top
            for z in zones:
                now = datetime.now(ZoneInfo(z["tz"]))
                r, g, b = z["color"]
                text = f'{z["label"]:<9}{now:%H:%M}'
                graphics.DrawText(canvas, font, 1, y, graphics.Color(r, g, b), text)
                y += line_height
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(refresh)
    except KeyboardInterrupt:
        matrix.Clear()


if __name__ == "__main__":
    main()
