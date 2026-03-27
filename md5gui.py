#!/usr/bin/env python3
"""
md5gui.py — GUI frontend for the MD5 Database Crawler.
Crawls a folder, hashes every file, and saves results to a JSON database.
Styled to match the MiNERVA Archive Checker (gui.py).
"""

import hashlib
import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

# ── Palette (matches gui.py) ──────────────────────────────────────────────────
BG        = "#231f20"
PANEL     = "#1a1718"
BORDER    = "#3d3440"
PURPLE    = "#9f7aea"
WHITE     = "#ffffff"
RED       = "#f5352b"
YELLOW    = "#f2c201"
GREEN     = "#00881c"
BLUE      = "#0184c3"
TEXT      = WHITE
TEXT_DIM  = "#7a6e7e"
TEXT_HASH = "#4a3f50"

MIN_W, MIN_H = 520, 620

DEFAULT_DB = Path(__file__).parent / "md5_database.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bind_drop(widget, callback):
    try:
        widget.drop_target_register("DND_Files")  # type: ignore
        widget.dnd_bind("<<Drop>>", lambda e: callback(e.data.strip("{}")))
    except Exception:
        pass


def _md5_of_file(filepath: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(filepath, "rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _load_db(db_path: Path) -> dict:
    if db_path.exists():
        try:
            with open(db_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as e:
            # Corrupted file — back it up and start fresh
            backup = db_path.with_suffix(".json.bak")
            db_path.rename(backup)
            print(f"[md5gui] WARNING: corrupt DB backed up to {backup} — starting fresh. ({e})")
    return {}


def _save_db(db: dict, db_path: Path) -> None:
    tmp = db_path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(db, fh, indent=2, ensure_ascii=False)
    tmp.replace(db_path)  # atomic rename — prevents corruption on interrupted saves

# ── App ───────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MiNERVA — MD5 Crawler")
        self.configure(bg=BG)
        self.minsize(MIN_W, MIN_H)
        self.geometry("580x640")
        self.db_path: Path = DEFAULT_DB
        self._running = False
        self._build_ui()
        self.columnconfigure(0, weight=1)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=PANEL, height=58)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="M",            bg=PANEL, fg=PURPLE,  padx=0, font=("Courier", 20, "bold")).pack(side="left")
        tk.Label(hdr, text="i",            bg=PANEL, fg=WHITE,   padx=0, font=("Courier", 20, "bold")).pack(side="left")
        tk.Label(hdr, text="NERVA",        bg=PANEL, fg=PURPLE,  padx=0, font=("Courier", 20, "bold")).pack(side="left")
        tk.Label(hdr, text=" MD5 Crawler", bg=PANEL, fg=TEXT_DIM, font=("Courier", 13)).pack(side="left")
        tk.Frame(self, bg=PURPLE, height=2).pack(fill="x", side="top")

        # Body
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(5, weight=1)

        # ── Folder drop zone ──
        folder_panel = tk.Frame(
            body, bg=PANEL,
            highlightbackground=BORDER, highlightthickness=1,
            height=110,
        )
        folder_panel.grid(row=0, column=0, sticky="ew")
        folder_panel.pack_propagate(False)

        tk.Label(folder_panel, text="⬇",                  bg=PANEL, fg=BORDER,  font=("TkDefaultFont", 22)).pack(expand=True)
        tk.Label(folder_panel, text="DROP FOLDER HERE or", bg=PANEL, fg=TEXT_DIM, font=("Courier", 10)).pack()

        btn_row = tk.Frame(folder_panel, bg=PANEL)
        btn_row.pack(pady=(4, 12))
        tk.Button(
            btn_row, text="BROWSE FOLDER →",
            bg=PANEL, fg=PURPLE, relief="flat",
            font=("Courier", 11, "bold"), cursor="hand2",
            activebackground=PANEL, activeforeground=WHITE,
            command=self._browse_folder,
        ).pack(side="left")

        _bind_drop(folder_panel, self._handle_drop)
        self._folder_panel = folder_panel

        # ── Path / DB info row ──
        path_frame = tk.Frame(body, bg=BG)
        path_frame.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        path_frame.columnconfigure(1, weight=1)

        tk.Label(path_frame, text="FOLDER", bg=BG, fg=TEXT_DIM, font=("Courier", 9), width=7, anchor="w").grid(row=0, column=0)
        self.folder_var = tk.StringVar(value="(none selected)")
        tk.Label(path_frame, textvariable=self.folder_var, bg=BG, fg=TEXT, font=("Courier", 9), anchor="w").grid(row=0, column=1, sticky="ew")

        tk.Label(path_frame, text="DB", bg=BG, fg=TEXT_DIM, font=("Courier", 9), width=7, anchor="w").grid(row=1, column=0, pady=(4, 0))
        self.db_var = tk.StringVar(value=str(self.db_path))
        db_label = tk.Label(path_frame, textvariable=self.db_var, bg=BG, fg=TEXT_HASH, font=("Courier", 9), anchor="w", cursor="hand2")
        db_label.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        db_label.bind("<Button-1>", lambda e: self._choose_db())

        # ── Status panel ──
        status_panel = tk.Frame(
            body, bg=PANEL,
            highlightbackground=BORDER, highlightthickness=1,
            height=62,
        )
        status_panel.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        status_panel.pack_propagate(False)

        self.status_label = tk.Label(
            status_panel, text="—",
            bg=PANEL, fg=TEXT_DIM,
            font=("TkDefaultFont", 14, "bold"),
            anchor="w", padx=20,
        )
        self.status_label.pack(fill="both", expand=True)

        # ── Run / Stop button ──
        self.run_btn = tk.Button(
            body, text="▶  RUN CRAWLER",
            bg=PURPLE, fg=WHITE, relief="flat",
            font=("Courier", 11, "bold"), cursor="hand2",
            activebackground=BORDER, activeforeground=WHITE,
            command=self._toggle_crawl,
        )
        self.run_btn.grid(row=3, column=0, sticky="ew", pady=(14, 0))

        # ── Results header ──
        results_hdr = tk.Frame(body, bg=BG)
        results_hdr.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        results_hdr.columnconfigure(0, weight=1)

        self.results_title = tk.Label(results_hdr, text="", bg=BG, fg=TEXT_DIM, font=("Courier", 9, "bold"), anchor="w")
        self.results_title.pack(side="left")

        self.clear_btn = tk.Button(
            results_hdr, text="CLEAR",
            bg=BG, fg=TEXT_DIM, relief="flat",
            font=("Courier", 9), cursor="hand2",
            activebackground=BG, activeforeground=RED,
            command=self._clear_results,
        )

        # ── Scrollable results list ──
        list_frame = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        list_frame.grid(row=5, column=0, sticky="nsew", pady=(4, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(list_frame, bg=PANEL, highlightthickness=0, height=200)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.results_inner = tk.Frame(self.canvas, bg=PANEL)
        self._cw = self.canvas.create_window((0, 0), window=self.results_inner, anchor="nw")

        self.results_inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",        lambda e: self.canvas.itemconfig(self._cw, width=e.width))
        self.canvas.bind("<MouseWheel>",        lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        self.canvas.bind("<Button-4>",          lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>",          lambda e: self.canvas.yview_scroll(1, "units"))

        # Footer
        footer = tk.Frame(self, bg=BG, padx=24, pady=6)
        footer.pack(fill="x", side="bottom")
        self.progress_var = tk.StringVar(value="")
        tk.Label(footer, textvariable=self.progress_var, bg=BG, fg=BLUE, font=("Courier", 9)).pack(side="right")

    # ── Folder / DB selection ─────────────────────────────────────────────────

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder to crawl")
        if folder:
            self._set_folder(folder)

    def _handle_drop(self, path: str):
        p = Path(path)
        if p.is_dir():
            self._set_folder(str(p))

    def _set_folder(self, folder: str):
        self.folder_var.set(folder)
        self._folder_path = Path(folder)
        self._flash(PURPLE)
        self.status_label.config(text="Ready to crawl", fg=TEXT_DIM)

    def _choose_db(self):
        path = filedialog.asksaveasfilename(
            title="Choose / create database file",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="md5_database.json",
        )
        if path:
            self.db_path = Path(path)
            self.db_var.set(str(self.db_path))

    # ── Crawl logic ───────────────────────────────────────────────────────────

    def _toggle_crawl(self):
        if self._running:
            self._running = False
            self.run_btn.config(text="▶  RUN CRAWLER", bg=PURPLE)
            return

        if not hasattr(self, "_folder_path"):
            self.status_label.config(text="Select a folder first", fg=RED)
            return

        self._running = True
        self.run_btn.config(text="■  STOP", bg=RED)
        self._clear_results(silent=True)
        threading.Thread(target=self._do_crawl, daemon=True).start()

    def _do_crawl(self):
        folder  = self._folder_path
        db_path = self.db_path
        tmp     = db_path.with_suffix(".json.tmp")

        try:
            db = _load_db(db_path)
        except Exception as e:
            self.after(0, lambda: self.status_label.config(text=f"DB load error: {e}", fg=RED))
            self.after(0, lambda: self.run_btn.config(text="▶  RUN CRAWLER", bg=PURPLE))
            self._running = False
            return

        all_files = [p for p in folder.rglob("*") if p.is_file()]
        total     = len(all_files)

        self.after(0, lambda: self.status_label.config(text=f"Crawling — {total} file(s) found…", fg=TEXT_DIM))
        self.after(0, lambda: self.results_title.config(text=f"RESULTS — {folder.name}"))
        self.after(0, lambda: self.clear_btn.pack(side="right"))

        added = skipped = errors = 0

        for i, filepath in enumerate(all_files, 1):
            if not self._running:
                break

            rel = str(filepath.relative_to(folder))
            self.after(0, lambda i=i: self.progress_var.set(f"hashing {i}/{total}…"))

            try:
                md5 = _md5_of_file(filepath)
            except Exception as e:
                errors += 1
                self.after(0, self._append_error_row, rel, str(e))
                continue

            if md5 in db:
                skipped += 1
                self.after(0, self._append_row, rel, md5, "skip")
            else:
                db[md5] = rel
                added += 1
                self.after(0, self._append_row, rel, md5, "add")

            # Write progress to tmp after every file
            _save_db(db, tmp)

        if self._running:  # completed naturally
            tmp.replace(db_path)  # atomic promotion to real DB
            summary = f"✔ {added} added  ·  {skipped} skipped  ·  {errors} errors  ·  {len(db)} total"
            self.after(0, lambda: self.status_label.config(text=summary, fg=GREEN))
            self.after(0, lambda: self._flash(GREEN if errors == 0 else YELLOW))
        else:
            # Stopped mid-crawl — leave .tmp on disk for inspection, don't touch real DB
            self.after(0, lambda: self.status_label.config(
                text=f"Stopped — partial results in {tmp.name}", fg=YELLOW))

        self.after(0, lambda: self.progress_var.set(""))
        self.after(0, lambda: self.run_btn.config(text="▶  RUN CRAWLER", bg=PURPLE))
        self._running = False
        # ── Result rows ───────────────────────────────────────────────────────────

    def _append_row(self, rel_path: str, md5: str, kind: str):
            row = tk.Frame(self.results_inner, bg=PANEL)
            row.pack(fill="x", padx=6, pady=1)

            icon, colour = ("✦", YELLOW) if kind == "add" else ("·", TEXT_DIM)

            tk.Label(row, text=icon,              bg=PANEL, fg=colour,   font=("Courier", 10, "bold"), width=2).pack(side="left")
            tk.Label(row, text=Path(rel_path).name, bg=PANEL, fg=TEXT,   font=("Courier", 9), anchor="w").pack(side="left", padx=(4, 8))
            tk.Label(row, text=md5,               bg=PANEL, fg=TEXT_HASH, font=("Courier", 8), anchor="e").pack(side="right")

    def _append_error_row(self, rel_path: str, msg: str):
        row = tk.Frame(self.results_inner, bg=PANEL)
        row.pack(fill="x", padx=6, pady=1)
        tk.Label(row, text="✗",                                  bg=PANEL, fg=RED, font=("Courier", 10, "bold"), width=2).pack(side="left")
        tk.Label(row, text=f"{Path(rel_path).name} — {msg}",    bg=PANEL, fg=RED, font=("Courier", 9), anchor="w").pack(side="left", padx=4)

    def _clear_results(self, silent=False):
        for w in self.results_inner.winfo_children():
            w.destroy()
        if not silent:
            self.results_title.config(text="")
            self.clear_btn.pack_forget()

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _flash(self, colour: str):
        self._folder_panel.config(highlightbackground=colour)
        self.after(600, lambda: self._folder_panel.config(highlightbackground=BORDER))


if __name__ == "__main__":
    App().mainloop()
