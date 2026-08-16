from PySide6.QtWidgets import QApplication, QMessageBox, QMainWindow
from PySide6.QtGui import QIcon
from pathlib import Path
import sys

# Resources folder
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # PyInstaller temp path
    RESOURCES = Path(sys._MEIPASS) / 'res'
else:
    # Local res folder
    RESOURCES = Path(__file__).parent / 'res'

LOGO = RESOURCES / 'logo.ico'

# Icons
ICON_STOP = QMessageBox.Icon.Critical
ICON_EXCLAMATION = QMessageBox.Icon.Warning
ICON_INFORMATION = QMessageBox.Icon.Information

# Styles
STYLE_OK = QMessageBox.StandardButton.Ok
STYLE_OKCANCEL = QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
STYLE_Q = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No

# Return Values
IDOK = QMessageBox.StandardButton.Ok.value
IDCANCEL = QMessageBox.StandardButton.Cancel.value
IDYES = QMessageBox.StandardButton.Yes.value
IDNO = QMessageBox.StandardButton.No.value

def message_box(text, icon=ICON_INFORMATION, style=STYLE_OK, title='DBSFW Code Injector') -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Create a dummy main window to set the taskbar icon
    main_window = QMainWindow()
    main_window.setWindowIcon(QIcon(str(LOGO)))
    main_window.hide()  # Hide the main window since we only need it for the icon

    # Create and set up the message box
    msg_box = QMessageBox()
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(icon)
    msg_box.setWindowIcon(QIcon(str(LOGO)))  # Ensure the message box has the icon too
    
    # Set the buttons based on style
    msg_box.setStandardButtons(style)
    
    # Set default button for specific styles
    if style == STYLE_OKCANCEL:
        msg_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    elif style == STYLE_Q:
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

    # Execute the message box and wait for user action
    result = msg_box.exec()

    # Return corresponding result based on the button clicked
    return result

class CustomException(Exception):
    """Carries a user-facing error message and dialog icon.

    Does not show a dialog or exit by itself; the entrypoint that
    catches it is responsible for that (see main.py).
    """
    def __init__(self, err, icon=ICON_STOP):
        super().__init__(err)
        self.icon = icon
