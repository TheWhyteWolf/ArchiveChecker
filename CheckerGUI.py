#!/usr/bin/env python3
"""
gui.py — Tkinter GUI frontend for the MiNERVA Archive Checker.
Resizable window; supports single file and folder batch checking.
"""

import tkinter as tk
from tkinter import filedialog, simpledialog
from pathlib import Path
import threading
from PIL import Image, ImageTk

from core import check_file, add_to_database, DEFAULT_DB, CheckResult

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#231f20"
PANEL    = "#1a1718"
BORDER   = "#3d3440"
PURPLE   = "#9f7aea"
WHITE    = "#ffffff"
RED      = "#f5352b"
YELLOW   = "#f2c201"
GREEN    = "#00881c"
BLUE     = "#0184c3"
TEXT     = WHITE
TEXT_DIM = "#7a6e7e"
TEXT_HASH= "#4a3f50"

LOGO_PATH = Path(__file__).parent / "g6.jpg"
MIN_W, MIN_H = 480, 560

def _bind_drop(widget, callback):
    try:
        widget.drop_target_register("DND_Files")          # type: ignore
        widget.dnd_bind("<<Drop>>", lambda e: callback(e.data.strip("{}")))
    except Exception:
        pass

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MiNERVA Archive Checker")
        self.configure(bg=BG)
        self.minsize(MIN_W, MIN_H)
        self.geometry("620x620")
        self.db_path = DEFAULT_DB
        self._last_result: CheckResult | None = None
        self._logo_img = None
        self._build_ui()
        self.columnconfigure(0, weight=1)

    def _build_ui(self):
        # ── Header ──
        hdr = tk.Frame(self, bg=PANEL, height=58)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        if LOGO_PATH.exists():
            try:
                raw = Image.open(LOGO_PATH)
                h = 40
                w = int(raw.width * h / raw.height)
                raw = raw.resize((w, h), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(raw)
                tk.Label(hdr, image=self._logo_img, bg=PANEL, padx=12).pack(side="left")
            except Exception:
                pass

        tk.Label(hdr, text="M",               bg=PANEL, fg=PURPLE,   padx=0, font=("Courier", 20, "bold")).pack(side="left")
        tk.Label(hdr, text="i",               bg=PANEL, fg=WHITE,    padx=0, font=("Courier", 20, "bold")).pack(side="left")
        tk.Label(hdr, text="NERVA",           bg=PANEL, fg=PURPLE,   padx=0, font=("Courier", 20, "bold")).pack(side="left")
        tk.Label(hdr, text="  Archive Checker", bg=PANEL, fg=TEXT_DIM, font=("Courier", 13)).pack(side="left")

        tk.Frame(self, bg=PURPLE, height=2).pack(fill="x", side="top")

        # ── Body ──
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(5, weight=1)   # results list gets all extra vertical space

        # ── Drop zone ──
        self.drop_zone = tk.Frame(
            body, bg=PANEL,
            highlightbackground=BORDER, highlightthickness=1,
            height=130, cursor="hand2",
        )
        self.drop_zone.grid(row=0, column=0, sticky="ew")
        self.drop_zone.pack_propagate(False)

        self.drop_icon = tk.Label(self.drop_zone, text="⬇", bg=PANEL, fg=BORDER, font=("TkDefaultFont", 28))
        self.drop_icon.pack(expand=True)

        self.drop_hint = tk.Label(self.drop_zone, text="DROP FILE HERE or", bg=PANEL, fg=TEXT_DIM, font=("Courier", 10))
        self.drop_hint.pack()

        # Browse buttons row
        btn_row = tk.Frame(self.drop_zone, bg=PANEL)
        btn_row.pack(pady=(4, 14))

        tk.Button(
            btn_row, text="BROWSE FILE →",
            bg=PANEL, fg=PURPLE, relief="flat",
            font=("Courier", 11, "bold"), cursor="hand2",
            activebackground=PANEL, activeforeground=WHITE,
            command=self._browse_file,
        ).pack(side="left", padx=(0, 12))

        tk.Button(
            btn_row, text="BROWSE FOLDER →",
            bg=PANEL, fg=PURPLE, relief="flat",
            font=("Courier", 11, "bold"), cursor="hand2",
            activebackground=PANEL, activeforeground=WHITE,
            command=self._browse_folder,
        ).pack(side="left")

        for w in (self.drop_zone, self.drop_icon, self.drop_hint):
            w.bind("<Button-1>", lambda e: self._browse_file())

        _bind_drop(self.drop_zone, self._handle_drop)

        # ── Status panel (single-file mode) ──
        status_panel = tk.Frame(
            body, bg=PANEL,
            highlightbackground=BORDER, highlightthickness=1,
            height=72,
        )
        status_panel.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        status_panel.pack_propagate(False)

        self.status_label = tk.Label(
            status_panel, text="—",
            bg=PANEL, fg=TEXT_DIM,
            font=("TkDefaultFont", 16, "bold"),
            anchor="w", padx=20,
        )
        self.status_label.pack(fill="both", expand=True)

        # ── Hash row ──
        hash_row = tk.Frame(body, bg=BG, pady=8)
        hash_row.grid(row=2, column=0, sticky="ew")

        tk.Label(hash_row, text="MD5", bg=BG, fg=TEXT_DIM,
                 font=("Courier", 9), width=5, anchor="w").pack(side="left")

        self.hash_var = tk.StringVar(value="—" * 32)
        self.hash_entry = tk.Entry(
            hash_row, textvariable=self.hash_var,
            bg=BG, fg=TEXT_HASH, relief="flat",
            font=("Courier", 10), readonlybackground=BG,
            insertbackground=PURPLE, state="readonly", width=36,
        )
        self.hash_entry.pack(side="left", padx=(8, 0))

        self.copy_btn = tk.Button(
            hash_row, text="COPY",
            bg=BG, fg=BLUE, relief="flat",
            font=("Courier", 9), cursor="hand2",
            activebackground=BG, activeforeground=WHITE,
            command=self._copy_hash,
        )
        self.copy_btn.pack(side="left", padx=8)

        # File info
        self.file_label = tk.Label(
            body, text="",
            bg=BG, fg=TEXT_DIM, font=("Courier", 8),
            anchor="w", wraplength=520,
        )
        self.file_label.grid(row=3, column=0, sticky="ew")

        # Add to DB button (single-file mode, hidden by default)
        self.add_btn = tk.Button(
            body, text="+ ADD TO DATABASE",
            bg=BG, fg=YELLOW, relief="flat",
            font=("Courier", 10, "bold"), cursor="hand2",
            activebackground=BG, activeforeground=WHITE,
            command=self._add_to_db,
        )

        # ── Batch results header ──
        batch_hdr = tk.Frame(body, bg=BG, pady=(6))
        batch_hdr.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        batch_hdr.columnconfigure(0, weight=1)

        self.batch_title = tk.Label(
            batch_hdr, text="",
            bg=BG, fg=TEXT_DIM, font=("Courier", 9, "bold"), anchor="w",
        )
        self.batch_title.pack(side="left")

        self.batch_clear_btn = tk.Button(
            batch_hdr, text="CLEAR",
            bg=BG, fg=TEXT_DIM, relief="flat",
            font=("Courier", 9), cursor="hand2",
            activebackground=BG, activeforeground=RED,
            command=self._clear_batch,
        )
        # shown only when results exist

        # ── Scrollable results list ──
        list_frame = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        list_frame.grid(row=6, column=0, sticky="nsew", pady=(4, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        body.rowconfigure(6, weight=1)

        self.results_canvas = tk.Canvas(list_frame, bg=PANEL, highlightthickness=0, height=180)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.results_canvas.yview)
        self.results_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.results_canvas.pack(side="left", fill="both", expand=True)

        self.results_inner = tk.Frame(self.results_canvas, bg=PANEL)
        self._canvas_window = self.results_canvas.create_window((0, 0), window=self.results_inner, anchor="nw")

        self.results_inner.bind("<Configure>", self._on_results_configure)
        self.results_canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse wheel scrolling
        self.results_canvas.bind("<MouseWheel>", lambda e: self.results_canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        self.results_canvas.bind("<Button-4>",   lambda e: self.results_canvas.yview_scroll(-1, "units"))
        self.results_canvas.bind("<Button-5>",   lambda e: self.results_canvas.yview_scroll(1,  "units"))

        # ── Progress / footer ──
        footer = tk.Frame(self, bg=BG, padx=24, pady=6)
        footer.pack(fill="x", side="bottom")
        self.progress_var = tk.StringVar(value="")
        tk.Label(footer, textvariable=self.progress_var,
                 bg=BG, fg=BLUE, font=("Courier", 9)).pack(side="right")

        self.bind("<Configure>", self._on_resize)

    # ── Canvas / resize helpers ───────────────────────────────────────────────

    def _on_results_configure(self, event):
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.results_canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_resize(self, event):
        new_wrap = self.winfo_width() - 48
        if new_wrap > 100:
            self.file_label.config(wraplength=new_wrap)

    # ── Browse actions ────────────────────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(title="Select file to check")
        if path:
            self._check_file(path)

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder to check")
        if folder:
            self._check_folder(folder)

    def _handle_drop(self, path: str):
        p = Path(path)
        if p.is_dir():
            self._check_folder(str(p))
        else:
            self._check_file(str(p))

    # ── Single file ───────────────────────────────────────────────────────────

    def _check_file(self, filepath: str):
        self.add_btn.grid_remove()
        self.progress_var.set("hashing…")
        self.status_label.config(text="…", fg=TEXT_DIM)
        self.hash_var.set("—" * 32)
        self.hash_entry.config(fg=TEXT_HASH)
        self.file_label.config(text=Path(filepath).name, fg=TEXT_DIM)
        threading.Thread(target=self._do_check, args=(filepath,), daemon=True).start()

    def _do_check(self, filepath: str):
        try:
            result = check_file(filepath, db_path=self.db_path)
            self.after(0, self._show_result, result)
        except FileNotFoundError as e:
            self.after(0, self._show_error, str(e))
        except Exception as e:
            self.after(0, self._show_error, f"Unexpected error: {e}")

    def _show_result(self, result: CheckResult):
        self._last_result = result
        self.progress_var.set("")
        self.hash_var.set(result.md5)
        self.hash_entry.config(fg=TEXT)
        self.file_label.config(text=result.filepath, fg=TEXT_DIM)

        if result.in_library:
            label_info = f"  ({result.label})" if result.label else ""
            self.status_label.config(text=f"✔ IN LIBRARY{label_info}", fg=GREEN)
            self._flash(GREEN)
            self.add_btn.grid_remove()
        else:
            self.status_label.config(text="✦ NEW ARCHIVE", fg=YELLOW)
            self._flash(YELLOW)
            self.add_btn.grid(row=4, column=0, sticky="w", pady=(4, 0))

    def _show_error(self, msg: str):
        self.progress_var.set("")
        self.status_label.config(text="ERROR", fg=RED)
        self.file_label.config(text=msg, fg=RED)
        self.add_btn.grid_remove()

    # ── Folder batch ──────────────────────────────────────────────────────────

    def _check_folder(self, folder: str):
        files = [f for f in Path(folder).rglob("*") if f.is_file()]
        if not files:
            self.status_label.config(text="Empty folder", fg=TEXT_DIM)
            return

        # Reset single-file UI
        self.add_btn.grid_remove()
        self.hash_var.set("—" * 32)
        self.hash_entry.config(fg=TEXT_HASH)
        self.file_label.config(text="")
        self.status_label.config(text=f"Scanning {len(files)} file(s)…", fg=TEXT_DIM)
        self._clear_batch(silent=True)

        self.batch_title.config(text=f"FOLDER RESULTS — {Path(folder).name}")
        self.batch_clear_btn.pack(side="right")

        threading.Thread(
            target=self._do_batch, args=(files,), daemon=True
        ).start()

    def _do_batch(self, files: list):
        results = []
        for i, f in enumerate(files, 1):
            self.after(0, lambda i=i, total=len(files): self.progress_var.set(f"hashing {i}/{total}…"))
            try:
                r = check_file(f, db_path=self.db_path)
                results.append(r)
                self.after(0, self._append_batch_row, r)
            except Exception as e:
                self.after(0, self._append_batch_error, str(f), str(e))

        in_lib  = sum(1 for r in results if r.in_library)
        new_arc = len(results) - in_lib
        self.after(0, lambda: self.status_label.config(
            text=f"✔ {in_lib} in library   ✦ {new_arc} new", fg=PURPLE))
        self.after(0, lambda: self.progress_var.set(""))
        self.after(0, lambda: self._flash(GREEN if new_arc == 0 else YELLOW))

    def _append_batch_row(self, result: CheckResult):
        row = tk.Frame(self.results_inner, bg=PANEL)
        row.pack(fill="x", padx=6, pady=2)

        colour = GREEN if result.in_library else YELLOW
        status = "✔" if result.in_library else "✦"

        tk.Label(row, text=status, bg=PANEL, fg=colour,
                 font=("Courier", 10, "bold"), width=2).pack(side="left")

        name = Path(result.filepath).name
        tk.Label(row, text=name, bg=PANEL, fg=TEXT,
                 font=("Courier", 9), anchor="w").pack(side="left", padx=(4, 8))

        tk.Label(row, text=result.md5, bg=PANEL, fg=TEXT_HASH,
                 font=("Courier", 8), anchor="e").pack(side="right")

    def _append_batch_error(self, filepath: str, msg: str):
        row = tk.Frame(self.results_inner, bg=PANEL)
        row.pack(fill="x", padx=6, pady=2)
        tk.Label(row, text="✗", bg=PANEL, fg=RED,
                 font=("Courier", 10, "bold"), width=2).pack(side="left")
        tk.Label(row, text=f"{Path(filepath).name} — {msg}", bg=PANEL, fg=RED,
                 font=("Courier", 9), anchor="w").pack(side="left", padx=4)

    def _clear_batch(self, silent=False):
        for widget in self.results_inner.winfo_children():
            widget.destroy()
        if not silent:
            self.batch_title.config(text="")
            self.batch_clear_btn.pack_forget()

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _flash(self, colour: str):
        self.drop_zone.config(highlightbackground=colour)
        self.after(600, lambda: self.drop_zone.config(highlightbackground=BORDER))

    def _copy_hash(self):
        val = self.hash_var.get()
        if val and "—" not in val:
            self.clipboard_clear()
            self.clipboard_append(val)
            self.copy_btn.config(text="✔", fg=GREEN)
            self.after(1500, lambda: self.copy_btn.config(text="COPY", fg=BLUE))

    def _add_to_db(self):
        if not self._last_result:
            return
        label = simpledialog.askstring(
            "Add to Database",
            "Enter a label for this file (leave blank to use filename):",
            parent=self,
        )
        if label is None:
            return
        label = label.strip() or Path(self._last_result.filepath).name
        add_to_database(self._last_result.md5, label, db_path=self.db_path)
        self.status_label.config(text="✔ IN LIBRARY", fg=GREEN)
        self._flash(GREEN)
        self.add_btn.grid_remove()

if __name__ == "__main__":
    App().mainloop()
