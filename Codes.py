import tkinter as tk
from tkinter import messagebox, scrolledtext
import re

# Global variable to track whether to append or overwrite
append_mode = False
input_box = None  # Declare input_box at the module level

# Function to extract codes from the input text
def extract_codes(overwrite=True):
    global append_mode
    text = input_box.get("1.0", tk.END)  # Get all text from the input box
    pattern = r"\b[A-Z0-9]{4} [A-Z0-9]{4} [A-Z0-9]{4} [A-Z0-9]{4}\b"  # Code pattern
    codes = re.findall(pattern, text)

    if codes:
        # Determine file mode based on whether to append or overwrite
        mode = "w" if overwrite else "a"
        with open("codes.txt", mode) as file:
            for code in codes:
                file.write(code.strip() + "\n")

        result = "\n".join(codes)
        messagebox.showinfo("Extracted Codes", f"Codes extracted and saved:\n{result}")
    else:
        messagebox.showwarning("No Codes Found", "No valid codes were found in the text.")

# Function to handle the initial extraction
def initial_extract():
    extract_codes(overwrite=True)

# Function to handle appending codes
def append_extract():
    global append_mode
    append_mode = True
    extract_codes(overwrite=False)

# Function to clear the text box
def clear_text():
    input_box.delete("1.0", tk.END)

# Function to center the window on the screen
def center_window(root):
    root.update_idletasks()  # Update the window's size and geometry
    width = root.winfo_width()
    height = root.winfo_height()

    # Calculate the x and y coordinates to center the window
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)

    root.geometry(f"{width}x{height}+{x}+{y}")

# Function to create and run the GUI
def run_codes():
    global input_box  # Declare input_box as global to access in extract_codes
    
    # Create the main window
    root = tk.Tk()
    root.title("Code Extractor")
    root.geometry("600x400")  # Initial size
    root.configure(bg="#e9ecef")  # Light background color

    # Center the window
    center_window(root)

    # Header label
    header = tk.Label(
        root, text="Paste your text below and extract codes", 
        font=("Arial", 16, "bold"), bg="#e9ecef", fg="#333333", pady=10
    )
    header.pack()

    # Scrollable text box for input
    input_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Arial", 12), height=10, bg="#ffffff", fg="#000000", borderwidth=2, relief="groove")
    input_box.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

    # Frame for buttons
    button_frame = tk.Frame(root, bg="#e9ecef")
    button_frame.pack(pady=15)

    # Function to change button colors on hover
    def on_enter(e):
        e.widget['background'] = '#007bff'

    def on_leave(e):
        e.widget['background'] = '#0056b3'

    # Function to create a modern button
    def create_button(text, command):
        button = tk.Button(
            button_frame, text=text, command=command, 
            font=("Arial", 12, "bold"), bg="#0056b3", fg="white", padx=20, pady=10,
            borderwidth=0, relief="flat"
        )
        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)
        button.pack(side=tk.LEFT, padx=10)  # Use pack for modern layout
        return button

    # Extract button
    create_button("Extract Codes", initial_extract)

    # Append button
    create_button("Append Codes", append_extract)

    # Clear button
    create_button("Clear", clear_text)

    def on_closing():
        root.quit()  # Stop the main loop
        root.destroy()  # Close the window
        
    # Bind the window close event
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Start the main event loop
    root.mainloop()