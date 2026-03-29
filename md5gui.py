#!/usr/bin/env python3
"""
md5gui.py — GUI frontend for the MiNERVA MD5 Database Crawler.
Includes C64-style diagonal striped animation within a rectangular bar.
"""

import hashlib
import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

# ── Palette ───────────────────────────────────────────────────────────────────
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

C64_RAINBOW = [RED, YELLOW, GREEN, BLUE]
MIN_W, MIN_H = 520, 680
DEFAULT_DB = Path(__file__).parent / "md5_database.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _bind_drop(widget, callback):
    try:
        widget.drop_target_register("DND_Files")
        widget.dnd_bind("<<Drop>>", lambda e: callback(e.data.strip("{}")))
    except Exception: pass

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
        except json.JSONDecodeError:
            db_path.rename(db_path.with_suffix(".json.bak"))
    return {}

def _save_db(db: dict, db_path: Path) -> None:
    tmp = db_path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(db, fh, indent=2, ensure_ascii=False)
    tmp.replace(db_path)

def _parse_md5sum(md5sum_path: Path) -> tuple[dict, list]:
    """
    Parse a .md5sum file into a {md5: filepath} dict.
    Returns (entries, errors). Supports one- and two-space separators.
    """
    entries, errors = {}, []
    with open(md5sum_path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            if len(line) < 34 or not all(c in "0123456789abcdefABCDEF" for c in line[:32]):
                errors.append(f"Line {lineno}: unrecognised format")
                continue
            md5 = line[:32].lower()
            rest = line[32:]
            if rest.startswith("  "):
                filepath = rest[2:].strip()
            elif rest.startswith(" "):
                filepath = rest[1:].strip()
            else:
                errors.append(f"Line {lineno}: no space after hash")
                continue
            if filepath and md5 not in entries:
                entries[md5] = filepath
    return entries, errors

# ── App ───────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MiNERVA — MD5 Crawler")
        self.configure(bg=BG)
        self.minsize(MIN_W, MIN_H)
        self.geometry("580x700")

        self.db_path = DEFAULT_DB
        self._running = False
        self._current_progress = (0, 0)
        self._anim_step = 0

        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=PANEL, height=58)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="MiNERVA", bg=PANEL, fg=PURPLE, font=("Courier", 20, "bold")).pack(side="left", padx=10)
        tk.Label(hdr, text=" MD5 Crawler", bg=PANEL, fg=TEXT_DIM, font=("Courier", 13)).pack(side="left")
        tk.Frame(self, bg=PURPLE, height=2).pack(fill="x", side="top")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(7, weight=1)

        # DB Selection
        db_frame = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        db_frame.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.db_var = tk.StringVar(value=str(self.db_path.name))
        tk.Label(db_frame, text="DB:", bg=PANEL, fg=TEXT_DIM, font=("Courier", 10, "bold")).pack(side="left", padx=(10, 5))
        tk.Label(db_frame, textvariable=self.db_var, bg=PANEL, fg=TEXT, font=("Courier", 9), anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(db_frame, text="IMPORT .MD5SUM", bg=PANEL, fg=YELLOW, relief="flat", font=("Courier", 9, "bold"), command=self._import_md5sum).pack(side="right", padx=(0, 2), pady=5)
        tk.Button(db_frame, text="SET OUTPUT", bg=PANEL, fg=BLUE, relief="flat", font=("Courier", 9, "bold"), command=self._browse_db).pack(side="right", padx=5, pady=5)

        # Folder Drop
        self.folder_panel = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, height=100)
        self.folder_panel.grid(row=1, column=0, sticky="ew")
        self.folder_panel.pack_propagate(False)
        tk.Label(self.folder_panel, text="⬇", bg=PANEL, fg=BORDER, font=("TkDefaultFont", 20)).pack(expand=True)
        tk.Button(self.folder_panel, text="BROWSE SOURCE FOLDER →", bg=PANEL, fg=PURPLE, relief="flat", font=("Courier", 10, "bold"), command=self._browse_folder).pack(pady=(0, 10))
        _bind_drop(self.folder_panel, self._handle_drop)

        self.folder_var = tk.StringVar(value="(no folder selected)")
        tk.Label(body, textvariable=self.folder_var, bg=BG, fg=TEXT_DIM, font=("Courier", 9), anchor="w").grid(row=2, column=0, sticky="ew", pady=(5, 0))

        # Status & Rainbow
        status_panel = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, height=90)
        status_panel.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        status_panel.pack_propagate(False)

        self.pbar_canvas = tk.Canvas(status_panel, bg=PANEL, height=24, highlightthickness=1, highlightbackground=BORDER)
        self.pbar_canvas.pack(fill="x", padx=20, pady=(15, 0))
        self.status_label = tk.Label(status_panel, text="Ready", bg=PANEL, fg=TEXT_DIM, font=("Courier", 10), anchor="w", padx=20)
        self.status_label.pack(fill="x")

        # Run Button
        self.run_btn = tk.Button(body, text="▶  RUN CRAWLER", bg=PURPLE, fg=WHITE, relief="flat", font=("Courier", 11, "bold"), command=self._toggle_crawl)
        self.run_btn.grid(row=4, column=0, sticky="ew", pady=(14, 0))

        # Results
        results_hdr = tk.Frame(body, bg=BG)
        results_hdr.grid(row=6, column=0, sticky="ew", pady=(16, 0))
        self.results_title = tk.Label(results_hdr, text="", bg=BG, fg=TEXT_DIM, font=("Courier", 9, "bold"), anchor="w")
        self.results_title.pack(side="left")

        list_frame = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        list_frame.grid(row=7, column=0, sticky="nsew", pady=(4, 0))
        self.canvas = tk.Canvas(list_frame, bg=PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.results_inner = tk.Frame(self.canvas, bg=PANEL)
        self._cw = self.canvas.create_window((0, 0), window=self.results_inner, anchor="nw")
        self.results_inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._cw, width=e.width))

        # Footer
        footer = tk.Frame(self, bg=BG, padx=24, pady=6)
        footer.pack(fill="x", side="bottom")
        self.progress_var = tk.StringVar(value="")
        tk.Label(footer, textvariable=self.progress_var, bg=BG, fg=BLUE, font=("Courier", 9)).pack(side="right")

    # ── Progress Animation ──

    def _update_pbar(self, current, total):
        self.pbar_canvas.delete("progress")
        if total <= 0: return

        w, h = self.pbar_canvas.winfo_width(), 24
        progress_width = (current / total) * w
        stripe_w = 25  # Width of each color band
        shear_offset = h * 0.577 # tan(30)

        # Start far enough left to cover the slant at the start
        x = -shear_offset - (self._anim_step % (stripe_w * len(C64_RAINBOW)))

        while x < progress_width:
            for color in C64_RAINBOW:
                if x > progress_width: break

                # Calculate polygon points for the diagonal slice
                # Points: Top-Left, Top-Right, Bottom-Right, Bottom-Left
                pts = [
                    x, 0,
                    x + stripe_w, 0,
                    x + stripe_w - shear_offset, h,
                    x - shear_offset, h
                ]

                # Clip the polygon manually to the current progress boundary
                # (Simple way: Draw everything, then a black box over the rest)
                self.pbar_canvas.create_polygon(pts, fill=color, outline="", tags="progress")
                x += stripe_w

        # Overlay to hide stripes beyond the progress width (the "unfilled" part)
        self.pbar_canvas.create_rectangle(progress_width, 0, w, h, fill=PANEL, outline="", tags="progress")

    def _animate_rainbow(self):
        if self._running:
            self._anim_step += 2 # Speed of flow
            self._update_pbar(*self._current_progress)
            self.after(50, self._animate_rainbow)

    # ── Logic ──

    def _browse_db(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if path:
            self.db_path = Path(path)
            self.db_var.set(self.db_path.name)

    def _import_md5sum(self):
        # 1. Pick the source .md5sum file
        src = filedialog.askopenfilename(
            title="Select .md5sum file to import",
            filetypes=[("MD5 sum files", "*.md5sum *.md5 *.txt"), ("All files", "*.*")],
        )
        if not src:
            return
        src_path = Path(src)

        # 2. Pick the output / merge target JSON
        default_out = src_path.with_suffix(".json")
        dst = filedialog.asksaveasfilename(
            title="Save imported database as…",
            initialfile=default_out.name,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
        )
        if not dst:
            return
        dst_path = Path(dst)

        # 3. Parse, merge if target already exists, save — all on a worker thread
        self.status_label.config(text="Importing…", fg=TEXT_DIM)
        self.progress_var.set("parsing .md5sum…")

        def _do_import():
            try:
                entries, errors = _parse_md5sum(src_path)

                existing = _load_db(dst_path) if dst_path.exists() else {}
                before   = len(existing)
                existing.update(entries)
                added    = len(existing) - before
                dupes    = len(entries) - added

                _save_db(existing, dst_path)

                summary = f"✔ {added} added · {dupes} dupes skipped · {len(errors)} errors"
                self.after(0, lambda: self.status_label.config(text=summary, fg=GREEN))
                self.after(0, self._clear_results)
                self.after(0, lambda: self.results_title.config(text=f"IMPORT — {src_path.name}"))

                # Show each imported entry in the results list
                for md5, label in entries.items():
                    kind = "skip" if md5 in (existing.keys() - entries.keys()) else "add"
                    self.after(0, self._append_row, label, md5, "add")

                for err in errors:
                    self.after(0, self._append_error_row, err, "parse error")

            except Exception as e:
                self.after(0, lambda: self.status_label.config(text=f"Import failed: {e}", fg=RED))
            finally:
                self.after(0, lambda: self.progress_var.set(""))

        threading.Thread(target=_do_import, daemon=True).start()

    def _toggle_crawl(self):
        if self._running:
            self._running = False
            return
        if not hasattr(self, "_folder_path"): return
        self._running = True
        self.run_btn.config(text="■  STOP CRAWLER", bg=RED)
        self._clear_results()
        self._animate_rainbow()
        threading.Thread(target=self._do_crawl, daemon=True).start()

    def _do_crawl(self):
        folder, db_file = self._folder_path, self.db_path
        db_data = _load_db(db_file)
        all_files = [p for p in folder.rglob("*") if p.is_file()]
        total = len(all_files)

        self.after(0, lambda: self.results_title.config(text=f"RESULTS — {folder.name}"))
        added = skipped = 0

        for i, filepath in enumerate(all_files, 1):
            if not self._running: break
            rel = str(filepath.relative_to(folder))
            self._current_progress = (i, total)
            self.after(0, lambda i=i: self.progress_var.set(f"hashing {i}/{total}…"))

            try:
                md5 = _md5_of_file(filepath)
                if md5 in db_data:
                    skipped += 1
                    self.after(0, self._append_row, rel, md5, "skip")
                else:
                    db_data[md5] = rel
                    added += 1
                    self.after(0, self._append_row, rel, md5, "add")
                if i % 10 == 0: _save_db(db_data, db_file)
            except Exception as e:
                self.after(0, self._append_error_row, rel, str(e))

        _save_db(db_data, db_file)
        self._running = False
        self.after(0, lambda: self.status_label.config(text=f"✔ {added} added · {skipped} skipped", fg=GREEN))
        self.after(0, lambda: self.progress_var.set(""))
        self.after(0, lambda: self.run_btn.config(text="▶  RUN CRAWLER", bg=PURPLE))

    def _append_row(self, rel_path, md5, kind):
        # Indent the following lines relative to the 'def' above
        children = self.results_inner.winfo_children()
        if len(children) >= 500:
            children[0].destroy()

        row = tk.Frame(self.results_inner, bg=PANEL)
        row.pack(fill="x", padx=6, pady=1)
        icon, colour = ("✦", YELLOW) if kind == "add" else ("·", TEXT_DIM)
        tk.Label(row, text=icon, bg=PANEL, fg=colour, font=("Courier", 10, "bold"), width=2).pack(side="left")
        tk.Label(row, text=Path(rel_path).name, bg=PANEL, fg=TEXT, font=("Courier", 9), anchor="w").pack(side="left", padx=4)
        tk.Label(row, text=md5, bg=PANEL, fg=TEXT_HASH, font=("Courier", 8), anchor="e").pack(side="right")

    def _append_error_row(self, rel_path, msg):
        # Indent these as well
        children = self.results_inner.winfo_children()
        if len(children) >= 500:
            children[0].destroy()

        row = tk.Frame(self.results_inner, bg=PANEL)
        row.pack(fill="x", padx=6, pady=1)
        tk.Label(row, text="✗", bg=PANEL, fg=RED, font=("Courier", 10, "bold"), width=2).pack(side="left")
        tk.Label(row, text=f"{Path(rel_path).name} — {msg}", bg=PANEL, fg=RED, font=("Courier", 9), anchor="w").pack(side="left", padx=4)
    def _clear_results(self):
        for w in self.results_inner.winfo_children(): w.destroy()

    def _browse_folder(self):
        folder = filedialog.askdirectory()
        if folder: self._set_folder(folder)

    def _handle_drop(self, path):
        if Path(path).is_dir(): self._set_folder(path)

    def _set_folder(self, folder):
        self._folder_path = Path(folder)
        self.folder_var.set(folder)

if __name__ == "__main__":
    App().mainloop()
