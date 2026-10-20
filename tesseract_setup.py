"""Cross-platform Tesseract binary resolution, shared by main.py and Codes.py."""

import os
import platform
import shutil
import sys

import pytesseract

_FALLBACK_PATHS = {
    "Windows": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "Darwin": "/opt/homebrew/bin/tesseract",  # Apple Silicon Homebrew default
    "Linux": "/usr/bin/tesseract",
}


def configure_tesseract() -> None:
    """Point pytesseract at a tesseract binary.

    Resolution order:
    1. Frozen (PyInstaller) build: bundled binary next to the app.
    2. TESSERACT_CMD environment variable, if set.
    3. A tesseract binary found on PATH.
    4. A common per-OS install location as a last-resort guess.
    """
    # Codes.py runs one tesseract process per CPU core. Tesseract builds with
    # OpenMP would each start several threads on top of that and oversubscribe
    # the CPU (on a 4-core machine a single call went from ~0.5s to over 90s
    # in testing), so cap
    # every process to one thread, as recommended by the Tesseract docs.
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")

    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        exe_name = "tesseract.exe" if platform.system() == "Windows" else "tesseract"
        pytesseract.pytesseract.tesseract_cmd = os.path.join(base_path, "tesseract-ocr", exe_name)
        os.environ["TESSDATA_PREFIX"] = os.path.join(base_path, "tesseract-ocr", "tessdata")
        return

    env_path = os.environ.get("TESSERACT_CMD")
    if env_path:
        pytesseract.pytesseract.tesseract_cmd = env_path
        return

    which_path = shutil.which("tesseract")
    if which_path:
        pytesseract.pytesseract.tesseract_cmd = which_path
        return

    pytesseract.pytesseract.tesseract_cmd = _FALLBACK_PATHS.get(platform.system(), "tesseract")
