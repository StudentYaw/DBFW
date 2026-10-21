import os
import sys
import types
from collections import namedtuple
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image

# pyautogui only imports with a desktop session (CI runs on Windows and
# macOS); stub it elsewhere so main.py's logic can be tested on any OS.
# Every test replaces main.pyautogui and the screen-touching methods anyway,
# so no real mouse or keyboard input is ever sent.
try:
    __import__("pyautogui")
except Exception:
    sys.modules["pyautogui"] = types.ModuleType("pyautogui")

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
    # Default to the Windows code paths, also when the suite runs on macOS;
    # the macOS tests switch them on explicitly.
    monkeypatch.setattr(main, "IS_MACOS", False)
    monkeypatch.setattr(main.game_window, "missing_macos_permissions", lambda: [])
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


def test_duplicate_codes_are_submitted_once(injector, monkeypatch, tmp_path):
    # The Code Extractor appends, so after an aborted round wrote the codes
    # back (without spaces) the same codes can be added again (with spaces).
    (tmp_path / "codes.txt").write_text(
        "AAAA1111BBBB2222\nCCCC3333DDDD4444\nAAAA 1111 BBBB 2222\ncccc 3333 dddd 4444\n", encoding="utf-8"
    )
    events = []
    _stub_screen(injector, monkeypatch, ["success"] * 4, events)
    monkeypatch.setattr(injector, "_report_results", lambda errors: setattr(injector, "not_done", False))

    injector.run_injection()

    assert [event[1] for event in events if event[0] == "submit"] == ["AAAA1111BBBB2222", "CCCC3333DDDD4444"]
    assert (tmp_path / "codes.txt").read_text(encoding="utf-8") == ""


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


Box = namedtuple("Box", "left top width height")


def test_retina_click_positions_are_converted_to_points(injector):
    # locateOnScreen() reports screenshot pixels; on a Retina Mac clicks take
    # points, i.e. half of that.
    gui = main.pyautogui
    gui.ImageNotFoundException = type("ImageNotFoundException", (Exception,), {})
    boxes = {"textbox": Box(200, 100, 100, 40), "confirm": Box(400, 300, 60, 20)}
    gui.locateOnScreen.side_effect = lambda path, confidence: boxes[Path(path).stem]
    gui.center.side_effect = lambda box: (box.left + box.width / 2, box.top + box.height / 2)
    injector.scaled_images = {"textbox": Path("textbox"), "confirm": Path("confirm")}
    injector.screen_scale = 2.0

    injector._submit_code("AAAA1111BBBB2222")

    clicks = [click.args for click in gui.click.call_args_list]
    assert clicks == [(105.0, 60.0), (105.0, 60.0), (215.0, 155.0)]


@pytest.mark.parametrize("screen_scale, expected", [(1.0, 0.5), (2.0, 1.0)])
def test_template_scaling_uses_the_window_size_in_screenshot_pixels(injector, screen_scale, expected):
    class Window:  # 960x540 points: 1920x1080 pixels on a Retina display
        width, height = 960, 540

    injector.screen_scale = screen_scale

    assert injector._compute_scaling_factor(Window()) == expected


def test_template_scaling_ignores_the_black_bars_of_a_16_10_window(injector):
    # Full-screen game on a 16" MacBook Pro: 3456x2168 pixels, of which the
    # game's 16:9 picture uses 3456x1944 (1.8x the 1920x1080 templates).
    class Window:
        width, height = 1728, 1084

    injector.screen_scale = 2.0

    assert injector._compute_scaling_factor(Window()) == pytest.approx(1.8)


@pytest.mark.parametrize("is_macos, modifier", [(False, "ctrl"), (True, "command")])
def test_select_all_uses_the_platform_modifier(injector, monkeypatch, is_macos, modifier):
    monkeypatch.setattr(main, "IS_MACOS", is_macos)
    monkeypatch.setattr(main.game_window, "type_text", mock.MagicMock())

    injector._enter_code("AAAA 1111 BBBB 2222")

    main.pyautogui.hotkey.assert_called_once_with(modifier, "a")
    if is_macos:
        main.game_window.type_text.assert_called_once_with("AAAA1111BBBB2222", 0.03)
        main.pyautogui.write.assert_not_called()
    else:
        main.pyautogui.write.assert_called_once_with("AAAA1111BBBB2222", interval=0.03)


def test_ocr_on_macos_crops_a_full_resolution_screenshot(injector, monkeypatch):
    monkeypatch.setattr(main, "IS_MACOS", True)
    injector.screen_scale = 2.0
    grabs = []
    ocr_sizes = []

    def fake_grab(bbox=None):
        grabs.append(bbox)
        return Image.new("L", (3024, 1964), "white")

    monkeypatch.setattr(main.ImageGrab, "grab", fake_grab)
    monkeypatch.setattr(main.pytesseract, "image_to_string", lambda image, config="": ocr_sizes.append(image.size) or "")

    injector.ocr_check_text((10, 20, 110, 70))

    # The whole screen is grabbed at full resolution and the window region,
    # given in points, is cut out in pixels.
    assert grabs == [None]
    assert ocr_sizes == [(200, 100)]


def test_screen_scale_on_macos_compares_screenshot_pixels_to_points(injector, monkeypatch):
    monkeypatch.setattr(main, "IS_MACOS", True)
    main.pyautogui.screenshot.return_value = Image.new("L", (3024, 1964))
    main.pyautogui.size.return_value = (1512, 982)

    assert injector._detect_screen_scale() == 2.0


def test_screen_scale_is_one_outside_macos(injector):
    assert injector._detect_screen_scale() == 1.0
    main.pyautogui.screenshot.assert_not_called()


def test_missing_macos_permissions_stop_before_touching_the_game(injector, monkeypatch):
    requested = []
    monkeypatch.setattr(main.game_window, "missing_macos_permissions", lambda: ["Screen Recording", "Accessibility"])
    monkeypatch.setattr(main.game_window, "request_macos_permissions", lambda: requested.append(True))
    monkeypatch.setattr(injector, "_get_game_window", mock.MagicMock())

    with pytest.raises(CustomException) as exc:
        injector.run_injection()

    assert "Screen Recording, Accessibility" in str(exc.value)
    assert "System Settings" in str(exc.value)
    assert requested == [True]
    injector._get_game_window.assert_not_called()


def test_game_window_is_looked_up_by_the_configured_title(injector, monkeypatch):
    titles = []
    monkeypatch.setattr(main.game_window, "find_game_window", lambda title: titles.append(title))
    injector.config.config["window_title"] = "Fusion World"

    with pytest.raises(CustomException, match="Game is not opened"):
        injector._get_game_window()

    assert titles == ["Fusion World"]
