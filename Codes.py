from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QWidget, QFileDialog
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt
import re
from pathlib import Path
import sys
import os
from PIL import Image, ImageEnhance, ImageOps, ImageStat
import pytesseract
from pytesseract import Output
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
        self.ocr_selection_mode = self._get_ocr_selection_mode_config()
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

        if self.ocr_selection_mode == "code":
            ocr_configs = [
                r'--oem 3 --psm 6 -l eng',
                r'--oem 3 --psm 3 -l eng',
            ]
        else:
            ocr_configs = [
                r'--oem 3 --psm 6 -l eng',
                r'--oem 3 --psm 11 -l eng',
                r'--oem 3 --psm 3 -l eng',
            ]

        best_text = ""
        best_score = float("-inf")
        for variant in variants:
            for ocr_config in ocr_configs:
                text = pytesseract.image_to_string(variant, config=ocr_config)
                score = self._score_ocr_variant(variant, text)
                if score > best_score:
                    best_score = score
                    best_text = text

        if not best_text and variants:
            best_text = pytesseract.image_to_string(variants[0], config=r'--oem 3 --psm 6 -l eng')
        return best_text

    def _score_ocr_variant(self, image, text):
        codes = self._extract_codes_from_text(text, allow_compact=False, min_digits=2)
        confidence_score = self._ocr_confidence_score(image)
        text_quality_score = self._text_quality_score(text)

        # Mode beeinflusst, ob Volltext oder Codes bei der Variantenauswahl priorisiert werden.
        if self.ocr_selection_mode == "code":
            return len(codes) * 8.0 + confidence_score * 0.05 + text_quality_score * 0.2
        if self.ocr_selection_mode == "balanced":
            return len(codes) * 3.0 + confidence_score * 0.08 + text_quality_score * 0.4
        return confidence_score * 0.1 + text_quality_score

    def _ocr_confidence_score(self, image):
        try:
            data = pytesseract.image_to_data(
                image,
                config=r'--oem 3 --psm 3 -l eng',
                output_type=Output.DICT,
            )
        except Exception:
            return 0.0

        conf_values = []
        for value in data.get("conf", []):
            try:
                conf = float(value)
            except (TypeError, ValueError):
                continue
            if conf >= 0:
                conf_values.append(conf)

        if not conf_values:
            return 0.0
        return sum(conf_values) / len(conf_values)

    def _text_quality_score(self, text):
        upper = (text or "").upper()
        tokens = re.findall(r"[A-Z0-9]+", upper)
        if not tokens:
            return 0.0

        alpha_tokens = sum(1 for token in tokens if any(ch.isalpha() for ch in token))
        mixed_tokens = sum(1 for token in tokens if any(ch.isalpha() for ch in token) and any(ch.isdigit() for ch in token))
        long_noise = sum(1 for token in tokens if len(token) >= 14 and token.isalpha())
        bad_symbol_count = len(re.findall(r"[@#%&*_`~^\\|]", upper))
        short_token_count = sum(1 for token in tokens if len(token) == 1)

        # Keywords aus den Karten helfen, echten Text gegen OCR-Gibberish zu priorisieren.
        keyword_hits = sum(
            1
            for keyword in (
                "REDEEM", "REWARDS", "DIGITAL", "VERSION", "USE", "THIS", "CODE",
                "UNLOCK", "INGAME", "IN", "GAME", "DEADLINE", "MARCH", "CARD", "DATA"
            )
            if keyword in upper
        )

        phrase_hits = sum(
            1
            for phrase in (
                "REDEEM YOUR REWARDS",
                "IN THE DIGITAL VERSION",
                "USE THIS CODE TO UNLOCK YOUR IN-GAME REWARD",
                "CODE REDEMPTION DEADLINE",
            )
            if phrase in upper
        )

        score = alpha_tokens * 1.2 + mixed_tokens * 0.8
        score += keyword_hits * 4.0 + phrase_hits * 10.0
        score -= long_noise * 2.0
        score -= bad_symbol_count * 0.7
        score -= short_token_count * 0.8
        return score

    def _get_ocr_selection_mode_config(self):
        raw = self.config.get("ocr_selection_mode")
        if raw is None:
            return "text"

        value = str(raw).strip().lower()
        if value in ("code", "balanced", "text"):
            return value
        return "text"

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

    def _detect_card_regions(self, image):
        if min(image.width, image.height) < 400:
            return []

        layout_image = self._prepare_layout_image(image)
        x_spans = self._find_bright_spans(layout_image, axis="x")
        y_spans = self._find_bright_spans(layout_image, axis="y")
        if len(x_spans) < 2 or len(y_spans) < 2:
            return []

        scale_x = image.width / layout_image.width
        scale_y = image.height / layout_image.height
        pad_x = max(6, int(image.width * 0.006))
        pad_y = max(6, int(image.height * 0.006))
        min_width = max(120, int(image.width * 0.08))
        min_height = max(160, int(image.height * 0.12))

        regions = []
        for top, bottom in y_spans:
            for left, right in x_spans:
                x1 = max(0, int(round(left * scale_x)) - pad_x)
                y1 = max(0, int(round(top * scale_y)) - pad_y)
                x2 = min(image.width, int(round(right * scale_x)) + pad_x)
                y2 = min(image.height, int(round(bottom * scale_y)) + pad_y)
                if x2 - x1 < min_width or y2 - y1 < min_height:
                    continue
                regions.append((x1, y1, x2, y2))
        return regions

    def _prepare_layout_image(self, image):
        gray = ImageOps.autocontrast(image.convert('L'))
        max_side = 1000
        if max(gray.width, gray.height) > max_side:
            scale = max_side / max(gray.width, gray.height)
            gray = gray.resize(
                (max(1, int(gray.width * scale)), max(1, int(gray.height * scale))),
                Image.Resampling.BILINEAR,
            )
        return gray

    def _find_bright_spans(self, image, axis="x"):
        width, height = image.size
        mean_value = ImageStat.Stat(image).mean[0]
        bright_threshold = max(145, min(235, int(mean_value + 35)))

        if axis == "x":
            outer_len = width
            inner_len = height
        else:
            outer_len = height
            inner_len = width

        step = max(1, inner_len // 250)
        pixels = image.load()
        values = []
        for outer in range(outer_len):
            bright = 0
            samples = 0
            for inner in range(0, inner_len, step):
                value = pixels[outer, inner] if axis == "x" else pixels[inner, outer]
                bright += 1 if value >= bright_threshold else 0
                samples += 1
            values.append(bright / samples if samples else 0.0)

        smoothed = self._smooth_values(values, radius=4)
        low = min(smoothed)
        high = max(smoothed)
        if high - low < 0.08:
            return []

        active_threshold = max(0.18, low + (high - low) * 0.45)
        active = [value >= active_threshold for value in smoothed]
        spans = self._boolean_spans(active)
        spans = self._merge_spans(spans, gap_limit=max(3, outer_len // 80))
        min_span = max(24, int(outer_len * 0.08))
        return [span for span in spans if span[1] - span[0] >= min_span]

    def _smooth_values(self, values, radius=4):
        if not values:
            return []
        smoothed = []
        for index in range(len(values)):
            start = max(0, index - radius)
            end = min(len(values), index + radius + 1)
            window = values[start:end]
            smoothed.append(sum(window) / len(window))
        return smoothed

    def _boolean_spans(self, flags):
        spans = []
        start = None
        for index, flag in enumerate(flags):
            if flag and start is None:
                start = index
            elif not flag and start is not None:
                spans.append((start, index))
                start = None
        if start is not None:
            spans.append((start, len(flags)))
        return spans

    def _merge_spans(self, spans, gap_limit):
        if not spans:
            return []
        merged = [list(spans[0])]
        for start, end in spans[1:]:
            previous = merged[-1]
            if start - previous[1] <= gap_limit:
                previous[1] = end
            else:
                merged.append([start, end])
        return [(start, end) for start, end in merged]

    def _cleanup_display_text(self, text):
        cleaned_lines = []
        previous_line = None
        for raw_line in (text or "").splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip(" \t\r\n'\"`|“”‘’")
            if not line:
                continue
            if re.fullmatch(r"[-=~_.,;:|/\\]+", line):
                continue

            compact = re.sub(r"[^A-Z0-9]", "", line.upper())
            if len(compact) < 3:
                continue
            if previous_line and line.upper() == previous_line.upper():
                continue

            cleaned_lines.append(line)
            previous_line = line
        return "\n".join(cleaned_lines).strip()

    def _ocr_cards_in_image(self, image):
        card_regions = self._detect_card_regions(image)
        if not card_regions:
            return "", []

        card_texts = []
        all_codes = []
        for region in card_regions:
            card_image = image.crop(region)
            ocr_text = self._cleanup_display_text(self._ocr_image(card_image))
            if ocr_text:
                card_texts.append(ocr_text)
            for code in self._extract_codes_from_text(ocr_text, allow_compact=False, min_digits=2):
                if code not in all_codes:
                    all_codes.append(code)

        return "\n\n".join(card_texts).strip(), all_codes

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
            angle_results = []
            best_display_text = ""
            best_display_score = float("-inf")
            best_display_angle = 0

            # 0° und 90° reichen fuer die meisten Fotos; jetzt bevorzugt mit Karten-Segmentierung.
            for angle in (0, 90):
                rotated = original.rotate(angle, expand=True)
                segmented_text, segmented_codes = self._ocr_cards_in_image(rotated)
                if segmented_text:
                    ocr_text = segmented_text
                    found = segmented_codes
                else:
                    ocr_text = self._cleanup_display_text(self._ocr_image(rotated))
                    found = self._extract_codes_from_text(ocr_text, allow_compact=False, min_digits=2)

                display_score = self._text_quality_score(ocr_text)
                angle_results.append((angle, found))
                if display_score > best_display_score:
                    best_display_score = display_score
                    best_display_angle = angle
                    best_display_text = f"[{angle}°]\n{ocr_text.strip()}"

            # Codes konservativ sammeln: nur aus 0° und dem bestlesbaren Winkel.
            all_codes = []
            selected_angles = {0, best_display_angle}
            for angle, found in angle_results:
                if angle not in selected_angles:
                    continue
                for code in found:
                    if code not in all_codes:
                        all_codes.append(code)

            if best_display_text.strip():
                self.input_box.setPlainText(best_display_text)
            else:
                self.input_box.setPlainText("No readable OCR text found.")

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
