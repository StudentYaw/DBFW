import sys
import types

import pytest

import game_window


def _info(owner, name="", number=1, layer=0):
    return {
        "kCGWindowOwnerName": owner,
        "kCGWindowName": name,
        "kCGWindowNumber": number,
        "kCGWindowLayer": layer,
    }


def _fake_quartz(window_list=(), bounds_by_id=None):
    def copy_window_info(options, window_id):
        if window_id == 0:  # kCGNullWindowID: list all windows
            return list(window_list)
        bounds = (bounds_by_id or {}).get(window_id)
        return [{"kCGWindowBounds": bounds}] if bounds else []

    return types.SimpleNamespace(
        kCGWindowListOptionOnScreenOnly=1,
        kCGWindowListExcludeDesktopElements=16,
        kCGWindowListOptionIncludingWindow=8,
        kCGNullWindowID=0,
        CGWindowListCopyWindowInfo=copy_window_info,
    )


def test_mac_window_matches_app_name_ignoring_case():
    infos = [_info("Finder", number=1), _info("dbscgfw", number=7)]
    assert game_window._match_mac_window(infos, "DBSCGFW") == 7


def test_mac_window_matches_window_name():
    infos = [_info("Some App", "DBSCGFW", number=3)]
    assert game_window._match_mac_window(infos, "dbscgfw") == 3


def test_mac_window_matches_by_app_name_without_window_names():
    # Without the Screen Recording permission macOS leaves out kCGWindowName.
    infos = [{"kCGWindowOwnerName": "DBSCGFW", "kCGWindowNumber": 5, "kCGWindowLayer": 0}]
    assert game_window._match_mac_window(infos, "DBSCGFW") == 5


def test_mac_window_prefers_frontmost_match():
    infos = [_info("DBSCGFW", number=2), _info("DBSCGFW", number=9)]
    assert game_window._match_mac_window(infos, "DBSCGFW") == 2
    assert game_window._match_mac_window(infos, "Other Game") is None


def test_mac_window_list_skips_menu_bar_and_overlays(monkeypatch):
    quartz = _fake_quartz([_info("Control Center", number=1, layer=25), _info("DBSCGFW", number=2)])
    monkeypatch.setitem(sys.modules, "Quartz", quartz)

    assert [info["kCGWindowNumber"] for info in game_window._mac_window_infos()] == [2]


def test_find_game_window_on_macos(monkeypatch):
    monkeypatch.setattr(game_window, "IS_MACOS", True)
    monkeypatch.setitem(sys.modules, "Quartz", _fake_quartz([_info("Finder", number=1), _info("DBSCGFW", number=2)]))

    window = game_window.find_game_window("DBSCGFW")

    assert isinstance(window, game_window.MacWindow)
    assert window.window_id == 2
    assert game_window.find_game_window("Other Game") is None


def test_mac_window_reads_its_bounds_live(monkeypatch):
    bounds = {"X": 100.0, "Y": 50.0, "Width": 1512.0, "Height": 945.0}
    monkeypatch.setitem(sys.modules, "Quartz", _fake_quartz(bounds_by_id={42: bounds}))
    window = game_window.MacWindow(42)

    assert (window.left, window.top, window.right, window.bottom) == (100, 50, 1612, 995)
    assert (window.width, window.height) == (1512, 945)

    bounds["X"] = 300.0  # the window was moved
    assert window.left == 300


def test_mac_window_reports_a_closed_window(monkeypatch):
    monkeypatch.setitem(sys.modules, "Quartz", _fake_quartz())

    with pytest.raises(RuntimeError, match="closed"):
        game_window.MacWindow(42).left


def test_permissions_are_not_checked_outside_macos(monkeypatch):
    monkeypatch.setattr(game_window, "IS_MACOS", False)
    assert game_window.missing_macos_permissions() == []


@pytest.mark.skipif(sys.platform != "darwin", reason="needs the real macOS APIs")
def test_macos_apis_are_callable():
    # Runs on the macOS CI runner against the real pyobjc bindings to catch
    # wrong names or imports. The runner has neither the game nor the
    # permissions, so only the shape of the results is checked.
    __import__("pyautogui")  # main.py needs it; test_main.py would stub it
    assert game_window.find_game_window("no window is called this 7f3e") is None
    assert all(isinstance(line, str) for line in game_window.list_windows())
    assert set(game_window.missing_macos_permissions()) <= {"Screen Recording", "Accessibility"}
