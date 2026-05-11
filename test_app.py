import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

import dialog
from config_manager import ConfigManager
from Codes import CodeExtractor


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


def test_upload_image_and_extract_appends_by_default(extractor, monkeypatch, tmp_path, message_box_calls):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "codes.txt").write_text("KEEP 1111 THIS 2222\n", encoding="utf-8")

    image = Image.new("RGB", (10, 10), color="white")
    monkeypatch.setattr("Codes.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("fake.png", ""))
    monkeypatch.setattr("Codes.Image.open", lambda *args, **kwargs: image)
    monkeypatch.setattr(extractor, "_ocr_image", lambda rotated: "ABCD 1234 EFGH 5678")

    extractor.upload_image_and_extract()

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
    image = Image.new("RGB", (600, 420), color="#202020")
    draw = ImageDraw.Draw(image)
    for box in (
        (20, 20, 120, 180),
        (140, 20, 240, 180),
        (20, 210, 120, 390),
        (140, 210, 240, 390),
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

    assert (tmp_path / "codes.txt").read_text(encoding="utf-8") == (
        "ABCD 1234 EFGH 5678\n"
        "WXYZ 9876 IJKL 5432\n"
    )
    assert "ABCD 1234 EFGH 5678" in extractor.input_box.toPlainText()
    assert "WXYZ 9876 IJKL 5432" in extractor.input_box.toPlainText()
    assert len(message_box_calls) == 1
