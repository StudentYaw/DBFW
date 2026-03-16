from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QWidget
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt
import re
from pathlib import Path
import sys


# Resources folder
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # PyInstaller temp path
    RESOURCES = Path(sys._MEIPASS) / 'res'
else:
    # Local res folder
    RESOURCES = Path(__file__).parent / 'res'

LOGO = RESOURCES / 'logo.ico'


class CodeExtractor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Code Extractor")
        self.setGeometry(100, 100, 600, 400)
        self.setWindowIcon(QIcon(str(LOGO)))

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Header
        header = QLabel("Paste your text below and extract codes")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Text edit
        self.input_box = QTextEdit()
        self.input_box.setFont(QFont("Arial", 12))
        layout.addWidget(self.input_box)

        # Button layout
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        # Buttons
        self.extract_button = QPushButton("Extract Codes")
        self.extract_button.clicked.connect(self.extract_codes)
        button_layout.addWidget(self.extract_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_text)
        button_layout.addWidget(self.clear_button)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.close)
        button_layout.addWidget(self.next_button)

    def extract_codes(self, overwrite=True):
        text = self.input_box.toPlainText()

        # Text in Großbuchstaben umwandeln, damit Groß-/Kleinschreibung egal ist
        text = text.upper()

        # Erkenne Codes mit Leerzeichen: XXXX XXXX XXXX XXXX
        pattern_spaces = r"\b([A-Z0-9]{4}) ([A-Z0-9]{4}) ([A-Z0-9]{4}) ([A-Z0-9]{4})\b"
        # Erkenne Codes ohne Leerzeichen: XXXXXXXXXXXXXXXX (16 Zeichen)
        pattern_nospaces = r"\b([A-Z0-9]{4})([A-Z0-9]{4})([A-Z0-9]{4})([A-Z0-9]{4})\b"

        codes = []
        for match in re.finditer(pattern_spaces, text):
            code = f"{match.group(1)} {match.group(2)} {match.group(3)} {match.group(4)}"
            codes.append(code)

        # Nur suchen wenn noch keine gefunden (damit keine Doppelungen)
        if not codes:
            for match in re.finditer(pattern_nospaces, text):
                code = f"{match.group(1)} {match.group(2)} {match.group(3)} {match.group(4)}"
                codes.append(code)

        # Duplikate entfernen
        codes = list(dict.fromkeys(codes))

        if codes:
            mode = "w" if overwrite else "a"
            with open("codes.txt", mode) as file:
                for code in codes:
                    file.write(code.strip() + "\n")

            result = "\n".join(codes)
            from dialog import message_box, ICON_INFORMATION
            message_box(f"Codes extracted and saved:\n{result}", icon=ICON_INFORMATION)
        else:
            from dialog import message_box, ICON_EXCLAMATION
            message_box("No valid codes were found in the text.", icon=ICON_EXCLAMATION)

    def clear_text(self):
        self.input_box.clear()

def run_codes():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    window = CodeExtractor()
    window.show()
    app.exec()
