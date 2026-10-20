"""Find the game window on Windows (pygetwindow) and macOS (Quartz).

Run ``python game_window.py`` to list all open windows, e.g. to find the
right ``window_title`` for config.yaml.
"""
from __future__ import annotations

import sys
from typing import Any

IS_MACOS = sys.platform == "darwin"

# Keys of the dictionaries returned by Quartz.CGWindowListCopyWindowInfo
# (the Quartz constants of the same name have exactly these values).
_OWNER_NAME = "kCGWindowOwnerName"
_WINDOW_NAME = "kCGWindowName"
_LAYER = "kCGWindowLayer"
_NUMBER = "kCGWindowNumber"
_BOUNDS = "kCGWindowBounds"


class MacWindow:
    """A macOS window with the geometry attributes of a pygetwindow window.

    Values are in screen points and re-read on every access, so they stay
    correct if the window is moved, like pygetwindow's on Windows.
    """

    def __init__(self, window_id: int) -> None:
        self.window_id = window_id

    def _bounds(self) -> dict[str, float]:
        import Quartz

        infos = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionIncludingWindow, self.window_id)
        if not infos:
            raise RuntimeError("The game window was closed.")
        return infos[0][_BOUNDS]

    @property
    def left(self) -> int:
        return int(self._bounds()["X"])

    @property
    def top(self) -> int:
        return int(self._bounds()["Y"])

    @property
    def width(self) -> int:
        return int(self._bounds()["Width"])

    @property
    def height(self) -> int:
        return int(self._bounds()["Height"])

    @property
    def right(self) -> int:
        bounds = self._bounds()
        return int(bounds["X"] + bounds["Width"])

    @property
    def bottom(self) -> int:
        bounds = self._bounds()
        return int(bounds["Y"] + bounds["Height"])


def _mac_window_infos() -> list[Any]:
    import Quartz

    infos = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    # Layer 0 holds normal app windows; skip the menu bar, Dock, overlays, ...
    return [info for info in (infos or []) if info.get(_LAYER, 0) == 0]


def _match_mac_window(infos: list[Any], title: str) -> int | None:
    """Number of the frontmost window whose app or window name contains
    `title`, ignoring case like pygetwindow does on Windows.

    The app name is always available; macOS only reveals window names to
    apps with the Screen Recording permission.
    """
    needle = title.upper()
    for info in infos:
        names = (info.get(_OWNER_NAME) or "", info.get(_WINDOW_NAME) or "")
        if any(needle in str(name).upper() for name in names):
            return int(info[_NUMBER])
    return None


def find_game_window(title: str) -> Any | None:
    if IS_MACOS:
        window_id = _match_mac_window(_mac_window_infos(), title)
        return MacWindow(window_id) if window_id is not None else None

    import pygetwindow

    windows = pygetwindow.getWindowsWithTitle(title)
    return windows[0] if windows else None


def list_windows() -> list[str]:
    if IS_MACOS:
        return [
            f"{info.get(_OWNER_NAME) or ''} | {info.get(_WINDOW_NAME) or ''}"
            for info in _mac_window_infos()
        ]

    import pygetwindow

    return [title for title in pygetwindow.getAllTitles() if title]


def missing_macos_permissions() -> list[str]:
    """macOS privacy permissions DBFW needs but does not have (empty elsewhere).

    Without Screen Recording, screenshots only show the desktop, so the game
    is never found; without Accessibility, clicks and typing are dropped.
    """
    if not IS_MACOS:
        return []

    import Quartz
    from ApplicationServices import AXIsProcessTrusted

    missing = []
    if not Quartz.CGPreflightScreenCaptureAccess():
        missing.append("Screen Recording")
    if not AXIsProcessTrusted():
        missing.append("Accessibility")
    return missing


def request_macos_permissions() -> None:
    """Ask macOS to show its permission prompts. This also lists the app in
    System Settings, so the user only has to switch it on there."""
    if not IS_MACOS:
        return

    import Quartz
    from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt

    Quartz.CGRequestScreenCaptureAccess()
    AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})


if __name__ == "__main__":
    if IS_MACOS and "Screen Recording" in missing_macos_permissions():
        print("Note: without the Screen Recording permission macOS hides window names; only app names are listed.\n")
    for line in list_windows():
        print(line)
