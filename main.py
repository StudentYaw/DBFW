from __future__ import annotations

import logging
import sys
import os
from pathlib import Path
from typing import Any
import pyautogui
import pygetwindow as gw
from PIL import Image, ImageGrab, ImageEnhance, ImageFilter
from dialog import *
from Codes import run_codes
from config_manager import ConfigManager
from tesseract_setup import configure_tesseract
import pytesseract

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CodeInjector:
    def __init__(self) -> None:
        self.config = ConfigManager()
        self.resources = self.get_resources_path()
        self.scaled_images: dict[str, Path] = {}
        self.counter_suc = 0
        self.counter_err = 0
        self.counter_alr = 0
        self.counter_unk = 0
        self.not_done = True
        self._setup_tesseract()  # Einmalig beim Start

    def get_resources_path(self) -> Path:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS) / 'res'
        else:
            return Path(__file__).parent / 'res'

    def get_scaling_factor(
        self, original_resolution: tuple[float, float], current_resolution: tuple[float, float]
    ) -> float:
        width_factor = current_resolution[0] / original_resolution[0]
        height_factor = current_resolution[1] / original_resolution[1]
        return (width_factor + height_factor) / 2

    def scale_image(self, image_path: Path, scaling_factor: float) -> Path:
        scaled_path = self.resources / (image_path.stem + '_scaled.png')
        # Immer neu skalieren um sicherzustellen, dass der Skalierungsfaktor aktuell ist
        image = Image.open(image_path)
        new_width = int(image.width * scaling_factor)
        new_height = int(image.height * scaling_factor)
        scaled_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        scaled_image.save(scaled_path)
        logging.info(f"Scaled {image_path.name}: {image.width}x{image.height} -> {new_width}x{new_height}")
        return scaled_path

    def locate_image_on_screen(self, image_path: Path, scaling_factor: float) -> Any | None:
        scaled_path = self.scale_image(image_path, scaling_factor)
        try:
            position = pyautogui.locateOnScreen(str(scaled_path), confidence=self.config.get('confidence'))
            logging.info(f"Image found: {scaled_path}")
            return position
        except pyautogui.ImageNotFoundException:
            logging.warning(f"Image not found: {scaled_path}")
            return None

    def locate_image_on_screen_with_retry(
        self, image_path: Path, scaling_factor: float, retries: int = 3, delay: float = 1
    ) -> Any | None:
        for attempt in range(retries):
            position = self.locate_image_on_screen(image_path, scaling_factor)
            if position:
                return position
            pyautogui.sleep(delay)
        return None

    def resolve_to_standard_resolution(self, width: float, height: float) -> tuple[float, float]:
        standard_resolutions = [
            (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)
        ]
        tolerance = self.config.get('tolerance')
        for std_width, std_height in standard_resolutions:
            if abs(width - std_width) <= tolerance and abs(height - std_height) <= tolerance:
                return (std_width, std_height)
        return (width, height)  # Fallback to current

    def _enter_code(self, code: str) -> None:
        # Type exactly the normalized code string to avoid clipboard latency.
        normalized = ''.join(code.split()).upper()
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        interval = self.config.get('write_interval')
        if interval is None:
            interval = 0.05
        pyautogui.write(normalized, interval=float(interval))

    def run_injection(self) -> None:
        window = self._get_game_window()
        scaling_factor = self._compute_scaling_factor(window)
        self._prepare_scaled_images(scaling_factor)

        while self.not_done:
            codes = self._load_and_validate_codes()
            self._confirm_start(codes)
            pyautogui.sleep(self.config.get('sleep'))

            errors, codes = self._process_codes(codes)
            self._write_remaining_codes(codes)
            self._report_results(errors)

    def _get_game_window(self) -> Any:
        windows = gw.getWindowsWithTitle('DBSCGFW')
        if not windows:
            raise CustomException('Game is not opened. Make sure the game is opened!')
        return windows[0]

    def _compute_scaling_factor(self, window: Any) -> float:
        current_resolution = self.resolve_to_standard_resolution(window.width, window.height)
        return self.get_scaling_factor(self.config.get('original_resolution'), current_resolution)

    def _prepare_scaled_images(self, scaling_factor: float) -> None:
        image_paths = {
            'textbox': self.resources / 'textbox.png',
            'confirm': self.resources / 'confirm.png',
            'success': self.resources / 'success.png',
            'close': self.resources / 'close.png',
            'alreadyused': self.resources / 'alreadyused.png',
            'invalid': self.resources / 'invalid.png'
        }
        for key, path in image_paths.items():
            self.scaled_images[key] = self.scale_image(path, scaling_factor)

    def _load_and_validate_codes(self) -> list[str]:
        run_codes()
        try:
            with open(self.config.get('codes_file')) as f:
                codes = [''.join(line.strip().split()).upper() for line in f if line.strip()]
                if not codes:
                    raise CustomException(f'{self.config.get("codes_file")} is empty')
                if not all(len(code) == self.config.get('code_length') for code in codes):
                    invalid = [c for c in codes if len(c) != self.config.get('code_length')]
                    raise CustomException('Ungültige Codes gefunden:\n' + '\n'.join(invalid))
        except FileNotFoundError:
            raise CustomException(f'{self.config.get("codes_file")} not found')
        return codes

    def _confirm_start(self, codes: list[str]) -> None:
        approx_time = int(1 + len(codes) * (self.config.get('sleep') + self.config.get('sleep_confirm') + self.config.get('code_length') * self.config.get('write_interval')) / 60)
        suffix = 'minute' if approx_time == 1 else 'minutes'
        if message_box(f'This process will take approximately {approx_time} {suffix}. Continue?', style=STYLE_OKCANCEL) == IDCANCEL:
            sys.exit()

    def _process_codes(self, codes: list[str]) -> tuple[bool, list[str]]:
        errors = False
        while codes:
            code = codes.pop(0)
            self._submit_code(code)

            result = self.ocr_check_text()
            logging.info(f'OCR result for code {code}: {result}')
            if result == 'success':
                self.counter_suc += 1
            else:
                errors = True
                self._record_error(code, result)
                if self.counter_err + self.counter_unk >= self.config.get('max_errors'):
                    message_box('Exceeded the maximum number of fails!', icon=ICON_EXCLAMATION)
                    break

            self._close_result_dialog()
        return errors, codes

    def _submit_code(self, code: str) -> None:
        try:
            res = pyautogui.locateOnScreen(str(self.scaled_images['textbox']), confidence=self.config.get('confidence'))
            location = (res.left + res.width * 0.1, res.top + res.height * 0.5)
            pyautogui.click(*location)
            pyautogui.click(*location)
            pyautogui.sleep(self.config.get('sleep'))
            self._enter_code(code)
        except pyautogui.ImageNotFoundException as e:
            logging.error(f'Codes section not opened: {e}')
            raise CustomException('Codes section is not opened')

        try:
            res = pyautogui.locateOnScreen(str(self.scaled_images['confirm']), confidence=self.config.get('confidence'))
            pyautogui.click(pyautogui.center(res))
            pyautogui.sleep(self.config.get('sleep_confirm'))
        except pyautogui.ImageNotFoundException as e:
            logging.error(f'Cannot press confirm: {e}')
            raise CustomException('Cannot press confirm')

    def _record_error(self, code: str, result: str) -> None:
        if result == 'alreadyused':
            with open(self.config.get('codes_err_file'), 'a') as f:
                f.write(f'{code} Already used!\n')
            self.counter_alr += 1
        elif result == 'invalid':
            with open(self.config.get('codes_err_file'), 'a') as f:
                f.write(f'{code} Invalid Code!\n')
            self.counter_err += 1
        else:
            with open(self.config.get('codes_err_file'), 'a') as f:
                f.write(f'{code} Unknown Issue!\n')
            self.counter_unk += 1

    def _close_result_dialog(self) -> None:
        try:
            res = pyautogui.locateOnScreen(str(self.scaled_images['close']), confidence=self.config.get('confidence'))
            pyautogui.click(pyautogui.center(res))
        except pyautogui.ImageNotFoundException as e:
            logging.error(f'Cannot press close: {e}')
            raise CustomException('Cannot press close')

    def _write_remaining_codes(self, codes: list[str]) -> None:
        with open(self.config.get('codes_file'), 'w') as file:
            for code in codes:
                file.write(f'{code}\n')

    def _report_results(self, errors: bool) -> None:
        if errors:
            if message_box(
                f'Some errors occurred!\nThey were {self.counter_err} invalid codes, {self.counter_alr} codes that were already used, and {self.counter_suc} successful ones.\nThe codes have been written to {self.config.get("codes_err_file")}\nContinue?',
                icon=ICON_EXCLAMATION, style=STYLE_Q
            ) == IDNO:
                self.not_done = False
        else:
            if message_box(f'Done! I had {self.counter_suc} successful codes\nContinue?', style=STYLE_Q) == IDNO:
                self.not_done = False

    def _setup_tesseract(self) -> None:
        configure_tesseract()

    def _preprocess_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        Bereitet ein Bild für OCR vor:
        - Graustufen (weniger Rauschen)
        - Kontrast erhöhen (Text besser sichtbar)
        - Schärfen (Kanten klarer)
        Funktioniert bei jeder Auflösung und Bildqualität.
        """
        image = image.convert('L')                          # Graustufen
        image = ImageEnhance.Contrast(image).enhance(2.5)  # Kontrast erhöhen
        image = image.filter(ImageFilter.SHARPEN)           # Schärfen
        return image

    def ocr_check_text(self, region: tuple[int, int, int, int] | None = None) -> str:
        """
        Macht einen Screenshot und sucht per OCR nach bekannten Texten.
        region: (left, top, right, bottom) oder None für gesamten Bildschirm
        Gibt zurück: 'alreadyused', 'invalid', 'success', 'unknown'
        """
        screenshot = ImageGrab.grab(bbox=region) if region else ImageGrab.grab()
        screenshot = self._preprocess_for_ocr(screenshot)

        # Tesseract-Konfiguration: nur englische Zeichen, PSM 6 = gleichmäßiger Block
        custom_config = r'--oem 3 --psm 6 -l eng'
        text = pytesseract.image_to_string(screenshot, config=custom_config)
        text_lower = text.lower()
        logging.info(f"OCR erkannter Text: {text_lower[:100]}")

        if 'already entered this serial code' in text_lower:
            return 'alreadyused'
        elif 'already' in text_lower and 'serial' in text_lower:
            # Fallback falls OCR nicht perfekt ist
            return 'alreadyused'
        elif 'invalid' in text_lower or 'incorrect' in text_lower:
            return 'invalid'
        elif 'success' in text_lower or 'successfully' in text_lower or 'received' in text_lower:
            return 'success'
        else:
            return 'unknown'

if __name__ == "__main__":
    injector = CodeInjector()
    try:
        injector.run_injection()
    except CustomException as e:
        message_box(text=str(e), icon=e.icon)
        sys.exit(1)
