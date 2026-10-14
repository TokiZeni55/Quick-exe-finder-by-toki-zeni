import os
import sys
import ctypes
import threading
import queue
import tkinter as tk
from ctypes import wintypes
from tkinter import filedialog, messagebox

import customtkinter as ctk


# ============================================================
# THEMES
# ============================================================

THEMES = {
    "Dark": {
        "mode": "dark", "bg": "#17191f", "panel": "#22252d",
        "text": "#f2f4f8", "muted": "#a4a9b5",
        "accent": "#5b8cff", "hover": "#4775d1",
    },
    "Thunder": {
        "mode": "dark", "bg": "#101820", "panel": "#192832",
        "text": "#ecf8ff", "muted": "#a3bac8",
        "accent": "#00b8d9", "hover": "#008fa8",
    },
    "Lite": {
        "mode": "light", "bg": "#f4f6f9", "panel": "#ffffff",
        "text": "#202630", "muted": "#697386",
        "accent": "#3974d8", "hover": "#2e60b4",
    },
    "Neon": {
        "mode": "dark", "bg": "#100d19", "panel": "#1c1529",
        "text": "#f8f0ff", "muted": "#bba9ce",
        "accent": "#d946ef", "hover": "#a928bf",
    },
}


# ============================================================
# WINDOWS EXE ICON EXTRACTION
# If icon extraction fails, the app uses an EXE text icon.
# ============================================================

class SHFILEINFO(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HANDLE),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", wintypes.WCHAR * 260),
        ("szTypeName", wintypes.WCHAR * 80),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HANDLE),
        ("hbmColor", wintypes.HANDLE),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", wintypes.LONG),
        ("bmWidth", wintypes.LONG),
        ("bmHeight", wintypes.LONG),
        ("bmWidthBytes", wintypes.LONG),
        ("bmPlanes", wintypes.WORD),
        ("bmBitsPixel", wintypes.WORD),
        ("bmBits", ctypes.c_void_p),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", ctypes.c_ubyte),
        ("rgbGreen", ctypes.c_ubyte),
        ("rgbRed", ctypes.c_ubyte),
        ("rgbReserved", ctypes.c_ubyte),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", RGBQUAD * 1),
    ]


def extract_exe_icon(path, background):
    """Extract an EXE icon, returning None if extraction fails."""
    if sys.platform != "win32":
        return None

    icon_handle = None
    icon_info = None
    dc = None
    user32 = None
    gdi32 = None

    try:
        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        shell32.SHGetFileInfoW.restype = ctypes.c_size_t
        shell32.SHGetFileInfoW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(SHFILEINFO),
            wintypes.UINT,
            wintypes.UINT,
        ]

        info = SHFILEINFO()

        result = shell32.SHGetFileInfoW(
            path,
            0,
            ctypes.byref(info),
            ctypes.sizeof(info),
            0x100 | 0x1,
        )

        if not result or not info.hIcon:
            return None

        icon_handle = info.hIcon

        user32.GetIconInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ICONINFO),
        ]
        user32.GetIconInfo.restype = wintypes.BOOL

        icon_info = ICONINFO()

        if not user32.GetIconInfo(
            icon_handle, ctypes.byref(icon_info)
        ):
            return None

        if not icon_info.hbmColor:
            return None

        gdi32.GetObjectW.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        gdi32.GetObjectW.restype = ctypes.c_int

        bitmap = BITMAP()

        if not gdi32.GetObjectW(
            icon_info.hbmColor,
            ctypes.sizeof(bitmap),
            ctypes.byref(bitmap),
        ):
            return None

        width = bitmap.bmWidth
        height = bitmap.bmHeight

        if not (1 <= width <= 256 and 1 <= height <= 256):
            return None

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        pixels = ctypes.create_string_buffer(width * height * 4)
        dc = user32.GetDC(None)

        if not dc:
            return None

        gdi32.GetDIBits.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            wintypes.UINT,
            wintypes.UINT,
            ctypes.c_void_p,
            ctypes.POINTER(BITMAPINFO),
            wintypes.UINT,
        ]
        gdi32.GetDIBits.restype = ctypes.c_int

        lines = gdi32.GetDIBits(
            dc,
            icon_info.hbmColor,
            0,
            height,
            pixels,
            ctypes.byref(bmi),
            0,
        )

        if lines != height:
            return None

        raw = pixels.raw

        bg_r = int(background[1:3], 16)
        bg_g = int(background[3:5], 16)
        bg_b = int(background[5:7], 16)

        has_alpha = any(raw[i] for i in range(3, len(raw), 4))
        rgb = bytearray()

        for i in range(0, len(raw), 4):
            blue = raw[i]
            green = raw[i + 1]
            red = raw[i + 2]
            alpha = raw[i + 3] if has_alpha else 255

            red = (red * alpha + bg_r * (255 - alpha)) // 255
            green = (green * alpha + bg_g * (255 - alpha)) // 255
            blue = (blue * alpha + bg_b * (255 - alpha)) // 255

            rgb.extend((red, green, blue))

        ppm = (
            f"P6\n{width} {height}\n255\n".encode("ascii")
            + bytes(rgb)
        )

        return tk.PhotoImage(data=ppm, format="PPM")

    except Exception:
        return None

    finally:
        try:
            if dc and user32:
                user32.ReleaseDC(None, dc)
        except Exception:
            pass

        try:
            if icon_info and gdi32:
                if icon_info.hbmColor:
                    gdi32.DeleteObject(icon_info.hbmColor)
                if icon_info.hbmMask:
                    gdi32.DeleteObject(icon_info.hbmMask)
        except Exception:
            pass

        try:
            if icon_handle and user32:
                user32.DestroyIcon(icon_handle)
        except Exception:
            pass


