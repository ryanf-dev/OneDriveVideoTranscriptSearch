"""UI helper functions for threaded output and device-login dialogs."""

import queue
import re
import tkinter as tk
import webbrowser
from tkinter import messagebox
from tkinter import ttk


def process_output_queue(output_widget):
    """Drain queued UI actions and reschedule queue processing."""
    output_queue = getattr(output_widget, 'output_queue', None)
    if output_queue is None:
        return

    while True:
        try:
            action, payload = output_queue.get_nowait()
        except queue.Empty:
            break

        if action == 'device_login':
            show_device_login_popup(output_widget, payload or '')
            continue
        if action == 'close_device_login':
            close_device_login_popup(output_widget)
            continue

        output_widget.config(state='normal')
        if action == 'clear':
            output_widget.delete('1.0', tk.END)
        elif action == 'append':
            output_widget.insert(tk.END, (payload or '') + '\n')
            output_widget.see(tk.END)
        output_widget.config(state='disabled')

    output_widget.after(100, lambda: process_output_queue(output_widget))


def parse_device_login_message(message):
    """Extract login URL and device code from MSAL device flow text."""
    url_match = re.search(r'https?://\S+', message)
    code_match = re.search(r'enter the code\s+([A-Z0-9]+)', message, flags=re.IGNORECASE)
    login_url = url_match.group(0).rstrip('.') if url_match else ''
    device_code = code_match.group(1).strip() if code_match else ''
    return login_url, device_code


def show_device_login_prompt(output_widget, message):
    """Queue or display a device-login popup prompt for the user."""
    output_queue = getattr(output_widget, 'output_queue', None)
    if output_queue is not None:
        output_queue.put(('device_login', message))
        return

    show_device_login_popup(output_widget, message)


def close_device_login_prompt(output_widget):
    """Queue or close any visible device-login popup."""
    output_queue = getattr(output_widget, 'output_queue', None)
    if output_queue is not None:
        output_queue.put(('close_device_login', None))
        return

    close_device_login_popup(output_widget)


def show_device_login_popup(output_widget, message):
    """Create and display a modal popup with device login instructions."""
    login_url, device_code = parse_device_login_message(message)
    if not login_url or not device_code:
        messagebox.showinfo('Microsoft Sign-In', message, parent=output_widget.winfo_toplevel())
        return

    close_device_login_popup(output_widget)

    popup = tk.Toplevel(output_widget.winfo_toplevel())
    popup.title('Microsoft Sign-In Required')
    popup.transient(output_widget.winfo_toplevel())
    popup.grab_set()
    popup.resizable(False, False)

    setattr(output_widget, 'device_login_popup', popup)

    def on_popup_destroy(_event=None):
        """Clear popup reference when the dialog is destroyed."""
        if getattr(output_widget, 'device_login_popup', None) is popup:
            setattr(output_widget, 'device_login_popup', None)

    popup.bind('<Destroy>', on_popup_destroy)

    frame = ttk.Frame(popup, padding=16)
    frame.pack(fill='both', expand=True)

    ttk.Label(frame, text='Your device sign-in is required to access your files.', wraplength=350).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 12))

    ttk.Label(frame, text='Enter this code on your browser:', font=('TkDefaultFont', 10, 'bold')).grid(row=1, column=0, sticky='w')
    code_entry = tk.Entry(frame, width=20, font=('Courier', 14))
    code_entry.insert(0, device_code)
    code_entry.config(state='readonly')
    code_entry.grid(row=2, column=0, sticky='w', pady=(4, 8))

    def copy_value(value):
        """Copy a value to clipboard from the popup window."""
        popup.clipboard_clear()
        popup.clipboard_append(value)
        popup.update()

    ttk.Button(frame, text='Copy Code', command=lambda: copy_value(device_code)).grid(row=2, column=1, padx=(8, 0), sticky='w')

    ttk.Label(frame, text='Open this link in your browser:', font=('TkDefaultFont', 10, 'bold')).grid(row=3, column=0, columnspan=2, sticky='w', pady=(12, 4))
    link_entry = tk.Entry(frame, width=44)
    link_entry.insert(0, login_url)
    link_entry.config(state='readonly')
    link_entry.grid(row=4, column=0, sticky='ew', pady=(4, 8))

    ttk.Button(frame, text='Open Link', command=lambda: webbrowser.open(login_url)).grid(row=4, column=1, padx=(8, 0), sticky='w')
    ttk.Button(frame, text='Close', command=popup.destroy).grid(row=5, column=1, sticky='e', pady=(12, 0))

    frame.columnconfigure(0, weight=1)
    popup.update_idletasks()
    popup.geometry(f'+{popup.winfo_toplevel().winfo_rootx() + 120}+{popup.winfo_toplevel().winfo_rooty() + 120}')
    popup.focus_force()


def close_device_login_popup(output_widget):
    """Destroy the current device-login popup if it exists."""
    popup = getattr(output_widget, 'device_login_popup', None)
    if popup is None:
        return

    if popup.winfo_exists():
        popup.destroy()

    setattr(output_widget, 'device_login_popup', None)
