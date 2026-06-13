"""Tkinter UI for searching OneDrive transcript files and presenting matches."""

import queue
import re
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from .cache_manager import CacheManager
from .config import get_client_id
from .search_service import search_onedrive_folder
from .ui_helpers import close_device_login_prompt, process_output_queue, show_device_login_prompt

CARD_FRAME_STYLE = 'Card.TFrame'
CARD_DETAILS_STYLE = 'CardDetails.TFrame'
FONT_SEMIBOLD = 'Segoe UI Semibold'
FONT_REGULAR = 'Segoe UI'
CARD_TITLE_STYLE = 'CardTitle.TLabel'
CARD_META_STYLE = 'CardMeta.TLabel'
CARD_COUNT_STYLE = 'CardCount.TLabel'
APP_FRAME_STYLE = 'App.TFrame'
FORM_LABEL_STYLE = 'FormLabel.TLabel'
EXPAND_LABEL = '▶'
COLLAPSE_LABEL = '▼'


def reset_authentication(status_var, results_var, cache_manager):
    """Clear cached tokens and update UI state to signed out."""
    cache_manager.reset()
    status_var.set('Signed out. Next search will require login.')
    results_var.set('')


def format_phrase_timestamp(timestamp):
    """Convert HH:MM:SS timestamps into a human-friendly label."""
    if not timestamp or timestamp == 'Unknown':
        return 'Unknown'
    parts = timestamp.split(':')
    if len(parts) != 3:
        return timestamp
    return f'{parts[0]}h {parts[1]}m {parts[2]}s'


