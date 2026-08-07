# World Clock — Horloge multi-fuseaux sur afficheur LED

Affiche plusieurs fuseaux horaires sur un afficheur LED HUB75 (type « bandeau
aéroport ») piloté par un Raspberry Pi. Chaque ville s'affiche avec son heure
locale et sa couleur. Les changements d'heure été/hiver sont gérés
automatiquement.

## Contenu du dossier

```
worldclock/
├── main.py                Le programme (n'a pas besoin d'être modifié)
├── config.example.json    Modèle de configuration à copier en config.json
├── config.json            TA configuration (ignorée par git)
├── install.sh             Installation / mise à jour en une commande (idempotent)
├── fonts/                 Polices d'affichage (.bdf)
└── README.md              Ce fichier
```

## Matériel

- Un Raspberry Pi (Zero 2 / 3 / 4 / 5) avec Raspberry Pi OS.
- Un ou plusieurs panneaux LED **HUB75** 64×32 (ex. Waveshare P4 ou P5).
- Une carte d'interface **Adafruit RGB Matrix Bonnet / HAT** (aucune soudure).
- Une **alimentation 5 V** dédiée et suffisante (~4 A max par panneau).

Le Pi se branche sur son alimentation habituelle. Les panneaux sont alimentés
par l'alimentation 5 V séparée, jamais par le Pi.

## Installation

Copie ce dossier `worldclock/` sur le Pi (par ex. dans `~/worldclock`), puis :

```bash
cd ~/worldclock
cp config.example.json config.json   # première fois seulement
bash install.sh
```

Le script :

1. installe les dépendances,
2. compile et installe la bibliothèque LED **une seule fois** (il saute cette
   étape si elle est déjà là),
3. désactive le module son du Pi (connu pour perturber les LED),
4. crée un **service** qui lance l'horloge,
5. démarre l'horloge et l'active **au démarrage du Pi**.

Le script est **idempotent** : tu peux le relancer autant de fois que tu veux
(après une mise à jour de `config.json` ou du code) sans effet indésirable.

## Configuration (`config.json`)

Tout se règle ici. Après chaque modification :

```bash
sudo systemctl restart worldclock
```

### Les fuseaux (`zones`)

```json
"zones": [
  { "label": "PARIS",    "tz": "Europe/Paris",     "color": [255, 90, 0] },
  { "label": "NEW YORK", "tz": "America/New_York", "color": [0, 160, 255] },
  { "label": "TOKYO",    "tz": "Asia/Tokyo",       "color": [0, 220, 120] }
]
```

- `label` : le texte affiché (garde-le court).
- `tz` : nom du fuseau au format IANA (`Europe/Paris`, `America/New_York`,
  `Asia/Tokyo`, `America/Los_Angeles`, `Asia/Dubai`, `Australia/Sydney`…).
  Liste complète : <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>
- `color` : couleur `[R, G, B]` (0–255).

Tu peux mettre autant de villes que la hauteur de l'écran le permet (3 tiennent
bien sur un panneau de 32 pixels de haut).

### Les panneaux (`panel`)

| Clé | Rôle |
|-----|------|
| `chain_length` | Nombre de panneaux chaînés (1, 2, 3…). **Mets 3 quand ton 3e panneau arrive.** |
| `parallel` | Nombre de chaînes en parallèle (1 en usage normal). |
| `rows`, `cols` | Résolution d'UN panneau (64×32 → `cols`=64, `rows`=32). |
| `hardware_mapping` | `regular` ou `adafruit-hat` selon ta carte. |
| `gpio_slowdown` | 1 à 4. Augmente si l'image scintille ou plante (Pi 4/5 : 2–4). |
| `disable_hardware_pulsing` | `true` si tu lançais la démo avec `--led-no-hardware-pulse`. |
| `brightness` | Luminosité 0–100. |

### La police (`font`)

Chemin relatif au dossier du projet. Polices fournies dans `fonts/` :
`5x7.bdf` (compacte), `6x10.bdf` (par défaut), `6x13.bdf`, `7x13.bdf` (grande).

## Gérer le service

```bash
sudo systemctl status worldclock     # état
sudo systemctl restart worldclock    # relancer (après modif config)
sudo systemctl stop worldclock       # arrêter
sudo systemctl start worldclock      # démarrer
journalctl -u worldclock -f          # voir les logs en direct
```

## Dépannage

- **Écran noir / plante au lancement** : regarde `journalctl -u worldclock -f`.
  Essaie d'augmenter `gpio_slowdown`, ou passe `disable_hardware_pulsing` à
  `true`.
- **Les deux moitiés sont inversées** (panneaux chaînés dans l'autre sens) :
  c'est un problème de mapping, dis-le, on ajoutera un `pixel_mapper`.
- **Couleurs fausses** (rouge/bleu inversés) : certains panneaux inversent R et
  B ; on peut le corriger dans le mapping.
- **L'heure est décalée** : vérifie le fuseau du Pi (`timedatectl`) et que
  l'heure réseau (NTP) est active.

## Ajouter le 3e panneau

1. Branche-le en série après le 2e.
2. Dans `config.json`, passe `"chain_length"` à `3`.
3. `sudo systemctl restart worldclock`.

## Désinstaller

```bash
sudo systemctl disable --now worldclock
sudo rm /etc/systemd/system/worldclock.service
sudo systemctl daemon-reload
```
