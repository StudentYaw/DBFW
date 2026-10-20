import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytesseract
import pytest
from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

import dialog
from config_manager import ConfigManager
from Codes import CodeExtractor
from tesseract_setup import configure_tesseract


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def extractor(qapp, monkeypatch):
    monkeypatch.setattr(CodeExtractor, "_setup_tesseract", lambda self: None)
    window = CodeExtractor()
    yield window
    window.close()


@pytest.fixture
def message_box_calls(monkeypatch):
    calls = []

    def fake_message_box(text, **kwargs):
        calls.append(text)
        return dialog.IDOK

    monkeypatch.setattr(dialog, "message_box", fake_message_box)
    return calls


def wait_for_ocr(window, timeout=10.0):
    """upload_image_and_extract runs OCR in a background thread; process Qt
    events until its result has been delivered back to the window."""
    deadline = time.monotonic() + timeout
    while window._ocr_running:
        assert time.monotonic() < deadline, "OCR did not finish in time"
        QApplication.processEvents()
        time.sleep(0.01)


def test_config_manager_load():
    config = ConfigManager()
    assert config.get('code_length') == 16
    assert config.get('confidence') == 0.85


def test_code_extractor_extract_codes_supports_overwrite_and_append(extractor, monkeypatch, tmp_path, message_box_calls):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "codes.txt").write_text("OLD1 CODE 0000 0000\n", encoding="utf-8")

    extractor.input_box.setPlainText("abcd1234efgh5678")
    extractor.extract_codes(overwrite=True)
    assert (tmp_path / "codes.txt").read_text(encoding="utf-8") == "ABCD 1234 EFGH 5678\n"

    extractor.input_box.setPlainText("WXYZ9876IJKL5432")
    extractor.extract_codes(overwrite=False)
    assert (tmp_path / "codes.txt").read_text(encoding="utf-8") == (
        "ABCD 1234 EFGH 5678\n"
        "WXYZ 9876 IJKL 5432\n"
    )
    assert len(message_box_calls) == 2


def test_extract_codes_writes_to_configured_codes_file(extractor, monkeypatch, tmp_path, message_box_calls):
    monkeypatch.chdir(tmp_path)
    extractor.config.config["codes_file"] = "my_codes.txt"

    extractor.input_box.setPlainText("ABCD 1234 EFGH 5678")
    extractor.extract_codes(overwrite=True)

    assert (tmp_path / "my_codes.txt").read_text(encoding="utf-8") == "ABCD 1234 EFGH 5678\n"
    assert not (tmp_path / "codes.txt").exists()


