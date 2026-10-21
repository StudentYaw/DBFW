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

## macOS (Apple Silicon)

Mit dem echten Spiel getestet auf einem MacBook Pro mit Apple Silicon und
deutschem Tastaturlayout. Eingelöste Codes, bereits benutzte Codes und
ungültige Codes wurden jeweils richtig erkannt. Rückmeldungen zu Problemen
helfen sehr.

### Einrichten

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
   gestartet wird, und dieses Programm neu starten. Das ist zum Beispiel
   *Terminal* oder, beim Terminal in der Claude-App, *Claude*.
4. **Fenstername prüfen:** Spiel öffnen, dann
   ```
   python game_window.py
   ```
   ausführen. Das listet alle sichtbaren Fenster als `App | Fenstertitel`.
   DBFW sucht nach `window_title` aus `config.yaml` (Standard: `DBSCGFW`,
   Groß-/Kleinschreibung egal). Das Spiel selbst heißt `DBSCGFW`, der Launcher
   `DBSCG FW` (mit Leerzeichen). Der Standard passt also. Steht das Spiel unter
   einem anderen Namen in der Liste, diesen Namen in `config.yaml` eintragen.

### Codes einlösen

1. Das Spiel im **Fenstermodus** laufen lassen, nicht im macOS-Vollbild. Am
   besten das Fenster groß ziehen, z. B. über den grünen Knopf → „Füllen“.
2. Im Spiel *Enter a code* → *Serial code* öffnen. Die vier Eingabefelder
   müssen leer sein, sonst einmal auf *Reset* klicken.
3. `python main.py` starten. Das Spiel muss dabei **auf dem aktuellen
   Bildschirm sichtbar** sein (siehe Hinweise).
4. Im Fenster *Code Extractor* die Codes einfügen, auf **Extract Codes**
   klicken und die Meldung mit OK schließen. Erst dann auf **Next** klicken.
   *Next* allein speichert keine Codes.
5. Bei „This process will take approximately … Continue?“ auf **OK** klicken.
   Ab dann **Maus und Tastatur nicht anfassen**, bis DBFW das Ergebnis meldet.
   Pro Code dauert es etwa 10 Sekunden.

Hinweise:
- **Kein macOS-Vollbild und kein anderer Space:** DBFW findet nur Fenster,
  die beim Start auf dem aktuellen Bildschirm sichtbar sind. Läuft das Spiel
  im Vollbild oder auf einem anderen Schreibtisch, meldet DBFW „Game is not
  opened“. Seine eigenen Fenster öffnen sich außerdem auf dem Schreibtisch und
  verdecken sonst das Spiel.
- **Nichts über dem Spiel:** DBFW sucht das Eingabefeld und den *Confirm*-Knopf
  auf dem Bildschirm. Liegt ein anderes Fenster darüber, z. B. das Terminal,
  meldet DBFW „Codes section is not opened“ oder „Cannot press confirm“.
- Das Spiel muss auf dem **Hauptbildschirm** laufen.
- Retina-Bildschirme und Fenster, die nicht 16:9 sind (das Spiel zeigt dann
  schwarze Balken), werden automatisch berücksichtigt.
- Andere Tastaturlayouts als US (z. B. Deutsch) werden unterstützt.
- Das Spiel sperrt die Code-Eingabe nach **10 falschen Codes für 6 Stunden**.
  DBFW bricht eine Runde nach `max_errors` ungültigen oder unklaren Codes ab
  (Standard: 5).
- Liegen mehrere Karten auf einem Foto, erkennt die Foto-OCR nicht immer alle
  Codes. Die Liste nach dem Hochladen prüfen oder die Codes als Text eingeben.
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
