import tkinter as tk
from tkinter import messagebox
import sys

# Icons
ICON_STOP = 'error'
ICON_EXCLAMATION = 'warning'
ICON_INFORMATION = 'info'

# Styles
STYLE_OK = 'ok'
STYLE_OKCANCEL = 'okcancel'
STYLE_Q = 'Yesorno'

# Return Value
IDOK = 1
IDCANCEL = 2
IDYES = 3
IDNO = 4

def message_box(text, icon=ICON_INFORMATION, style=STYLE_OK, title='DBSFW Code Enjector') -> int:
    # Erstelle ein Hauptfenster, das nicht angezeigt wird
    dialog = tk.Tk()
    dialog.withdraw()  # Hauptfenster ausblenden
    if style == STYLE_Q:
        result = messagebox.askyesno(title, text, icon=icon)
        return IDYES if result else IDNO  # IDOK oder IDCANCEL
    
    # Message Box anzeigen und den Rückgabewert speichern
    if style == STYLE_OKCANCEL:
        result = messagebox.askokcancel(title, text, icon=icon)
        return IDOK if result else IDCANCEL  # IDOK oder IDCANCEL
    else:
        messagebox.showinfo(title, text, icon=icon)
        return IDOK  # Nur OK
    
class CustomException(Exception):
    def __init__(self, err, icon=ICON_STOP):
        super().__init__(err)
        message_box(text=err, icon=icon)
        sys.exit()