def test_upload_image_and_extract_appends_by_default(extractor, monkeypatch, tmp_path, message_box_calls):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "codes.txt").write_text("KEEP 1111 THIS 2222\n", encoding="utf-8")

    image = Image.new("RGB", (10, 10), color="white")
    monkeypatch.setattr("Codes.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("fake.png", ""))
    monkeypatch.setattr("Codes.Image.open", lambda *args, **kwargs: image)
    monkeypatch.setattr(extractor, "_ocr_image", lambda rotated: "ABCD 1234 EFGH 5678")

    extractor.upload_image_and_extract()

    wait_for_ocr(extractor)

    assert (tmp_path / "codes.txt").read_text(encoding="utf-8") == (
        "KEEP 1111 THIS 2222\n"
        "ABCD 1234 EFGH 5678\n"
    )
    assert "ABCD 1234 EFGH 5678" in message_box_calls[-1]


def test_upload_image_and_extract_can_overwrite(extractor, monkeypatch, tmp_path, message_box_calls):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "codes.txt").write_text("OLDX 1111 DATA 2222\n", encoding="utf-8")

    image = Image.new("RGB", (10, 10), color="white")
    monkeypatch.setattr("Codes.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("fake.png", ""))
    monkeypatch.setattr("Codes.Image.open", lambda *args, **kwargs: image)
    monkeypatch.setattr(extractor, "_ocr_image", lambda rotated: "WXYZ 9876 IJKL 5432")

    extractor.upload_image_and_extract(overwrite=True)

    wait_for_ocr(extractor)

    assert (tmp_path / "codes.txt").read_text(encoding="utf-8") == "WXYZ 9876 IJKL 5432\n"
    assert "WXYZ 9876 IJKL 5432" in message_box_calls[-1]


def test_manual_mode_indicator_starts_in_overwrite_with_first_click_hint(extractor):
    assert extractor.manual_overwrite is True
    assert extractor._first_extract_click_pending is True
    assert "Overwrite" in extractor.mode_label.text()
    assert "First click" in extractor.mode_label.text()
    assert extractor.toggle_mode_button.text() == "Switch to Append"


def test_extract_button_first_click_switches_to_append(extractor, monkeypatch):
    calls = []

    def fake_extract_codes(*, overwrite=True):
        calls.append(overwrite)

    monkeypatch.setattr(extractor, "extract_codes", fake_extract_codes)

    extractor.extract_button.click()

    assert calls == [False]
    assert extractor.manual_overwrite is False
    assert extractor._first_extract_click_pending is False
    assert extractor.mode_label.text() == "Manual Extract Mode: Append"
    assert extractor.toggle_mode_button.text() == "Switch to Overwrite"


def test_toggle_extract_mode_updates_indicator(extractor):
    extractor.toggle_mode_button.click()

    assert extractor.manual_overwrite is False
    assert extractor._first_extract_click_pending is False
    assert extractor.mode_label.text() == "Manual Extract Mode: Append"
    assert extractor.toggle_mode_button.text() == "Switch to Overwrite"


def test_code_extractor_reads_manual_overwrite_default_from_config(qapp, monkeypatch):
    config_values = {
        "manual_overwrite_default": False,
        "ocr_overwrite_default": False,
    }
    monkeypatch.setattr(CodeExtractor, "_setup_tesseract", lambda self: None)
    monkeypatch.setattr(ConfigManager, "get", lambda self, key: config_values.get(key))

    window = CodeExtractor()
    try:
        assert window.manual_overwrite is False
        assert window._first_extract_click_pending is False
        assert window.mode_label.text() == "Manual Extract Mode: Append"
    finally:
        window.close()


def test_upload_image_uses_ocr_overwrite_default_when_no_parameter(qapp, monkeypatch):
    config_values = {
        "manual_overwrite_default": True,
        "ocr_overwrite_default": True,
    }
    monkeypatch.setattr(CodeExtractor, "_setup_tesseract", lambda self: None)
    monkeypatch.setattr(ConfigManager, "get", lambda self, key: config_values.get(key))

    window = CodeExtractor()
    try:
        image = Image.new("RGB", (10, 10), color="white")
        monkeypatch.setattr("Codes.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("fake.png", ""))
        monkeypatch.setattr("Codes.Image.open", lambda *args, **kwargs: image)
        monkeypatch.setattr(window, "_ocr_image", lambda rotated: "ABCD 1234 EFGH 5678")

        write_overwrite_flags = []

        def fake_write_codes(codes, overwrite=True):
            write_overwrite_flags.append(overwrite)

        monkeypatch.setattr(window, "_write_codes", fake_write_codes)
        monkeypatch.setattr(dialog, "message_box", lambda *args, **kwargs: dialog.IDOK)

        window.upload_image_and_extract()

        wait_for_ocr(window)

        assert write_overwrite_flags == [True]
    finally:
        window.close()


def test_extract_codes_rejects_ocr_fragments_and_keeps_valid_groups(extractor):
    text = "FTERFB09CARDDATA IONWORLDFB09REDE Q7NL HU2Z CYMU UMZ5"
    codes = extractor._extract_codes_from_text(text)
    assert codes == ["Q7NL HU2Z CYMU UMZ5"]


def test_extract_codes_allows_single_compact_manual_input(extractor):
    extractor.input_box.setPlainText("abcd1234efgh5678")
    calls = []

    def fake_write_codes(codes, overwrite=True):
        calls.extend(codes)

    from dialog import IDOK

    def fake_message_box(*args, **kwargs):
        return IDOK

    extractor._write_codes = fake_write_codes
    dialog.message_box = fake_message_box

    extractor.extract_codes(overwrite=True)

    assert calls == ["ABCD 1234 EFGH 5678"]


def test_extract_codes_rejects_wordy_compact_false_positives(extractor):
    text = "1909DRAGBALLCARD WORKCARDGAMEF809 ABCD1234EFGH5678"
    codes = extractor._extract_codes_from_text(text, allow_compact=True, min_digits=1)
    assert codes == ["ABCD 1234 EFGH 5678"]


def test_extract_codes_compact_manual_input_rejects_wordy_string(extractor):
    extractor.input_box.setPlainText("WORKCARDGAMEF809")
    calls = []

    def fake_write_codes(codes, overwrite=True):
        calls.extend(codes)

    from dialog import IDOK

    def fake_message_box(*args, **kwargs):
        return IDOK

    extractor._write_codes = fake_write_codes
    dialog.message_box = fake_message_box

    extractor.extract_codes(overwrite=True)

    assert calls == []


def test_extract_codes_accepts_two_digit_grouped_codes(extractor):
    text = "GEXD NB4Z JCPJ BHZ5 WJFR NS4Z SQQD JHY2"
    codes = extractor._extract_codes_from_text(text, allow_compact=False, min_digits=2)
    assert codes == ["GEXD NB4Z JCPJ BHZ5", "WJFR NS4Z SQQD JHY2"]


def test_detect_card_regions_finds_grid_like_cards(extractor):
    # Boxes must be large enough to clear _detect_card_regions' own
    # min_width/min_height floors (120px/160px) after padding - a previous
    # version of this test used 100x160 boxes, which fell just short
    # (113px after padding) and always failed once actually run.
    image = Image.new("RGB", (700, 460), color="#202020")
    draw = ImageDraw.Draw(image)
    for box in (
        (20, 20, 160, 200),
        (190, 20, 330, 200),
        (20, 230, 160, 410),
        (190, 230, 330, 410),
    ):
        draw.rectangle(box, fill="white")

    regions = extractor._detect_card_regions(image)

    assert len(regions) == 4
    assert regions[0][0] < regions[0][2]
    assert regions[0][1] < regions[0][3]


def test_upload_image_and_extract_uses_segmented_card_ocr_without_mixing(extractor, monkeypatch, tmp_path, message_box_calls):
    monkeypatch.chdir(tmp_path)

    image = Image.new("RGB", (600, 420), color="white")
    monkeypatch.setattr("Codes.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("fake.png", ""))
    monkeypatch.setattr("Codes.Image.open", lambda *args, **kwargs: image)

    def fake_ocr_cards_in_image(rotated):
        if rotated.width == 600:
            return (
                "Use this code to unlock your in-game reward!\nABCD 1234 EFGH 5678\n\n"
                "Use this code to unlock your in-game reward!\nWXYZ 9876 IJKL 5432",
                ["ABCD 1234 EFGH 5678", "WXYZ 9876 IJKL 5432"],
            )
        return ("", [])

    monkeypatch.setattr(extractor, "_ocr_cards_in_image", fake_ocr_cards_in_image)
    monkeypatch.setattr(extractor, "_ocr_image", lambda rotated: "NOISY PAGE OCR")

    extractor.upload_image_and_extract(overwrite=True)

    wait_for_ocr(extractor)

    assert (tmp_path / "codes.txt").read_text(encoding="utf-8") == (
        "ABCD 1234 EFGH 5678\n"
        "WXYZ 9876 IJKL 5432\n"
    )
    assert "ABCD 1234 EFGH 5678" in extractor.input_box.toPlainText()
    assert "WXYZ 9876 IJKL 5432" in extractor.input_box.toPlainText()
    assert len(message_box_calls) == 1


def test_upload_runs_ocr_in_background_and_keeps_window_open(extractor, monkeypatch, tmp_path, message_box_calls):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("Codes.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("fake.png", ""))
    monkeypatch.setattr("Codes.Image.open", lambda *args, **kwargs: Image.new("RGB", (10, 10), "white"))
    release = threading.Event()
    ocr_threads = []

    def slow_ocr(image):
        ocr_threads.append(threading.current_thread())
        release.wait(timeout=10)
        return "ABCD 1234 EFGH 5678"

    monkeypatch.setattr(extractor, "_ocr_image", slow_ocr)
    write_threads = []
    original_write_codes = extractor._write_codes

    def recording_write_codes(codes, overwrite=True):
        write_threads.append(threading.current_thread())
        original_write_codes(codes, overwrite=overwrite)

    monkeypatch.setattr(extractor, "_write_codes", recording_write_codes)
    extractor.show()

    extractor.upload_image_and_extract(overwrite=True)

    # The call returns while OCR is still running. Nothing that could race
    # with it is usable, and the window refuses to close: main.py reads the
    # codes file as soon as it does.
    assert extractor._ocr_running
    assert not extractor.next_button.isEnabled()
    assert not extractor.upload_button.isEnabled()
    extractor.close()
    assert extractor.isVisible()

    release.set()
    wait_for_ocr(extractor)

    # OCR ran in the background, but the result (file write, widgets) was
    # handled back on the GUI thread.
    assert ocr_threads and threading.main_thread() not in ocr_threads
    assert write_threads == [threading.main_thread()]
    assert extractor.next_button.isEnabled()
    assert (tmp_path / "codes.txt").read_text(encoding="utf-8") == "ABCD 1234 EFGH 5678\n"
    extractor.close()
    assert not extractor.isVisible()


def test_upload_reports_ocr_errors_and_unlocks_window(extractor, monkeypatch, message_box_calls):
    monkeypatch.setattr("Codes.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("broken.png", ""))

    def broken_open(*args, **kwargs):
        raise OSError("cannot identify image file")

    monkeypatch.setattr("Codes.Image.open", broken_open)

    extractor.upload_image_and_extract()
    wait_for_ocr(extractor)

    assert message_box_calls == ["OCR failed: cannot identify image file"]
    assert extractor.upload_button.isEnabled()


def test_ocr_image_computes_confidence_once_per_variant(extractor, monkeypatch):
    calls = {"image_to_string": 0, "image_to_data": 0}
    lock = threading.Lock()

    def counting(name, result):
        def fake(*args, **kwargs):
            with lock:
                calls[name] += 1
            return result
        return fake

    monkeypatch.setattr("Codes.pytesseract.image_to_string", counting("image_to_string", ""))
    monkeypatch.setattr("Codes.pytesseract.image_to_data", counting("image_to_data", {"conf": []}))
    extractor.ocr_selection_mode = "text"

    assert extractor._ocr_image(Image.new("RGB", (40, 20), "white")) == ""

    # 3 variants x 3 configs for the text, the confidence once per variant
    # (it does not depend on the config) and no repeated call for the
    # empty-text fallback.
    assert calls == {"image_to_string": 9, "image_to_data": 3}


def test_ocr_image_keeps_first_combination_on_equal_scores(extractor, monkeypatch):
    # Precondition: both texts score the same.
    assert extractor._text_quality_score("REDEEM FIRST") == extractor._text_quality_score("REDEEM OTHER")

    def fake_image_to_string(image, config=""):
        if image.mode == "RGB" and "--psm 6" in config:
            time.sleep(0.2)  # the first combination finishes last
            return "REDEEM FIRST"
        return "REDEEM OTHER"

    monkeypatch.setattr("Codes.pytesseract.image_to_string", fake_image_to_string)
    monkeypatch.setattr("Codes.pytesseract.image_to_data", lambda *args, **kwargs: {"conf": ["90"]})
    extractor.ocr_selection_mode = "text"

    # Results are evaluated in submission order, not completion order, so
    # ties are broken exactly as in the old sequential loop.
    assert extractor._ocr_image(Image.new("RGB", (40, 20), "white")) == "REDEEM FIRST"


def test_configure_tesseract_limits_tesseract_to_one_thread(monkeypatch):
    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", pytesseract.pytesseract.tesseract_cmd)

    monkeypatch.delenv("OMP_THREAD_LIMIT", raising=False)
    configure_tesseract()
    assert os.environ["OMP_THREAD_LIMIT"] == "1"

    # An explicit user setting wins.
    monkeypatch.setenv("OMP_THREAD_LIMIT", "3")
    configure_tesseract()
    assert os.environ["OMP_THREAD_LIMIT"] == "3"


def test_extract_codes_does_not_join_groups_across_lines(extractor):
    # A code whose last group was cut off must not be completed with the
    # first word of the next line.
    assert extractor._extract_codes_from_text("Q7NL HU2Z CYMU\nCode redemption deadline") == []
    assert extractor._extract_codes_from_text("Q7NL HU2Z CYMU UMZ5\nCode redemption deadline") == ["Q7NL HU2Z CYMU UMZ5"]


@pytest.mark.parametrize("text", [
    "ABCD-EF3Z-GHJK-LMN5",
    "ABCD\tEF3Z\tGHJK\tLMN5",
    "ABCD\u00a0EF3Z\u00a0GHJK\u00a0LMN5",  # non-breaking spaces from pasted web text
])
def test_extract_codes_accepts_horizontal_separators(extractor, text):
    assert extractor._extract_codes_from_text(text) == ["ABCD EF3Z GHJK LMN5"]


def test_extract_codes_accepts_grouped_codes_with_digits_only_in_second_group(extractor):
    # Every known real code has a digit in its second group; that is enough
    # for cleanly grouped text, even if no other group has a digit.
    assert extractor._extract_codes_from_text("ABCD EF3Z GHJK LMNP") == ["ABCD EF3Z GHJK LMNP"]


def test_extract_codes_still_rejects_wordy_text_and_glued_fragments(extractor):
    # Digit only in the first group: card text, not a code.
    assert extractor._extract_codes_from_text("AFTER FB09 CARD DATA WILL BE") == []
    # Glued OCR fragment with a digit in its second group: the relaxed rule
    # applies to cleanly grouped text only.
    assert extractor._extract_codes_from_text("FTERFB09CARDDATA", allow_compact=True, min_digits=1) == []


def test_extract_codes_reads_zero_as_letter_o(extractor):
    # Real codes never contain 0 but do contain O, which OCR often reads as 0.
    assert extractor._extract_codes_from_text("03EF Z84Z NW6C R245") == ["O3EF Z84Z NW6C R245"]
    assert extractor._extract_codes_from_text("03EFZ84ZNW6CR245", allow_compact=True, min_digits=1) == ["O3EF Z84Z NW6C R245"]


def test_upload_falls_back_to_whole_image_when_card_segmentation_finds_no_codes(extractor, monkeypatch, tmp_path, message_box_calls):
    # A single card filling the photo can be mis-segmented into a blank
    # "card"; its unreadable text must not replace the whole-image OCR.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("Codes.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("fake.png", ""))
    monkeypatch.setattr("Codes.Image.open", lambda *args, **kwargs: Image.new("RGB", (900, 600), "white"))
    monkeypatch.setattr(extractor, "_ocr_cards_in_image", lambda rotated: ("F ES Qe QS ww", []))
    monkeypatch.setattr(extractor, "_ocr_image", lambda rotated: "Use this code to unlock\nGO4D KX7Z PLMO R2S5")

    extractor.upload_image_and_extract(overwrite=True)
    wait_for_ocr(extractor)

    assert (tmp_path / "codes.txt").read_text(encoding="utf-8") == "GO4D KX7Z PLMO R2S5\n"


def _upright_test_image():
    # Portrait image with a red marker in its top-left corner, so the
    # orientation the OCR gets to see can be checked.
    image = Image.new("RGB", (30, 60), "white")
    ImageDraw.Draw(image).rectangle((0, 0, 9, 9), fill="red")
    return image


def _is_upright(image):
    return image.size == (30, 60) and image.getpixel((2, 2)) == (255, 0, 0)


@pytest.mark.parametrize("orientation, stored_as", [
    (3, Image.Transpose.ROTATE_180),
    (6, Image.Transpose.ROTATE_90),   # phone held upright, the most common case
    (8, Image.Transpose.ROTATE_270),
])
def test_ocr_uses_photo_as_displayed_on_the_phone(extractor, monkeypatch, tmp_path, orientation, stored_as):
    # Phones store the pixels rotated and record the rotation in EXIF.
    exif = Image.Exif()
    exif[0x0112] = orientation
    path = tmp_path / "photo.png"
    _upright_test_image().transpose(stored_as).save(path, exif=exif)
    seen = []

    def fake_ocr(image):
        seen.append(image)
        return "Use this code\nGO4D KX7Z PLMO R2S5" if _is_upright(image) else ""

    monkeypatch.setattr(extractor, "_ocr_image", fake_ocr)

    display_text, codes = extractor._ocr_file(str(path))

    assert _is_upright(seen[0])  # the first (0 degree) pass already sees it upright
    assert codes == ["GO4D KX7Z PLMO R2S5"]
    assert display_text.startswith("[0°]")


def test_ocr_tries_upside_down_only_when_nothing_was_found(extractor, monkeypatch, tmp_path):
    # Cards lying upside down in a photo without EXIF rotation.
    path = tmp_path / "photo.png"
    _upright_test_image().transpose(Image.Transpose.ROTATE_180).save(path)
    calls = []

    def fake_ocr(image):
        calls.append(image)
        return "Use this code\nGO4D KX7Z PLMO R2S5" if _is_upright(image) else ""

    monkeypatch.setattr(extractor, "_ocr_image", fake_ocr)

    display_text, codes = extractor._ocr_file(str(path))

    assert codes == ["GO4D KX7Z PLMO R2S5"]
    assert display_text.startswith("[180°]")
    assert len(calls) == 4  # 0, 90, then 180 and 270


def test_ocr_skips_extra_angles_when_codes_were_found(extractor, monkeypatch, tmp_path):
    path = tmp_path / "photo.png"
    _upright_test_image().save(path)
    calls = []

    def fake_ocr(image):
        calls.append(image)
        return "Use this code\nGO4D KX7Z PLMO R2S5" if _is_upright(image) else ""

    monkeypatch.setattr(extractor, "_ocr_image", fake_ocr)

    _, codes = extractor._ocr_file(str(path))

    assert codes == ["GO4D KX7Z PLMO R2S5"]
    assert len(calls) == 2  # only 0 and 90 degrees
