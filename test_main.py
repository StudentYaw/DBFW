import os
import sys
import types
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image

# pyautogui and pygetwindow only import on a real Windows desktop. CI runs on
# Windows; stub them elsewhere so main.py's logic can be tested on any OS.
# Every test replaces main.pyautogui and the screen-touching methods anyway,
# so no real mouse or keyboard input is ever sent.
for _name in ("pyautogui", "pygetwindow"):
    try:
        __import__(_name)
    except Exception:
        sys.modules[_name] = types.ModuleType(_name)

import main
from dialog import CustomException, IDOK


class FakeWindow:
    left, top, right, bottom = 10, 20, 1930, 1100
    width, height = 1920, 1080


@pytest.fixture
def injector(monkeypatch, tmp_path):
    monkeypatch.setattr(main.CodeInjector, "_setup_tesseract", lambda self: None)
    monkeypatch.setattr(main, "pyautogui", mock.MagicMock())
    monkeypatch.setattr(main, "message_box", mock.MagicMock(return_value=IDOK))
    injector = main.CodeInjector()
    monkeypatch.chdir(tmp_path)
    injector.config.config.update(
        codes_file="codes.txt",
        codes_err_file="codes_with_errors.txt",
        max_errors=5,
    )
    return injector


def _stub_screen(injector, monkeypatch, ocr_results, events):
    """Replace every step that touches the game with fakes logging to `events`."""
    monkeypatch.setattr(injector, "_get_game_window", lambda: FakeWindow())
    monkeypatch.setattr(injector, "_prepare_scaled_images", lambda factor: None)
    monkeypatch.setattr(main, "run_codes", lambda: None)
    monkeypatch.setattr(injector, "_submit_code", lambda code: events.append(("submit", code)))
    monkeypatch.setattr(injector, "_close_result_dialog", lambda: events.append(("close",)))
    results = iter(ocr_results)
    monkeypatch.setattr(injector, "ocr_check_text", lambda region=None: next(results))
    main.message_box.side_effect = lambda text, **kwargs: events.append(("message", text)) or IDOK


def test_error_limit_is_counted_per_round(injector, monkeypatch):
    injector.config.config["max_errors"] = 2
    events = []
    _stub_screen(injector, monkeypatch, ["invalid", "invalid", "invalid", "success"], events)
    rounds = iter([
        ["AAAA1111BBBB2222", "CCCC3333DDDD4444", "EEEE5555FFFF6666"],
        ["GGGG7777HHHH8888", "IIII9999JJJJ0000"],
    ])
    monkeypatch.setattr(injector, "_load_and_validate_codes", lambda: next(rounds))
    monkeypatch.setattr(injector, "_confirm_start", lambda codes: None)
    reports = []

    def report(errors):
        reports.append((injector.counter_err, injector.counter_suc))
        injector.not_done = len(reports) < 2

    monkeypatch.setattr(injector, "_report_results", report)

    injector.run_injection()

    submitted = [event[1] for event in events if event[0] == "submit"]
    # Round 1 stops at the limit; round 2 starts from zero and gets through
    # both codes instead of aborting on its first error.
    assert submitted == [
        "AAAA1111BBBB2222", "CCCC3333DDDD4444",
        "GGGG7777HHHH8888", "IIII9999JJJJ0000",
    ]
    assert reports == [(2, 0), (1, 1)]
    assert sum(event[0] == "message" for event in events) == 1


def test_result_dialog_is_closed_before_aborting_on_error_limit(injector, monkeypatch):
    injector.config.config["max_errors"] = 2
    events = []
    _stub_screen(injector, monkeypatch, ["invalid", "invalid"], events)
    codes = ["AAAA1111BBBB2222", "CCCC3333DDDD4444", "EEEE5555FFFF6666"]

    assert injector._process_codes(codes) is True

    assert events[-2:] == [("close",), ("message", "Exceeded the maximum number of fails!")]
    assert codes == ["EEEE5555FFFF6666"]


def _fail_on_second_call(result=None):
    calls = []

    def step(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise RuntimeError("step failed")
        return result

    return step


@pytest.mark.parametrize("failing_step, result", [
    ("_submit_code", None),
    ("ocr_check_text", "success"),
])
def test_unhandled_codes_are_saved_when_a_step_fails(injector, monkeypatch, tmp_path, failing_step, result):
    (tmp_path / "codes.txt").write_text(
        "AAAA 1111 BBBB 2222\nCCCC 3333 DDDD 4444\nEEEE 5555 FFFF 6666\n", encoding="utf-8"
    )
    _stub_screen(injector, monkeypatch, ["success"] * 3, [])
    monkeypatch.setattr(injector, failing_step, _fail_on_second_call(result))

    with pytest.raises(RuntimeError):
        injector.run_injection()

    # The first code went through; the one that failed mid-way stays queued.
    assert (tmp_path / "codes.txt").read_text(encoding="utf-8") == (
        "CCCC3333DDDD4444\n"
        "EEEE5555FFFF6666\n"
    )


def test_ocr_reads_only_the_game_window(injector, monkeypatch):
    regions = []

    def fake_grab(bbox=None):
        regions.append(bbox)
        return Image.new("RGB", (40, 20), "white")

    monkeypatch.setattr(main.ImageGrab, "grab", fake_grab)
    monkeypatch.setattr(main.pytesseract, "image_to_string", lambda image, config="": "Code redeemed successfully")
    monkeypatch.setattr(injector, "_submit_code", lambda code: None)
    monkeypatch.setattr(injector, "_close_result_dialog", lambda: None)
    injector.window = FakeWindow()

    assert injector._process_codes(["AAAA1111BBBB2222"]) is False
    assert regions == [(10, 20, 1930, 1100)]


@pytest.mark.parametrize("text, expected", [
    ("You have already entered this serial code.", "alreadyused"),
    ("The serial code is invalid.", "invalid"),
    ("Rewards received!", "success"),
    ("Loading...", "unknown"),
])
def test_ocr_check_text_classifies_result(injector, monkeypatch, text, expected):
    monkeypatch.setattr(main.ImageGrab, "grab", lambda bbox=None: Image.new("RGB", (40, 20), "white"))
    monkeypatch.setattr(main.pytesseract, "image_to_string", lambda image, config="": text)

    assert injector.ocr_check_text((0, 0, 40, 20)) == expected


def test_main_shows_unexpected_errors_instead_of_crashing(monkeypatch):
    shown = []
    monkeypatch.setattr(main, "message_box", lambda text, **kwargs: shown.append(text))
    monkeypatch.setattr(main.CodeInjector, "_setup_tesseract", lambda self: None)

    def run_injection(self):
        raise RuntimeError("tesseract is not installed")

    monkeypatch.setattr(main.CodeInjector, "run_injection", run_injection)

    with pytest.raises(SystemExit) as exc:
        main.main()

    assert exc.value.code == 1
    assert "tesseract is not installed" in shown[0]


def test_main_still_shows_custom_exceptions_with_their_icon(monkeypatch):
    shown = []
    monkeypatch.setattr(main, "message_box", lambda text, **kwargs: shown.append((text, kwargs.get("icon"))))
    monkeypatch.setattr(main.CodeInjector, "_setup_tesseract", lambda self: None)

    def run_injection(self):
        raise CustomException("Codes section is not opened")

    monkeypatch.setattr(main.CodeInjector, "run_injection", run_injection)

    with pytest.raises(SystemExit):
        main.main()

    assert shown == [("Codes section is not opened", main.ICON_STOP)]
