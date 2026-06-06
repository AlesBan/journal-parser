from __future__ import annotations

import json
import os
import threading
import traceback
from pathlib import Path
from datetime import datetime
from tkinter import BooleanVar, Button, Canvas, Frame, PhotoImage, StringVar, Tk, filedialog, messagebox, ttk

from journal_parser.analyze import analyze_pdf, build_report_path


APP_NAME = "journal-parser"
APP_ID = "journal-parser"


def _find_icon_ico(repo: Path) -> Path | None:
    # Prefer icon from the install root / working directory, then fallback to repo assets.
    try:
        cwd = Path.cwd()
        candidates = [cwd / "app.ico", cwd / "app.png"]
        for p in candidates:
            if p.exists():
                return p
    except Exception:
        pass

    # Repo fallbacks
    candidates = [
        repo / "installer" / "payload" / "app.ico",
        repo / "assets" / "app.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _set_windows_app_user_model_id(app_id: str) -> None:
    # Helps Windows taskbar group the app and use the window icon instead of pythonw.exe icon.
    try:
        import ctypes  # noqa: PLC0415

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def _appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_NAME


def _config_path() -> Path:
    return _appdata_dir() / "config.json"


def _load_config() -> dict:
    p = _config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(cfg: dict) -> None:
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _repo_root() -> Path:
    # This file lives in journal_parser/, so repo root is two levels up.
    return Path(__file__).resolve().parents[1]


def _open_path(path: Path) -> None:
    # Use Windows shell to open file/folder.
    os.startfile(str(path))  # type: ignore[attr-defined]


class App:
    def __init__(self, root: Tk) -> None:
        _set_windows_app_user_model_id(APP_ID)
        self.root = root
        self.root.title("journal-parser")
        self.root.geometry("860x520")
        self.root.minsize(860, 520)

        self.cfg = _load_config()
        self.repo = _repo_root()

        icon_path = _find_icon_ico(self.repo)
        if icon_path:
            try:
                # iconbitmap expects .ico; for .png we use iconphoto.
                if icon_path.suffix.lower() == ".ico":
                    self.root.iconbitmap(default=str(icon_path))
                else:
                    self._icon_img = PhotoImage(file=str(icon_path))
                    self.root.iconphoto(True, self._icon_img)
            except Exception:
                pass

        # Defaults should not depend on previous runs/config.
        self.pdf_path = StringVar(value="")
        self.out_dir = StringVar(value=str((self.repo / "reports").resolve()))
        # OCR plugin can take minutes (network); keep it opt-in.
        self.use_ocr = BooleanVar(value=bool(self.cfg.get("use_ocr", False)))
        self.last_reports: list[Path] = []

        self._build_ui()

    def _build_ui(self) -> None:
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill="both", expand=True)

        # Row 1: PDF label + (path + buttons) all inside one frame
        pdf_outer = Frame(frm, bd=1, relief="solid")
        pdf_outer.pack(fill="x")
        pdf_outer.columnconfigure(0, weight=1)

        inner1 = ttk.Frame(pdf_outer, padding=(10, 8))
        inner1.grid(row=0, column=0, sticky="ew")
        inner1.columnconfigure(1, weight=1)

        ttk.Label(inner1, text="Файл (PDF)").grid(row=0, column=0, sticky="w")
        self.pdf_entry = ttk.Entry(inner1, textvariable=self.pdf_path, state="readonly")
        self.pdf_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))

        btns = ttk.Frame(inner1)
        btns.grid(row=0, column=2, sticky="e")
        ttk.Button(btns, text="Выбрать…", command=self.pick_pdf).pack(side="top", fill="x")
        # Use classic Tk button for a green background on Windows themes
        self._analyze_colors = {
            "normal_bg": "#c9f2d8",
            "hover_bg": "#b2ebc7",
            "pressed_bg": "#9ee3b8",
            "disabled_bg": "#e6e6e6",
        }
        self.btn_analyze = Button(
            btns,
            text="Анализировать",
            command=self.run_analyze,
            bg=self._analyze_colors["normal_bg"],
            fg="black",
            activebackground=self._analyze_colors["pressed_bg"],
            activeforeground="black",
            relief="raised",
            bd=1,
            padx=10,
            pady=6,
        )
        self.btn_analyze.pack(side="top", fill="x", pady=(6, 0))
        self.btn_analyze.bind(
            "<Enter>",
            lambda _e: self.btn_analyze.configure(bg=self._analyze_colors["hover_bg"])
            if str(self.btn_analyze["state"]) == "normal"
            else None,
        )
        self.btn_analyze.bind(
            "<Leave>",
            lambda _e: self.btn_analyze.configure(bg=self._analyze_colors["normal_bg"])
            if str(self.btn_analyze["state"]) == "normal"
            else None,
        )
        self.btn_analyze.bind(
            "<ButtonPress-1>",
            lambda _e: self.btn_analyze.configure(bg=self._analyze_colors["pressed_bg"])
            if str(self.btn_analyze["state"]) == "normal"
            else None,
        )
        self.btn_analyze.bind(
            "<ButtonRelease-1>",
            lambda _e: self.btn_analyze.configure(bg=self._analyze_colors["hover_bg"])
            if str(self.btn_analyze["state"]) == "normal"
            else None,
        )

        # OCR toggle (opt-in)
        ocr_row = ttk.Frame(frm)
        ocr_row.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(
            ocr_row,
            text="Использовать OCR (медленно, если PDF скан)",
            variable=self.use_ocr,
            command=lambda: _save_config({**self.cfg, "use_ocr": bool(self.use_ocr.get())}),
        ).pack(side="left")

        # Row 2: Output directory (boxed) + include/exclude editors (boxed)
        row2 = ttk.Frame(frm)
        row2.pack(fill="x", pady=(10, 0))
        row2.columnconfigure(0, weight=1)

        out_box = Frame(row2, bd=1, relief="solid")
        out_box.grid(row=0, column=0, sticky="ew")
        out_box.columnconfigure(0, weight=1)
        out_inner = ttk.Frame(out_box, padding=(10, 8))
        out_inner.grid(row=0, column=0, sticky="ew")
        out_inner.columnconfigure(1, weight=1)

        ttk.Label(out_inner, text="Папка вывода").grid(row=0, column=0, sticky="w")
        self.out_entry = ttk.Entry(out_inner, textvariable=self.out_dir, state="readonly")
        self.out_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(out_inner, text="Открыть папку вывода", command=self.open_out_dir).grid(
            row=0, column=2, sticky="e"
        )

        edit_btn_box = Frame(row2, bd=1, relief="solid")
        edit_btn_box.grid(row=0, column=1, sticky="e", padx=(8, 0))
        edit_btn_inner = ttk.Frame(edit_btn_box, padding=(10, 8))
        edit_btn_inner.pack()
        ttk.Button(edit_btn_inner, text="Редактировать include", command=self.open_include).pack(side="left")
        ttk.Button(edit_btn_inner, text="Редактировать exclude", command=self.open_exclude).pack(side="left", padx=(8, 0))

        # History (scrollable rows with per-report button) inside a frame
        self.history_container = Frame(frm, bd=1, relief="solid")
        self.history_container.pack(fill="both", expand=True, pady=(14, 0))

        self.history_canvas = Canvas(self.history_container, borderwidth=0, highlightthickness=0)
        self.history_scroll = ttk.Scrollbar(
            self.history_container, orient="vertical", command=self.history_canvas.yview
        )
        self.history_canvas.configure(yscrollcommand=self.history_scroll.set)

        self.history_scroll.pack(side="right", fill="y")
        self.history_canvas.pack(side="left", fill="both", expand=True)

        self.history_rows = ttk.Frame(self.history_canvas)
        self._history_window = self.history_canvas.create_window((0, 0), window=self.history_rows, anchor="nw")

        def _clamp_scroll():
            bbox = self.history_canvas.bbox("all")
            if not bbox:
                self.history_canvas.yview_moveto(0)
                return
            content_h = bbox[3] - bbox[1]
            view_h = self.history_canvas.winfo_height()
            if content_h <= max(1, view_h):
                self.history_canvas.yview_moveto(0)
                return
            y0, y1 = self.history_canvas.yview()
            span = y1 - y0
            if y0 < 0:
                self.history_canvas.yview_moveto(0)
            elif y1 > 1:
                self.history_canvas.yview_moveto(max(0.0, 1.0 - span))

        def _on_configure(_evt=None):
            self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
            _clamp_scroll()

        def _on_canvas_configure(evt):
            self.history_canvas.itemconfigure(self._history_window, width=evt.width)
            _clamp_scroll()

        self.history_rows.bind("<Configure>", _on_configure)
        self.history_canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(evt):
            # Windows reports delta in multiples of 120
            delta = int(-1 * (evt.delta / 120))
            self.history_canvas.yview_scroll(delta, "units")
            _clamp_scroll()

        def _bind_wheel(_evt=None):
            self.history_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_wheel(_evt=None):
            self.history_canvas.unbind_all("<MouseWheel>")

        # Bind wheel only when pointer is over the history area.
        self.history_canvas.bind("<Enter>", _bind_wheel)
        self.history_canvas.bind("<Leave>", _unbind_wheel)

        # History starts empty

    def _add_info_row(self, text: str) -> None:
        if list(self.history_rows.winfo_children()):
            ttk.Separator(self.history_rows, orient="horizontal").pack(fill="x", pady=6)
        inner = ttk.Frame(self.history_rows, padding=(10, 8))
        inner.pack(fill="x")
        ttk.Label(inner, text=text).pack(side="left")

    def _add_report_row(self, report: Path, ts: datetime | None = None) -> None:
        if list(self.history_rows.winfo_children()):
            ttk.Separator(self.history_rows, orient="horizontal").pack(fill="x", pady=6)
        inner = ttk.Frame(self.history_rows, padding=(10, 8))
        inner.pack(fill="x")

        inner.columnconfigure(2, weight=1)
        time_text = (ts or datetime.now()).strftime("%H:%M:%S")

        ttk.Label(inner, text=time_text).grid(row=0, column=0, sticky="w")
        ttk.Separator(inner, orient="vertical").grid(row=0, column=1, sticky="ns", padx=10)
        ttk.Label(inner, text=report.name).grid(row=0, column=2, sticky="w")
        ttk.Separator(inner, orient="vertical").grid(row=0, column=3, sticky="ns", padx=10)
        ttk.Button(inner, text="Открыть", command=lambda p=report: _open_path(p)).grid(
            row=0, column=4, sticky="e"
        )
        self.history_canvas.yview_moveto(1.0)

    def pick_pdf(self) -> None:
        initial = self.cfg.get("last_pdf_dir") or ""
        if initial and not Path(initial).exists():
            initial = ""
        p = filedialog.askopenfilename(
            title="Выбрать PDF-файл",
            initialdir=initial or None,
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        )
        if not p:
            return
        self.pdf_path.set(p)
        self.cfg["last_pdf_dir"] = str(Path(p).parent)
        _save_config(self.cfg)

    def open_out_dir(self) -> None:
        p = Path(self.out_dir.get()).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        _open_path(p)

    def open_include(self) -> None:
        _open_path((self.repo / "filters" / "include.txt").resolve())

    def open_exclude(self) -> None:
        _open_path((self.repo / "filters" / "exclude.txt").resolve())

    def _set_busy(self, busy: bool) -> None:
        self.btn_analyze.configure(state=("disabled" if busy else "normal"))
        if busy:
            self.btn_analyze.configure(bg=self._analyze_colors["disabled_bg"])
        else:
            self.btn_analyze.configure(bg=self._analyze_colors["normal_bg"])

    def run_analyze(self) -> None:
        pdf = Path(self.pdf_path.get().strip().strip('"'))
        if not pdf.exists():
            messagebox.showerror("journal-parser", "PDF-файл не найден.")
            return

        out_dir = Path(self.out_dir.get().strip().strip('"') or (self.repo / "reports")).resolve()
        include_path = (self.repo / "filters" / "include.txt").resolve()
        exclude_path = (self.repo / "filters" / "exclude.txt").resolve()

        # Persist only what helps UX across runs; output dir is derived from the current repo root.

        self._set_busy(True)
        started_at = datetime.now()
        predicted_report = build_report_path(out_dir=out_dir, doc_title=pdf.name, now=started_at).resolve()

        if predicted_report.exists():
            replace = messagebox.askyesno(
                "journal-parser",
                f"Файл отчёта уже существует:\n{predicted_report.name}\n\nЗаменить его?",
            )
            if not replace:
                self._set_busy(False)
                return

        # OCR is internal; UI stays minimal. We auto-use plugin only when needed.
        ocr_plugin = (self.repo / "ocr_plugins" / "imagetoword_api_plugin.py").resolve()
        ocr_plugin_path = ocr_plugin if bool(self.use_ocr.get()) else None

        def worker() -> None:
            try:
                report = analyze_pdf(
                    pdf,
                    out_dir=out_dir,
                    include_path=include_path,
                    exclude_path=exclude_path,
                    ocr_plugin_path=ocr_plugin_path,
                    ocr_force=False,
                    now=started_at,
                )
                self.last_reports.append(report)

                def done_ok() -> None:
                    self._add_report_row(report, ts=datetime.now())
                    self._set_busy(False)

                self.root.after(0, done_ok)
            except BaseException as e:
                # Includes SystemExit, KeyboardInterrupt, etc.
                tb = traceback.format_exc()

                def done_err() -> None:
                    messagebox.showerror("journal-parser", str(e))
                    self._set_busy(False)

                self.root.after(0, done_err)

        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    root = Tk()
    ttk.Style().theme_use("vista" if "vista" in ttk.Style().theme_names() else "default")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

