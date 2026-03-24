from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QWidget, QFileDialog
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt
import re
from pathlib import Path
import sys
import os
from PIL import Image, ImageEnhance
import pytesseract
from config_manager import ConfigManager


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
        self.config = ConfigManager()
        self.setWindowTitle("Code Extractor")
        self.setGeometry(100, 100, 600, 400)
        self.setWindowIcon(QIcon(str(LOGO)))
        self.manual_overwrite = self._get_bool_config("manual_overwrite_default", True)
        self.ocr_overwrite_default = self._get_bool_config("ocr_overwrite_default", False)
        # Erstklick-Switch ist nur sinnvoll, wenn initial Overwrite aktiv ist.
        self._first_extract_click_pending = self.manual_overwrite

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Header
        header = QLabel("Paste your text below and extract codes")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        self.mode_label = QLabel()
        self.mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.mode_label)

        # Text edit
        self.input_box = QTextEdit()
        self.input_box.setFont(QFont("Arial", 12))
        layout.addWidget(self.input_box)

        # Button layout
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        # Buttons
        self.extract_button = QPushButton("Extract Codes")
        self.extract_button.clicked.connect(self._handle_extract_button_click)
        button_layout.addWidget(self.extract_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_text)
        button_layout.addWidget(self.clear_button)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.close)
        button_layout.addWidget(self.next_button)

        self.upload_button = QPushButton("Upload Image (OCR)")
        self.upload_button.clicked.connect(lambda: self.upload_image_and_extract())
        button_layout.addWidget(self.upload_button)

        mode_button_layout = QHBoxLayout()
        layout.addLayout(mode_button_layout)

        self.toggle_mode_button = QPushButton()
        self.toggle_mode_button.clicked.connect(self.toggle_extract_mode)
        mode_button_layout.addWidget(self.toggle_mode_button)

        self._update_mode_indicator()

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

    def _extract_codes_from_text(self, text, allow_compact=False, min_digits=2):
        text = (text or "").upper()

        # Prefer explicit 4x4 grouping in OCR-like text to avoid matching long words.
        separated_pattern = (
            r"(?<![A-Z0-9])"
            r"([A-Z0-9]{4})[\s\-]+([A-Z0-9]{4})[\s\-]+([A-Z0-9]{4})[\s\-]+([A-Z0-9]{4})"
            r"(?![A-Z0-9])"
        )

        matches = re.findall(separated_pattern, text)
        if allow_compact:
            compact_pattern = r"(?<![A-Z0-9])([A-Z0-9]{16})(?![A-Z0-9])"
            matches.extend([(m[0:4], m[4:8], m[8:12], m[12:16]) for m in re.findall(compact_pattern, text)])

        codes = []
        for groups in matches:
            normalized = ''.join(groups)
            if len(normalized) != 16:
                continue
            digit_count = sum(c.isdigit() for c in normalized)
            # Fragments like FB09CARDDATA often have very few digits.
            if digit_count < min_digits:
                continue

            # Wortartige OCR-Fragmente vermeiden: Ziffern sollten in mehreren 4er-Gruppen vorkommen.
            groups_with_digits = sum(any(ch.isdigit() for ch in group) for group in groups)
            if groups_with_digits < 2:
                continue

            if any(c.isdigit() for c in normalized) and any(c.isalpha() for c in normalized):
                codes.append(f"{normalized[0:4]} {normalized[4:8]} {normalized[8:12]} {normalized[12:16]}")
        return list(dict.fromkeys(codes))

    def _looks_like_single_compact_code_input(self, text):
        compact = re.sub(r"[\s\-]", "", (text or "").upper())
        return bool(re.fullmatch(r"[A-Z0-9]{16}", compact))

    def _write_codes(self, codes, overwrite=True):
        mode = "w" if overwrite else "a"
        with open("codes.txt", mode, encoding="utf-8") as file:
            for code in codes:
                file.write(code.strip() + "\n")

    def _get_bool_config(self, key, default):
        value = self.config.get(key)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "on"):
                return True
            if normalized in ("false", "0", "no", "off"):
                return False
        return bool(value)

    def extract_codes(self, overwrite=True):
        # Manual text input: allow lowercase by converting first
        text = self.input_box.toPlainText().upper()
        codes = self._extract_codes_from_text(text, allow_compact=False, min_digits=2)

        # Convenience fallback for users who paste one compact code without spaces.
        if not codes and self._looks_like_single_compact_code_input(text):
            codes = self._extract_codes_from_text(text, allow_compact=True, min_digits=1)

        if codes:
            self._write_codes(codes, overwrite=overwrite)

            result = "\n".join(codes)
            from dialog import message_box, ICON_INFORMATION
            message_box(f"Codes extracted and saved:\n{result}", icon=ICON_INFORMATION)
        else:
            from dialog import message_box, ICON_EXCLAMATION
            message_box("No valid codes were found in the text.", icon=ICON_EXCLAMATION)

    def upload_image_and_extract(self, overwrite=None):
        if overwrite is None:
            overwrite = self.ocr_overwrite_default

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
                found = self._extract_codes_from_text(ocr_text, allow_compact=False, min_digits=2)
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
                self._write_codes(all_codes, overwrite=overwrite)
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

    def _update_mode_indicator(self):
        mode_name = "Overwrite" if self.manual_overwrite else "Append"
        first_click_hint = " (First click switches to append)" if self._first_extract_click_pending else ""
        self.mode_label.setText(f"Manual Extract Mode: {mode_name}{first_click_hint}")
        next_mode = "Append" if self.manual_overwrite else "Overwrite"
        self.toggle_mode_button.setText(f"Switch to {next_mode}")

    def toggle_extract_mode(self):
        self.manual_overwrite = not self.manual_overwrite
        self._first_extract_click_pending = False
        self._update_mode_indicator()

    def _handle_extract_button_click(self):
        if self._first_extract_click_pending:
            self.manual_overwrite = False
            self._first_extract_click_pending = False
            self._update_mode_indicator()
        self.extract_codes(overwrite=self.manual_overwrite)


def run_codes():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    window = CodeExtractor()
    window.show()
    app.exec()
