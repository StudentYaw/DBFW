from pathlib import Path
import sys
import pyautogui
import pygetwindow as gw
from PIL import Image
from dialog import *
from Codes import *

# codes
CODES_FILE = 'codes.txt'
CODES_ERR_FILE = 'codes_with_errors.txt'

# variables

counterSuc = 0
counterErr = 0
counterAlr = 0
NotDone = True

# resources folder
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # PyInstaller temp path
    RESOURCES = Path(sys._MEIPASS) / 'res'
else:
    # local res folder
    RESOURCES = Path(__file__).parent / 'res'

# original images
TEXTBOX_IMG = RESOURCES / 'textbox.png'
CONFIRM_IMG = RESOURCES / 'confirm.png'
SUCCESS_IMG = RESOURCES / 'success.png'
CLOSE_IMG = RESOURCES / 'close.png'
ALREADYUSED_IMG = RESOURCES / 'alreadyused.png'
INVALID_IMG = RESOURCES / 'invalid.png'
# scaled images
TEXTBOX_IMG1 = RESOURCES / 'textbox_scaled.png'
CONFIRM_IMG1 = RESOURCES / 'confirm_scaled.png'
SUCCESS_IMG1 = RESOURCES / 'success_scaled.png'
CLOSE_IMG1 = RESOURCES / 'close_scaled.png'
ALREADYUSED_IMG1 = RESOURCES / 'alreadyused.png'
INVALID_IMG1 = RESOURCES / 'invalid.png'

# constants
CODE_LENGTH = 16
CONFIDENCE = 0.85
SLEEP = 0.5
SLEEP_CONFIRM = 5
WRITE_INTERVAL = 0.03
ORIGINAL_RESOLUTION = (1920, 1080)

# function to determine Scale factor
def get_scaling_factor(ORIGINAL_RESOLUTION, current_resolution):
    width_factor = current_resolution[0] / ORIGINAL_RESOLUTION[0]
    height_factor = current_resolution[1] / ORIGINAL_RESOLUTION[1]
    return (width_factor + height_factor) / 2

# Scaling the new picture
def scale_image(image_path, scaling_factor):
    image = Image.open(image_path)
    
    # Calc the new Size
    new_width = int(image.width * scaling_factor)
    new_height = int(image.height * scaling_factor)
    
    # Resampling
    scaled_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Saving the new Picture
    scaled_image_path = RESOURCES / (image_path.stem + '_scaled.png')
    scaled_image.save(scaled_image_path)
    return scaled_image_path

# Function to locate scaled picture
def locate_image_on_screen(image_path, scaling_factor):
    scaled_image_path = scale_image(image_path, scaling_factor)
    if scaled_image_path:
        try:
            position = pyautogui.locateOnScreen(scaled_image_path.as_posix(),confidence= CONFIDENCE)
            return position
        except pyautogui.ImageNotFoundException:
            return None
        except Exception as e:
            return None
    return None

def resolve_to_standard_resolution(width, height):
    # Definition of standard resolutions
    standard_resolutions = [
        (1280, 720),   # 720p
        (1920, 1080),  # 1080p
        (2560, 1440),  # 1440p
        (3840, 2160)   # 4K
    ]
    # toleranz for mismatch 
    tolerance = 100  # allowed tolerance in pixel

    for (std_width, std_height) in standard_resolutions:
        if (abs(width - std_width) <= tolerance) and (abs(height - std_height) <= tolerance):
            return (std_width, std_height)
    return None

# Get Window Size
windows = gw.getWindowsWithTitle('DBSCGFW')

if windows:
    # Assuming you want to work with the first window with the given title
    window = windows[0]
    
    # Get window size and position
    width, height = window.width, window.height

# Calc of Window Res and Scaling factor
try:
    current_resolution = resolve_to_standard_resolution(width, height) # Window Resolution
    scaling_factor = get_scaling_factor(ORIGINAL_RESOLUTION, current_resolution)
except Exception:
    raise CustomException(f'Game isnt opened make sure the Game is opened!')