def highlight_match_text(text_widget, snippet_text, search_term):
    """Insert snippet text and highlight matching terms in a Tk text widget."""
    text_widget.insert(tk.END, snippet_text)
    words = re.findall(r'\S+', search_term)
    if not words:
        return

    pattern = re.compile(r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b", flags=re.IGNORECASE)
    for match in pattern.finditer(snippet_text):
        start = f'1.0+{match.start()}c'
        end = f'1.0+{match.end()}c'
        text_widget.tag_add('highlight', start, end)


def create_result_card(parent, file_result, search_term):
    """Render one expandable result card for a matched transcript file."""
    card = ttk.Frame(parent, padding=(14, 12), style=CARD_FRAME_STYLE)
    card.pack(fill='x', pady=(0, 8))

    is_expanded = tk.BooleanVar(value=False)

    header = ttk.Frame(card, style=CARD_FRAME_STYLE)
    header.pack(fill='x')

    toggle_button = ttk.Button(header, text=EXPAND_LABEL, style='CardToggle.TButton')
    toggle_button.grid(row=0, column=1, rowspan=3, sticky='ne', padx=(10, 0))

    title_label = ttk.Label(header, text=file_result['meeting_title'], style=CARD_TITLE_STYLE)
    title_label.grid(row=0, column=0, sticky='w')
    meta_label = ttk.Label(header, text=f"Meeting date/time: {file_result['modified']}", style=CARD_META_STYLE)
    meta_label.grid(row=1, column=0, sticky='w', pady=(2, 0))
    count_label = ttk.Label(header, text=f"{file_result['match_count']} matches", style=CARD_COUNT_STYLE)
    count_label.grid(row=2, column=0, sticky='w', pady=(3, 0))
    header.columnconfigure(0, weight=1)

    details = ttk.Frame(card, style=CARD_DETAILS_STYLE)

    for index, occurrence in enumerate(file_result['occurrences'], start=1):
        match_frame = ttk.Frame(details, style=CARD_DETAILS_STYLE)
        match_frame.pack(fill='x', pady=(6, 0))

        readable_ts = format_phrase_timestamp(occurrence.get('timestamp', 'Unknown'))
        ttk.Label(match_frame, text=f'Match {index} - Timestamp: {readable_ts}', style='MatchHeader.TLabel').pack(anchor='w')

        snippet_text = tk.Text(
            match_frame,
            height=3,
            wrap='word',
            padx=8,
            pady=6,
            bd=1,
            relief='solid',
            background='#ffffff',
            foreground='#1f2937',
            highlightthickness=0,
        )
        snippet_text.pack(fill='x', pady=(2, 0))
        snippet_text.tag_configure('highlight', background='#ffe08a', foreground='#111827')
        highlight_match_text(snippet_text, occurrence.get('snippet', ''), search_term)
        snippet_text.config(state='disabled')

    def toggle_card():
        """Toggle card details between expanded and collapsed states."""
        expanded = not is_expanded.get()
        is_expanded.set(expanded)
        if expanded:
            details.pack(fill='x', pady=(8, 0))
            toggle_button.config(text=COLLAPSE_LABEL)
        else:
            details.pack_forget()
            toggle_button.config(text=EXPAND_LABEL)

    def set_hover_style(is_hovered):
        """Apply hover styles to card elements for visual feedback."""
        card_style = 'CardHover.TFrame' if is_hovered else CARD_FRAME_STYLE
        details_style = 'CardDetailsHover.TFrame' if is_hovered else CARD_DETAILS_STYLE
        title_style = 'CardTitleHover.TLabel' if is_hovered else CARD_TITLE_STYLE
        meta_style = 'CardMetaHover.TLabel' if is_hovered else CARD_META_STYLE
        count_style = 'CardCountHover.TLabel' if is_hovered else CARD_COUNT_STYLE

        card.configure(style=card_style)
        header.configure(style=card_style)
        details.configure(style=details_style)
        title_label.configure(style=title_style)
        meta_label.configure(style=meta_style)
        count_label.configure(style=count_style)

    def bind_hover(widget):
        """Bind enter/leave events that switch the card hover style."""
        widget.bind('<Enter>', lambda _event: set_hover_style(True), add='+')
        widget.bind('<Leave>', lambda _event: set_hover_style(False), add='+')

    bind_hover(card)
    bind_hover(header)
    bind_hover(toggle_button)
    bind_hover(title_label)
    bind_hover(meta_label)
    bind_hover(count_label)

    toggle_button.config(command=toggle_card)


def search_one_drive(folder_path, search_term, results_host, cache_manager):
    """Authenticate and search a OneDrive folder for phrase matches."""
    try:
        if not get_client_id():
            return {'error': 'Client ID is required.', 'matching_files': []}
        if folder_path:
            cache_manager.set_folder_path(folder_path)
        if not folder_path:
            return {'error': 'Please set Folder Path before searching.', 'matching_files': []}
        if not search_term:
            return {'error': 'Search term is required.', 'matching_files': []}

        access_token = cache_manager.acquire_access_token(
            show_device_login_prompt=lambda message: show_device_login_prompt(results_host, message),
            close_device_login_prompt=lambda: close_device_login_prompt(results_host),
        )
        if not access_token:
            return {'error': 'Authentication failed.', 'matching_files': []}

        return search_onedrive_folder(
            access_token=access_token,
            folder_path=folder_path,
            search_term=search_term,
        )
    except Exception as exc:
        return {'error': f'Unexpected error: {exc}', 'matching_files': []}


def can_start_search(search_button, folder_path, search_term, folder_path_entry, search_term_entry):
    """Return whether a search can start and show popups for missing inputs."""
    if search_button.instate(['disabled']):
        return False
    if folder_path:
        if search_term:
            return True

        messagebox.showwarning('Search Term Required', 'Please enter a search term before searching.')
        search_term_entry.focus_set()
        return False

    messagebox.showwarning('Folder Path Required', 'Please set Folder Path before searching.')
    folder_path_entry.focus_set()
    return False


def main():
    """Start and run the desktop application main event loop."""
    cache_manager = CacheManager()

    root = tk.Tk()
    root.title('OneDrive Transcript Search')
    root.geometry('900x610')

    style = ttk.Style(root)
    if 'clam' in style.theme_names():
        style.theme_use('clam')

    style.configure(APP_FRAME_STYLE, background='#ffffff')
    style.configure(FORM_LABEL_STYLE, background='#ffffff', foreground='#111827', font=(FONT_REGULAR, 10))
    style.configure(CARD_FRAME_STYLE, background='#f8fafc', relief='solid', borderwidth=1)
    style.configure('CardHover.TFrame', background='#eef6ff', relief='solid', borderwidth=1)
    style.configure(CARD_DETAILS_STYLE, background='#f8fafc')
    style.configure('CardDetailsHover.TFrame', background='#eef6ff')
    style.configure(CARD_TITLE_STYLE, background='#f8fafc', foreground='#111827', font=(FONT_SEMIBOLD, 11))
    style.configure('CardTitleHover.TLabel', background='#eef6ff', foreground='#111827', font=(FONT_SEMIBOLD, 11))
    style.configure(CARD_META_STYLE, background='#f8fafc', foreground='#4b5563', font=(FONT_REGULAR, 9))
    style.configure('CardMetaHover.TLabel', background='#eef6ff', foreground='#4b5563', font=(FONT_REGULAR, 9))
    style.configure(CARD_COUNT_STYLE, background='#f8fafc', foreground='#0f766e', font=(FONT_SEMIBOLD, 9))
    style.configure('CardCountHover.TLabel', background='#eef6ff', foreground='#0f766e', font=(FONT_SEMIBOLD, 9))
    style.configure('MatchHeader.TLabel', background='#f8fafc', foreground='#374151', font=(FONT_SEMIBOLD, 9))
    style.configure('CardToggle.TButton', padding=(10, 4), font=(FONT_REGULAR, 9))
    style.configure(
        'Green.Horizontal.TProgressbar',
        troughcolor='#e5e7eb',
        background='#16a34a',
        darkcolor='#15803d',
        lightcolor='#22c55e',
        bordercolor='#e5e7eb',
    )

    frame = ttk.Frame(root, padding=12, style=APP_FRAME_STYLE)
    frame.pack(fill='both', expand=True)

    ttk.Label(frame, text='Folder Path:', style=FORM_LABEL_STYLE).grid(row=0, column=0, sticky='w')
    folder_path_var = tk.StringVar(value=cache_manager.get_folder_path())
    folder_path_entry = ttk.Entry(frame, textvariable=folder_path_var, width=70)
    folder_path_entry.grid(row=0, column=1, columnspan=3, sticky='ew', pady=2)

    ttk.Label(frame, text='Search Term:', style=FORM_LABEL_STYLE).grid(row=1, column=0, sticky='w')
    search_term_var = tk.StringVar()
    search_term_entry = ttk.Entry(frame, textvariable=search_term_var, width=50)
    search_term_entry.grid(row=1, column=1, sticky='w', pady=2)

    results_container = ttk.Frame(frame)
    results_container.grid(row=2, column=0, columnspan=4, sticky='nsew', pady=(10, 0))

    results_canvas = tk.Canvas(results_container, highlightthickness=0, background='#ffffff', bd=0)
    results_scrollbar = ttk.Scrollbar(results_container, orient='vertical', command=results_canvas.yview)
    results_canvas.configure(yscrollcommand=results_scrollbar.set)
    results_canvas.pack(side='left', fill='both', expand=True)
    results_scrollbar.pack(side='right', fill='y')

    cards_frame = ttk.Frame(results_canvas)
    cards_window = results_canvas.create_window((0, 0), window=cards_frame, anchor='nw')

    cards_frame.output_queue = queue.Queue()
    process_output_queue(cards_frame)

    def on_cards_configure(_event):
        """Update scroll region when card content size changes."""
        results_canvas.configure(scrollregion=results_canvas.bbox('all'))

    def on_canvas_configure(event):
        """Keep the cards frame width aligned with the canvas width."""
        results_canvas.itemconfig(cards_window, width=event.width)

    cards_frame.bind('<Configure>', on_cards_configure)
    results_canvas.bind('<Configure>', on_canvas_configure)

    status_row = ttk.Frame(frame, style=APP_FRAME_STYLE)
    status_row.grid(row=3, column=0, columnspan=3, sticky='w', pady=(10, 0))

    status_var = tk.StringVar(value='')
    status_label = ttk.Label(status_row, textvariable=status_var, style=FORM_LABEL_STYLE)
    status_label.grid(row=0, column=0, sticky='w')

    progress_bar = ttk.Progressbar(status_row, mode='indeterminate', length=180, style='Green.Horizontal.TProgressbar')
    progress_bar.grid(row=0, column=1, sticky='w', padx=(10, 0))

    results_var = tk.StringVar(value='')
    results_label = ttk.Label(status_row, textvariable=results_var, style=FORM_LABEL_STYLE)
    results_label.grid(row=0, column=2, sticky='w', padx=(12, 0))

    def clear_cards():
        """Remove all rendered result cards from the results area."""
        for widget in cards_frame.winfo_children():
            widget.destroy()

    def render_results(search_term, matching_files):
        """Render result cards for all matching files."""
        clear_cards()
        for file_result in matching_files:
            create_result_card(cards_frame, file_result, search_term)

    def finalize_search(result):
        """Apply search results to UI state after background work finishes."""
        matching_files = result.get('matching_files', [])
        error_message = result.get('error')
        if error_message:
            status_var.set(error_message)
            results_var.set('')
            clear_cards()
        else:
            status_var.set('')
            results_var.set(f"Found {len(matching_files)} matching files")
            render_results(search_term_var.get().strip(), matching_files)

    def set_searching_state(is_searching):
        """Enable or disable loading state controls for active searches."""
        def apply_state():
            """Apply state changes on the Tk main thread."""
            if is_searching:
                status_var.set('Searching...')
                results_var.set('')
                progress_bar.start(10)
                search_button.state(['disabled'])
            else:
                progress_bar.stop()
                search_button.state(['!disabled'])

        root.after(0, apply_state)

    def run_search(folder_path, search_term):
        """Execute a folder search in a worker thread."""
        set_searching_state(True)
        try:
            result = search_one_drive(
                folder_path,
                search_term,
                cards_frame,
                cache_manager,
            )
            root.after(0, lambda: finalize_search(result))
        finally:
            set_searching_state(False)

    def start_search():
        """Start a new background search when the UI is ready."""
        folder_path = folder_path_var.get().strip()
        search_term = search_term_var.get().strip()
        if not can_start_search(search_button, folder_path, search_term, folder_path_entry, search_term_entry):
            return
        clear_cards()
        threading.Thread(target=run_search, args=(folder_path, search_term), daemon=True).start()

    search_button = ttk.Button(
        frame,
        text='Search',
        command=start_search,
        default='active',
    )
    search_button.grid(row=1, column=2, sticky='w', padx=8)

    def on_enter_key(_event):
        """Trigger search when the Enter key is pressed."""
        start_search()
        return 'break'

    root.bind('<Return>', on_enter_key)

    sign_out_button = ttk.Button(
        frame,
        text='Sign Out',
        command=lambda: reset_authentication(status_var, results_var, cache_manager),
    )
    sign_out_button.grid(row=3, column=3, sticky='e', pady=(10, 0))

    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(2, weight=1)

    root.mainloop()
