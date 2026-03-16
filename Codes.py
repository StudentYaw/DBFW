from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QWidget, QFileDialog
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt
import re
from pathlib import Path
import sys
import os
from PIL import Image, ImageEnhance
import pytesseract


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
        self._setup_tesseract()
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

        self.upload_button = QPushButton("Upload Image (OCR)")
        self.upload_button.clicked.connect(self.upload_image_and_extract)
        button_layout.addWidget(self.upload_button)

    def _setup_tesseract(self):
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
            tesseract_path = os.path.join(base_path, 'tesseract-ocr', 'tesseract.exe')
            os.environ['TESSDATA_PREFIX'] = os.path.join(base_path, 'tesseract-ocr', 'tessdata')
        else:
            tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

    def _preprocess_for_ocr(self, image):
        """Leichte Vorverarbeitung für Screenshots (wird in ocr_check_text verwendet)."""
        image = image.convert('L')
        image = ImageEnhance.Contrast(image).enhance(2.5)
        image = ImageEnhance.Sharpness(image).enhance(2.0)
        return image

    def _preprocess_photo(self, image):
        """Vorverarbeitung für Fotos/hochgeladene Bilder - sanfter um Details zu erhalten."""
        # Upscale falls nötig damit Tesseract genug Pixel hat
        min_dim = 2000
        if max(image.width, image.height) < min_dim:
            scale = min_dim / max(image.width, image.height)
            image = image.resize(
                (int(image.width * scale), int(image.height * scale)),
                Image.Resampling.LANCZOS
            )
        return image

    def _ocr_image(self, image):
        """OCR auf einem Bild, probiert mehrere Preprocessing-Varianten und gibt den besten Text zurück."""
        variants = []

        # Variante 1: Original (nur upscaled)
        base = self._preprocess_photo(image)
        variants.append(base)

        # Variante 2: Graustufen + leichter Kontrast
        gray = base.convert('L')
        gray = ImageEnhance.Contrast(gray).enhance(1.5)
        variants.append(gray)

        # Variante 3: Graustufen + stärkerer Kontrast
        gray2 = base.convert('L')
        gray2 = ImageEnhance.Contrast(gray2).enhance(2.5)
        variants.append(gray2)

        best_text = ""
        best_count = 0
        for variant in variants:
            text = pytesseract.image_to_string(variant, config=r'--oem 3 --psm 3 -l eng')
            codes = self._extract_codes_from_text(text)
            if len(codes) > best_count:
                best_count = len(codes)
                best_text = text
        # Falls keine Variante Codes findet, trotzdem Text der ersten zurückgeben
        if not best_text:
            best_text = pytesseract.image_to_string(variants[1], config=r'--oem 3 --psm 3 -l eng')
        return best_text

    def _extract_codes_from_text(self, text):
        # Codes are always CAPS — no need to call .upper()
        # Match XXXX XXXX XXXX XXXX / XXXX-XXXX-XXXX-XXXX / XXXXXXXXXXXXXXXX
        pattern = r"\b([A-Z0-9]{4})[\s\-]?([A-Z0-9]{4})[\s\-]?([A-Z0-9]{4})[\s\-]?([A-Z0-9]{4})\b"
        matches = re.findall(pattern, text)
        codes = []
        for groups in matches:
            normalized = ''.join(groups)
            if len(normalized) != 16:
                continue
            # The full code must contain at least one digit AND at least one letter
            # to avoid matching pure words like MADEINJAPAN, CARDGAMEFB09 etc.
            if any(c.isdigit() for c in normalized) and any(c.isalpha() for c in normalized):
                codes.append(f"{normalized[0:4]} {normalized[4:8]} {normalized[8:12]} {normalized[12:16]}")
        return list(dict.fromkeys(codes))

    def extract_codes(self, overwrite=True):
        # Manual text input: allow lowercase by converting first
        text = self.input_box.toPlainText().upper()
        codes = self._extract_codes_from_text(text)

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

    def upload_image_and_extract(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select image for OCR",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff)"
        )
        if not file_path:
            return

        try:
            original = Image.open(file_path)
            all_codes = []
            best_texts = []

            # Only 0° and 90° — 180°/270° cause mirrored OCR artefacts (false codes)
            for angle in (0, 90):
                rotated = original.rotate(angle, expand=True)
                ocr_text = self._ocr_image(rotated)
                found = self._extract_codes_from_text(ocr_text)
                if found:
                    best_texts.append(f"[{angle}°]\n{ocr_text.strip()}")
                    for code in found:
                        if code not in all_codes:
                            all_codes.append(code)

            # Nur lesbaren Text (aus Rotationen mit Codes) im Textfeld anzeigen
            if best_texts:
                self.input_box.setPlainText("\n\n".join(best_texts))
            else:
                self.input_box.setPlainText("No codes found in any rotation.")

            if all_codes:
                with open("codes.txt", "w") as file:
                    for code in all_codes:
                        file.write(code.strip() + "\n")
                from dialog import message_box, ICON_INFORMATION
                message_box("Codes extracted and saved:\n" + "\n".join(all_codes), icon=ICON_INFORMATION)
            else:
                from dialog import message_box, ICON_EXCLAMATION
                message_box("No valid codes were found in the image.", icon=ICON_EXCLAMATION)
        except Exception as e:
            from dialog import message_box, ICON_STOP
            message_box(f"OCR failed: {e}", icon=ICON_STOP)

    def clear_text(self):
        self.input_box.clear()

def run_codes():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    window = CodeExtractor()
    window.show()
    app.exec()