# generate Scaled Images
scale_image(TEXTBOX_IMG, scaling_factor)
scale_image(CONFIRM_IMG, scaling_factor)
scale_image(SUCCESS_IMG, scaling_factor)
scale_image(CLOSE_IMG, scaling_factor)
scale_image(ALREADYUSED_IMG, scaling_factor)
scale_image(INVALID_IMG, scaling_factor)

while NotDone:
    run_codes()
    try:
        with open(CODES_FILE) as f:
            codes = [''.join(line.strip().split()) for line in f]
            if not codes:
                raise CustomException(f'{CODES_FILE} is empty')
            if not all(len(code) == CODE_LENGTH for code in codes):
                raise CustomException(f'Ensure all codes have {CODE_LENGTH} characters')
    except FileNotFoundError:
        raise CustomException(f'{CODES_FILE} not found')

    approx_time = int(1 + len(codes) * (SLEEP + SLEEP_CONFIRM + CODE_LENGTH*WRITE_INTERVAL) / 60)
    suffix = 'minute' if approx_time == 1 else 'minutes'
    if message_box(f'This process will take approximately {approx_time} {suffix}. Continue?', style=STYLE_OKCANCEL) == IDCANCEL:
        sys.exit()

    pyautogui.sleep(SLEEP)

    errors = False
    while codes:
        code = codes.pop(0)
        try:
            res = pyautogui.locateOnScreen(TEXTBOX_IMG1.as_posix(), confidence=CONFIDENCE)
            location = (res.left + res.width*0.1, res.top + res.height*0.5)
            pyautogui.click(*location)
            pyautogui.click(*location)
            pyautogui.sleep(SLEEP)
            pyautogui.write(code, WRITE_INTERVAL)
        except Exception:
            raise CustomException(f'Codes Section is not opened')

        # confirm
        try:
            res = pyautogui.locateOnScreen(CONFIRM_IMG1.as_posix(), confidence=CONFIDENCE)
            pyautogui.click(pyautogui.center(res))
            pyautogui.sleep(SLEEP_CONFIRM)
        except:
            raise CustomException('Cannot press Confirm')

        # check if successful
        try:
            res = pyautogui.locateOnScreen(SUCCESS_IMG1.as_posix(), confidence=CONFIDENCE)
            counterSuc += 1
        except:
            errors = True
            try:    
                pyautogui.locateOnScreen(ALREADYUSED_IMG1.as_posix(), confidence=CONFIDENCE)
                with open(CODES_ERR_FILE, 'a') as f:
                    f.write(f'{code} Already used!\n')
                    counterAlr  += 1
            except: 
                try:
                    pyautogui.locateOnScreen(INVALID_IMG1.as_posix(), confidence=CONFIDENCE)
                    with open(CODES_ERR_FILE, 'a') as f:
                        f.write(f'{code} Invalid Code!\n')
                    counterErr += 1 
                except:
                    with open(CODES_ERR_FILE, 'a') as f:
                        f.write(f'{code} Unknown Issue!\n')
            if counterErr>=5:
                message_box('Exceeded the maximum numbers of Fails!', icon=ICON_EXCLAMATION)
                break

        # close
        try:
            res = pyautogui.locateOnScreen(CLOSE_IMG1.as_posix(), confidence=CONFIDENCE)
            pyautogui.click(pyautogui.center(res))
        except:
            raise CustomException('Cannot press Close')

    with open(CODES_FILE, 'w') as file:
        for code in codes:
            file.write(f'{code} \n')


    if errors:
        if message_box(
            f'Some errors occured!\nThey were {counterErr} invalid codes, {counterAlr} Codes that were Already used and {counterSuc} successful one. \nThe codes have been written to {CODES_ERR_FILE} \nContinue?'
            , icon=ICON_EXCLAMATION , style=STYLE_Q
            ) == IDNO:
            NotDone = False
    else:
        if message_box(f'Done! I had {counterSuc} Succeful Codes \nContinue?' , style=STYLE_Q) == IDNO:
            NotDone = False
