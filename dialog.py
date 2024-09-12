import ctypes
import sys

# Modality
MB_SYSTEMMODAL = 0x00001000

# Icon
MB_ICONSTOP = 0x00000010
MB_ICONEXCLAMATION = 0x00000030
MB_ICONINFORMATION = 0x00000040

# Style
MB_OK = 0x00000000
MB_OKCANCEL = 0x00000001

# Return Value
IDOK = 1
IDCANCEL = 2


def message_box(text, icon=MB_ICONINFORMATION, style=MB_OK, title='DBSFW Code Enjector') -> int:
    return ctypes.windll.user32.MessageBoxW(None, str(text), title, icon | style | MB_SYSTEMMODAL)


class CustomException(Exception):
    def __init__(self, err, icon=MB_ICONSTOP):
        super().__init__(err)
        message_box(text=err, icon=icon)
        sys.exit()
