#!/usr/bin/env python3
"""World Clock - affiche plusieurs fuseaux horaires sur un afficheur LED HUB75.

Layout par ville (une colonne = largeur_villes / N villes) :
    LABEL      (police compacte, en haut)
    HH:MM      (grande police, ':' clignote chaque seconde)
    JJ/MM      (police compacte, en bas)

Si `weather.enabled` est vrai, une zone meteo est reservee a droite (largeur
`weather.width_px`) et les villes se partagent la largeur restante. Meteo :
    LABEL      (nom de la ville)
    23°        (temperature entiere)
    Soleil     (condition texte, mapping WMO -> FR)

Le user n'a en principe qu'a lister ses `zones` dans config.json. Toutes les
autres cles ci-dessous (panneau, polices, positions, meteo) ont un defaut
raisonnable et ne sont a mettre dans config.json QUE pour surcharger celui-ci.
"""
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
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
    "weather": {
        "enabled": True,
        "label": "PARIS",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "color": [255, 255, 255],
        "width_px": 48,
        "refresh_seconds": 3600,
    },
}

# Mapping WMO weather_code (Open-Meteo) -> libelle FR court (<=8 chars).
# Cf. https://open-meteo.com/en/docs (section "Weather variable documentation").
WEATHER_CODES = {
    0: "Soleil",
    1: "Eclairci", 2: "Nuages", 3: "Couvert",
    45: "Brouil.", 48: "Brouil.",
    51: "Bruine", 53: "Bruine", 55: "Bruine",
    56: "Verglas", 57: "Verglas",
    61: "Pluie", 63: "Pluie", 65: "Pluie",
    66: "P.Gelee", 67: "P.Gelee",
    71: "Neige", 73: "Neige", 75: "Neige", 77: "Neige",
    80: "Averses", 81: "Averses", 82: "Averses",
    85: "Neige", 86: "Neige",
    95: "Orage",
    96: "Grele", 99: "Grele",
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


def draw_centered(canvas, font, char_w, y, color, text, area_x, area_w):
    x = area_x + (area_w - len(text) * char_w) // 2
    graphics.DrawText(canvas, font, x, y, color, text)


def format_time(now, blink_on):
    sep = ":" if blink_on else " "
    return f"{now:%H}" + sep + f"{now:%M}"


def format_date(now):
    return f"{now:%d/%m}"


class WeatherService:
    """Fetch periodique de la meteo Open-Meteo dans un thread background.

    Le thread principal n'est jamais bloque par le HTTP : il lit juste le
    dernier etat cache via `get()`. En cas d'echec reseau, on garde la
    derniere valeur connue.
    """

    def __init__(self, latitude, longitude, refresh_seconds):
        self.latitude = latitude
        self.longitude = longitude
        self.refresh_seconds = refresh_seconds
        self._state = None
        self._lock = threading.Lock()

    def _fetch(self):
        params = urllib.parse.urlencode({
            "latitude": self.latitude,
            "longitude": self.longitude,
            "current": "temperature_2m,weather_code",
        })
        url = f"https://api.open-meteo.com/v1/forecast?{params}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.load(r)
        current = data["current"]
        return {
            "temp": round(current["temperature_2m"]),
            "code": int(current["weather_code"]),
        }

    def _loop(self):
        while True:
            try:
                new_state = self._fetch()
                with self._lock:
                    self._state = new_state
            except Exception as e:
                print(f"[weather] fetch failed: {e}", file=sys.stderr)
            time.sleep(self.refresh_seconds)

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def get(self):
        with self._lock:
            return self._state


def draw_weather(canvas, cfg, fonts, widths, service, area_x, area_w):
    color = graphics.Color(*cfg["weather"]["color"])
    state = service.get()
    if state is None:
        temp_text = "..."
        cond_text = "..."
    else:
        temp_text = f'{state["temp"]}°'
        cond_text = WEATHER_CODES.get(state["code"], "?")
    draw_centered(canvas, fonts["label"], widths["label"], cfg["y_label"],
                  color, cfg["weather"]["label"], area_x, area_w)
    draw_centered(canvas, fonts["time"], widths["time"], cfg["y_time"],
                  color, temp_text, area_x, area_w)
    draw_centered(canvas, fonts["date"], widths["date"], cfg["y_date"],
                  color, cond_text, area_x, area_w)


def main():
    cfg = load_config()
    matrix = build_matrix(cfg["panel"])
    canvas = matrix.CreateFrameCanvas()

    fonts = {
        "label": load_font(cfg["font"]["label"]),
        "time": load_font(cfg["font"]["time"]),
        "date": load_font(cfg["font"]["date"]),
    }
    widths = {
        "label": font_char_width(cfg["font"]["label"]),
        "time": font_char_width(cfg["font"]["time"]),
        "date": font_char_width(cfg["font"]["date"]),
    }

    weather_service = None
    weather_area_w = 0
    if cfg["weather"]["enabled"]:
        w = cfg["weather"]
        weather_service = WeatherService(w["latitude"], w["longitude"],
                                         w["refresh_seconds"])
        weather_service.start()
        weather_area_w = w["width_px"]

    zones = cfg["zones"]
    cities_area_w = matrix.width - weather_area_w
    col_w = cities_area_w // len(zones)
    refresh = cfg["refresh_seconds"]

    try:
        while True:
            blink_on = int(time.time()) % 2 == 0
            canvas.Clear()
            for i, z in enumerate(zones):
                now = datetime.now(ZoneInfo(z["tz"]))
                color = graphics.Color(*z["color"])
                col_x = i * col_w
                draw_centered(canvas, fonts["label"], widths["label"],
                              cfg["y_label"], color, z["label"], col_x, col_w)
                draw_centered(canvas, fonts["time"], widths["time"],
                              cfg["y_time"], color,
                              format_time(now, blink_on), col_x, col_w)
                draw_centered(canvas, fonts["date"], widths["date"],
                              cfg["y_date"], color, format_date(now),
                              col_x, col_w)
            if weather_service:
                draw_weather(canvas, cfg, fonts, widths, weather_service,
                             cities_area_w, weather_area_w)
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(refresh)
    except KeyboardInterrupt:
        matrix.Clear()


if __name__ == "__main__":
    main()