# ============================================================
# MAIN APP
# ============================================================

class ExeFinder(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("EXE Finder")
        self.geometry("1000x650")
        self.minsize(760, 500)

        self.theme_name = "Thunder"
        self.theme = THEMES[self.theme_name]

        self.folder = ""
        self.files = []
        self.checked = set()
        self.scanning = False
        self.cancel_scan = threading.Event()
        self.events = queue.Queue()
        self.icon_cache = {}

        ctk.set_appearance_mode(self.theme["mode"])
        ctk.set_default_color_theme("blue")

        self._build_ui()
        self.apply_theme()
        self.after(100, self.process_events)

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.header = ctk.CTkFrame(self, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.header,
            text="EXE Finder ⚡",
            font=ctk.CTkFont(size=27, weight="bold"),
        ).grid(
            row=0, column=0, padx=18, pady=(14, 0), sticky="w"
        )

        ctk.CTkLabel(
            self.header,
            text="Find executables. Create shortcuts. Keep it simple.",
            font=ctk.CTkFont(size=12),
        ).grid(
            row=1, column=0, padx=20, pady=(0, 12), sticky="w"
        )

        self.theme_menu = ctk.CTkOptionMenu(
            self.header,
            values=list(THEMES.keys()),
            command=self.change_theme,
            width=125,
        )
        self.theme_menu.set("Thunder")
        self.theme_menu.grid(row=0, column=1, rowspan=2, padx=18)

        self.top = ctk.CTkFrame(self)
        self.top.grid(
            row=1, column=0, padx=14, pady=10, sticky="ew"
        )
        self.top.grid_columnconfigure(0, weight=1)

        self.folder_label = ctk.CTkLabel(
            self.top,
            text="Choose a folder to begin.",
            anchor="w",
            wraplength=850,
        )
        self.folder_label.grid(
            row=0, column=0, columnspan=5,
            padx=12, pady=(12, 5), sticky="ew",
        )

        self.choose_btn = ctk.CTkButton(
            self.top,
            text="Choose Folder",
            command=self.choose_folder,
            width=125,
        )
        self.choose_btn.grid(row=1, column=0, padx=5, pady=10)

        self.scan_btn = ctk.CTkButton(
            self.top,
            text="Scan for EXEs",
            command=self.start_scan,
            width=125,
        )
        self.scan_btn.grid(row=1, column=1, padx=5, pady=10)

        self.cancel_btn = ctk.CTkButton(
            self.top,
            text="Cancel",
            command=self.cancel,
            width=85,
            state="disabled",
        )
        self.cancel_btn.grid(row=1, column=2, padx=5, pady=10)

        self.all_btn = ctk.CTkButton(
            self.top,
            text="Select All",
            command=self.select_all,
            width=95,
        )
        self.all_btn.grid(row=1, column=3, padx=5, pady=10)

        self.none_btn = ctk.CTkButton(
            self.top,
            text="Select None",
            command=self.select_none,
            width=100,
        )
        self.none_btn.grid(row=1, column=4, padx=5, pady=10)

        self.results_panel = ctk.CTkFrame(self)
        self.results_panel.grid(
            row=2, column=0, padx=14, pady=(0, 8), sticky="nsew"
        )
        self.results_panel.grid_columnconfigure(0, weight=1)
        self.results_panel.grid_rowconfigure(1, weight=1)

        self.count_label = ctk.CTkLabel(
            self.results_panel,
            text="Found: 0 EXE files",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.count_label.grid(
            row=0, column=0, padx=12, pady=8, sticky="w"
        )

        self.list_frame = ctk.CTkScrollableFrame(self.results_panel)
        self.list_frame.grid(
            row=1, column=0, padx=8, pady=(0, 8), sticky="nsew"
        )
        self.list_frame.grid_columnconfigure(2, weight=1)

        self.status = ctk.CTkLabel(
            self,
            text="Ready — no background scanning.",
            anchor="w",
        )
        self.status.grid(
            row=3, column=0, padx=18, pady=4, sticky="ew"
        )

        self.shortcut_btn = ctk.CTkButton(
            self,
            text="Add Selected to Desktop",
            command=self.make_shortcuts,
            width=210,
        )
        self.shortcut_btn.grid(row=4, column=0, pady=(3, 12))

        self.credit = ctk.CTkLabel(
            self,
            text="ⓘ",
            cursor="hand2",
            font=ctk.CTkFont(size=12),
        )
        self.credit.place(relx=0.975, rely=0.975, anchor="se")
        self.credit.bind("<Button-1>", self.easter_egg)

    # --------------------------------------------------------
    # THEMING
    # --------------------------------------------------------

    def apply_theme(self):
        t = self.theme
        self.configure(fg_color=t["bg"])

        for frame in (self.header, self.top, self.results_panel):
            frame.configure(fg_color=t["panel"])

        self.list_frame.configure(fg_color=t["bg"])
        self.folder_label.configure(text_color=t["text"])
        self.count_label.configure(text_color=t["text"])
        self.status.configure(text_color=t["muted"])
        self.credit.configure(text_color=t["muted"])

        for button in (
            self.choose_btn, self.scan_btn, self.cancel_btn,
            self.all_btn, self.none_btn, self.shortcut_btn,
        ):
            button.configure(
                fg_color=t["accent"],
                hover_color=t["hover"],
                text_color="#ffffff",
            )

        self.theme_menu.configure(
            fg_color=t["accent"],
            button_color=t["accent"],
            button_hover_color=t["hover"],
        )

        self.render_files()

    def change_theme(self, name):
        self.theme_name = name
        self.theme = THEMES[name]
        ctk.set_appearance_mode(self.theme["mode"])
        self.icon_cache.clear()
        self.apply_theme()

    # --------------------------------------------------------
    # FOLDER SELECTION AND SCANNING
    # --------------------------------------------------------

    def choose_folder(self):
        if self.scanning:
            return

        folder = filedialog.askdirectory(title="Choose folder to scan")
        if not folder:
            return

        self.folder = os.path.abspath(folder)
        self.folder_label.configure(text=f"Folder: {self.folder}")

        self.files.clear()
        self.checked.clear()
        self.icon_cache.clear()
        self.render_files()

        self.count_label.configure(text="Found: 0 EXE files")
        self.status.configure(text="Folder selected. Ready to scan.")

    def start_scan(self):
        if self.scanning:
            return

        if not self.folder or not os.path.isdir(self.folder):
            messagebox.showinfo("EXE Finder", "Choose a folder first.")
            return

        self.files.clear()
        self.checked.clear()
        self.icon_cache.clear()
        self.render_files()
        self.count_label.configure(text="Found: 0 EXE files")

        self.cancel_scan.clear()
        self.scanning = True

        self.scan_btn.configure(state="disabled")
        self.choose_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.status.configure(
            text="Scanning selected folder and subfolders..."
        )

        threading.Thread(
            target=self.scan_worker,
            args=(self.folder,),
            daemon=True,
        ).start()

    def scan_worker(self, root):
        found = 0

        try:
            for current, dirs, filenames in os.walk(
                root, followlinks=False
            ):
                if self.cancel_scan.is_set():
                    break

                dirs[:] = [
                    d for d in dirs
                    if not os.path.islink(os.path.join(current, d))
                ]

                for filename in filenames:
                    if self.cancel_scan.is_set():
                        break

                    if filename.lower().endswith(".exe"):
                        path = os.path.abspath(
                            os.path.join(current, filename)
                        )
                        self.events.put(("file", path))
                        found += 1

        except Exception as exc:
            self.events.put(("scan_error", str(exc)))

        self.events.put((
            "finished",
            (found, self.cancel_scan.is_set()),
        ))

    def process_events(self):
        changed = False

        try:
            while True:
                kind, data = self.events.get_nowait()

                if kind == "file":
                    if data not in self.files:
                        self.files.append(data)
                        changed = True

                elif kind == "scan_error":
                    self.status.configure(text=f"Scan warning: {data}")

                elif kind == "finished":
                    count, cancelled = data
                    self.scanning = False

                    self.scan_btn.configure(state="normal")
                    self.choose_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")

                    message = (
                        "Scan cancelled" if cancelled else "Scan complete"
                    )
                    self.status.configure(
                        text=f"{message} — found {count} EXE files."
                    )
                    changed = True

        except queue.Empty:
            pass

        if changed:
            self.count_label.configure(
                text=f"Found: {len(self.files)} EXE files"
            )
            self.render_files()

        self.after(100, self.process_events)

    def cancel(self):
        if self.scanning:
            self.cancel_scan.set()
            self.status.configure(text="Cancelling scan...")

    # --------------------------------------------------------
    # EXE RESULTS AND ICONS
    # --------------------------------------------------------

    def get_icon(self, path):
        if path not in self.icon_cache:
            self.icon_cache[path] = extract_exe_icon(
                path, self.theme["bg"]
            )
        return self.icon_cache[path]

    def render_files(self):
        if not hasattr(self, "list_frame"):
            return

        for widget in self.list_frame.winfo_children():
            widget.destroy()

        if not self.files:
            ctk.CTkLabel(
                self.list_frame,
                text="No EXE files found yet.",
                text_color=self.theme["muted"],
            ).grid(row=0, column=0, padx=15, pady=20, sticky="w")
            return

        for row, path in enumerate(self.files):
            var = tk.BooleanVar(
                master=self,
                value=(path in self.checked),
            )

            def update_selection(p=path, v=var):
                if v.get():
                    self.checked.add(p)
                else:
                    self.checked.discard(p)

            ctk.CTkCheckBox(
                self.list_frame,
                text="",
                variable=var,
                width=25,
                command=update_selection,
            ).grid(row=row, column=0, padx=(6, 2), pady=6)

            icon = self.get_icon(path)

            if icon is not None:
                icon_widget = tk.Label(
                    self.list_frame,
                    image=icon,
                    bg=self.theme["bg"],
                    bd=0,
                    highlightthickness=0,
                )
                icon_widget.image = icon
            else:
                icon_widget = ctk.CTkLabel(
                    self.list_frame,
                    text="EXE",
                    width=38,
                    text_color=self.theme["accent"],
                    font=ctk.CTkFont(size=11, weight="bold"),
                )

            icon_widget.grid(row=row, column=1, padx=5, pady=5)

            info = ctk.CTkFrame(
                self.list_frame,
                fg_color="transparent",
            )
            info.grid(
                row=row, column=2, padx=5, pady=4, sticky="ew"
            )
            info.grid_columnconfigure(0, weight=1)

            # Filename label
            ctk.CTkLabel(
                info,
                text=os.path.basename(path),
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=self.theme["text"],
            ).grid(row=0, column=0, sticky="ew", padx=4)

            # Full file path label
            ctk.CTkLabel(
                info,
                text=path,
                anchor="w",
                text_color=self.theme["muted"],
                font=ctk.CTkFont(size=10),
            ).grid(row=1, column=0, sticky="ew", padx=4)

            ctk.CTkButton(
                self.list_frame,
                text="Open Folder",
                width=95,
                height=28,
                fg_color=self.theme["accent"],
                hover_color=self.theme["hover"],
                command=lambda p=path: self.open_folder(p),
            ).grid(row=row, column=3, padx=8, pady=5)

    def open_folder(self, path):
        try:
            os.startfile(os.path.dirname(path))
        except Exception as exc:
            messagebox.showerror("Could not open folder", str(exc))

    def select_all(self):
        self.checked.update(self.files)
        self.render_files()

    def select_none(self):
        self.checked.clear()
        self.render_files()

    # --------------------------------------------------------
    # DESKTOP SHORTCUTS
    # --------------------------------------------------------

    def make_shortcuts(self):
        selected = [
            p for p in self.files
            if p in self.checked and os.path.isfile(p)
        ]

        if not selected:
            messagebox.showinfo(
                "EXE Finder", "Select at least one EXE."
            )
            return

        try:
            import win32com.client
        except ImportError:
            messagebox.showerror(
                "Missing requirement",
                "Install shortcut support:\n\n"
                "python -m pip install pywin32",
            )
            return

        desktop = os.path.join(
            os.path.expanduser("~"), "Desktop"
        )

        if not os.path.isdir(desktop):
            messagebox.showerror(
                "EXE Finder",
                "Desktop folder not found. It may be redirected by OneDrive.",
            )
            return

        try:
            shell = win32com.client.Dispatch("WScript.Shell")
        except Exception as exc:
            messagebox.showerror(
                "Shortcut error",
                f"Could not initialize shortcuts:\n{exc}",
            )
            return

        created = 0
        skipped = 0
        failed = []

        for path in selected:
            name = os.path.splitext(os.path.basename(path))[0]
            link = os.path.join(desktop, name + ".lnk")

            # Never overwrite an existing shortcut.
            if os.path.exists(link):
                skipped += 1
                continue

            try:
                shortcut = shell.CreateShortCut(link)
                shortcut.Targetpath = path
                shortcut.WorkingDirectory = os.path.dirname(path)
                shortcut.Description = f"Shortcut to {name}"
                shortcut.IconLocation = path + ",0"
                shortcut.save()
                created += 1
            except Exception as exc:
                failed.append(f"{name}: {exc}")

        summary = (
            f"Created: {created}\n"
            f"Skipped existing names: {skipped}"
        )

        if failed:
            summary += "\n\nFailed:\n" + "\n".join(failed[:5])

        messagebox.showinfo("Shortcut results", summary)
        self.status.configure(
            text=f"Created {created} desktop shortcut(s)."
        )

    # --------------------------------------------------------
    # EASTER EGG
    # --------------------------------------------------------

    def easter_egg(self, _event=None):
        messagebox.showinfo("🤫 Secret!", "Made by Toki ✨")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    try:
        app = ExeFinder()
        app.mainloop()
    except Exception as exc:
        try:
            messagebox.showerror("EXE Finder startup error", str(exc))
        except Exception:
            print(f"EXE Finder startup error: {exc}")
