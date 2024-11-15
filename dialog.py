from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow
from PyQt5.QtGui import QIcon
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
ICON_STOP = QMessageBox.Critical
ICON_EXCLAMATION = QMessageBox.Warning
ICON_INFORMATION = QMessageBox.Information

# Styles
STYLE_OK = QMessageBox.Ok
STYLE_OKCANCEL = QMessageBox.Ok | QMessageBox.Cancel
STYLE_Q = QMessageBox.Yes | QMessageBox.No

# Return Values
IDOK = 1
IDCANCEL = 2
IDYES = 3
IDNO = 4

def message_box(text, icon=ICON_INFORMATION, style=STYLE_OK, title='DBSFW Code Enjector') -> int:
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
        msg_box.setDefaultButton(QMessageBox.Cancel)
    elif style == STYLE_Q:
        msg_box.setDefaultButton(QMessageBox.No)
    
    # Execute the message box and wait for user action
    result = msg_box.exec_()

    # Return corresponding result based on the button clicked
    if result == QMessageBox.Ok:
        return IDOK
    elif result == QMessageBox.Cancel:
        return IDCANCEL
    elif result == QMessageBox.Yes:
        return IDYES
    elif result == QMessageBox.No:
        return IDNO

class CustomException(Exception):
    def __init__(self, err, icon=ICON_STOP):
        super().__init__(err)
        message_box(text=err, icon=icon)
        sys.exit()
