# DBFW – Code Injector für Fusion World

DBFW löst Seriencodes in der digitalen Version von
*DRAGON BALL SUPER CARD GAME FUSION WORLD* automatisch ein:

1. **Codes sammeln:** Im Fenster „Code Extractor“ Text einfügen oder ein Foto
   der Codekarten hochladen (OCR). Die Codes landen in `codes.txt`.
2. **Codes einlösen:** DBFW sucht das Eingabefeld im Spiel, tippt jeden Code
   ein, bestätigt und liest das Ergebnis per OCR vom Bildschirm.
   Fehlgeschlagene Codes landen in `codes_with_errors.txt`.

Vor dem Start muss das Spiel geöffnet sein und der Bereich zum Einlösen von
Codes angezeigt werden.

## Windows

1. [Python 3.12](https://www.python.org/downloads/) und
   [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) installieren
   (Standardpfad `C:\Program Files\Tesseract-OCR`).
2. Im Projektordner:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```

Eine eigenständige `DBFW.exe` (mit Tesseract) baut man mit
`pip install -r requirements-build.txt` und `pyinstaller main.spec`.

## macOS (Apple Silicon) – neu, noch nicht mit dem Spiel getestet

Die Mac-Unterstützung ist neu und wurde bisher nur automatisch getestet, nicht
mit dem echten Spiel. Rückmeldungen zu Problemen helfen sehr.

1. Mit [Homebrew](https://brew.sh) Python und Tesseract installieren:
   ```
   brew install python@3.12 python-tk@3.12 tesseract
   ```
2. Im Projektordner:
   ```
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Berechtigungen:** DBFW braucht *Bildschirmaufnahme* (um das Spiel zu sehen)
   und *Bedienungshilfen* (um zu klicken und zu tippen). Beim ersten Start
   fragt macOS danach. Danach unter *Systemeinstellungen → Datenschutz &
   Sicherheit* bei beiden Punkten das Programm einschalten, aus dem DBFW
   gestartet wird (z. B. *Terminal*), und das Terminal neu starten.
4. **Fenstername prüfen:** Spiel öffnen, dann
   ```
   python game_window.py
   ```
   ausführen. Das listet alle offenen Fenster als `App | Fenstertitel`.
   DBFW sucht nach `window_title` aus `config.yaml` (Standard: `DBSCGFW`,
   Groß-/Kleinschreibung egal). Steht das Spiel unter einem anderen Namen in der
   Liste, diesen Namen in `config.yaml` eintragen.
5. Starten:
   ```
   python main.py
   ```

Hinweise:
- Das Spiel muss auf dem **Hauptbildschirm** laufen.
- Retina-Bildschirme werden automatisch berücksichtigt.
- Eine fertige Mac-App (`.app`) gibt es noch nicht.

## Konfiguration (`config.yaml`)

Fehlende Einträge fallen auf die Standardwerte in `config_manager.py` zurück.

| Schlüssel | Bedeutung |
|---|---|
| `window_title` | Teil des Fenster- bzw. App-Namens des Spiels |
| `codes_file` / `codes_err_file` | Datei mit den Codes / mit fehlgeschlagenen Codes |
| `code_length` | Länge eines Codes ohne Leerzeichen (16) |
| `confidence` | Mindest-Übereinstimmung bei der Bildsuche (0–1) |
| `sleep` / `sleep_confirm` | Wartezeit nach Klicks / nach dem Bestätigen (Sekunden) |
| `write_interval` | Pause zwischen zwei getippten Zeichen (Sekunden) |
| `original_resolution` | Auflösung, in der die Bilder in `res/` aufgenommen wurden |
| `tolerance` | Toleranz beim Einrasten auf Standardauflösungen (Pixel) |
| `max_errors` | Abbruch nach so vielen ungültigen/unklaren Codes pro Runde |
| `manual_overwrite_default` / `ocr_overwrite_default` | Codes-Datei überschreiben statt anhängen |

## Tests

```
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Die CI führt die Tests unter Windows und macOS aus.
