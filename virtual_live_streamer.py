import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess, threading, os, sys, json, time, uuid, shutil, platform, stat, queue, io, re, hashlib, urllib.request, urllib.error

APP = "Virtual Live Streamer"
VERSION = "11.1"
CFG_DIR = os.path.join(os.path.expanduser("~"), ".virtual_live_streamer")
CFG = os.path.join(CFG_DIR, "config.json")
LOG = os.path.join(CFG_DIR, "stream.log")
os.makedirs(CFG_DIR, exist_ok=True)

# Visual system — intentionally darker / cleaner than the old utility-style UI.
BG = "#090B10"
SURFACE = "#11151D"
SURFACE_2 = "#171C25"
SURFACE_3 = "#1D2430"
BORDER = "#202837"
BORDER_HI = "#344052"
TEXT = "#F7F9FC"
MUTED = "#8B95A5"
FAINT = "#5F6978"
RED = "#FF3355"
RED_DARK = "#C92140"
GREEN = "#25D987"
AMBER = "#F5B84B"
BLUE = "#6E8CFF"
BLACK = "#05070A"

SUPABASE_FUNCTION_URL = "https://wcsbtheojjmkbwnttufc.supabase.co/functions/v1/check-license"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_9f6Zyw7JBQe_BhrfKL4_Dw_zdsAyoQz"
WEEKLY_PAYMENT_URL = "https://rzp.io/rzp/fGs40bLg"
MONTHLY_PAYMENT_URL = "https://rzp.io/rzp/HW69fpy"

try:
    from PIL import Image, ImageTk, ImageOps, ImageDraw
    PIL_OK = True
except Exception:
    PIL_OK = False


def load_cfg():
    try:
        with open(CFG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"plan": "Locked", "license_key": "", "video": "", "quality": "720p", "loop": True, "reconnect": True, "license_valid": False, "license_expires_at": ""}


def save_cfg(data):
    try:
        with open(CFG, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def find_bundled():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    candidates = [os.path.join(base, "bin", exe), os.path.join(base, exe)]
    for p in candidates:
        if os.path.isfile(p):
            try:
                os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
            except Exception:
                pass
            return p
    return shutil.which(exe)


def get_ffmpeg(log=lambda _m: None):
    p = find_bundled()
    if p:
        return p
    # Development fallback. Customer builds should always bundle FFmpeg.
    p = shutil.which("ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
    if p:
        return p
    if platform.system() == "Darwin":
        import urllib.request, zipfile
        arch = platform.machine().lower()
        url_arch = "arm64" if arch in ("arm64", "aarch64") else "amd64"
        # Snapshot endpoint is less likely to reject automated build requests than release.
        url = f"https://ffmpeg.martin-riedl.de/redirect/latest/macos/{url_arch}/snapshot/ffmpeg.zip"
        cache = os.path.join(CFG_DIR, "bin")
        target = os.path.join(cache, "ffmpeg")
        try:
            os.makedirs(cache, exist_ok=True)
            log("FFmpeg missing — downloading a local development copy once…")
            req = urllib.request.Request(url, headers={"User-Agent": "VirtualLiveStreamer/6.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = [n for n in z.namelist() if n.endswith("/ffmpeg") or n == "ffmpeg"]
                if not names:
                    raise RuntimeError("FFmpeg binary not found in archive")
                with z.open(names[0]) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            os.chmod(target, os.stat(target).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            return target
        except Exception as e:
            raise RuntimeError(f"FFmpeg setup failed: {e}. Put bin/ffmpeg in the build package for production.")
    raise RuntimeError("FFmpeg is not available. Put bin/ffmpeg.exe (Windows) or bin/ffmpeg (Mac) in the build package.")


class ModernButton(tk.Canvas):
    """Custom rounded button so macOS native controls never make the UI look sharp/washed out."""
    def __init__(self, parent, text, command, bg=SURFACE_3, fg=TEXT, active=SURFACE_3,
                 padx=14, pady=8, font=("Segoe UI", 9, "bold"), radius=10, **kwargs):
        super().__init__(parent, bg=parent.cget("bg"), highlightthickness=0, bd=0,
                         cursor="hand2", height=max(34, pady * 2 + 22), **kwargs)
        self._command = command; self._bg = bg; self._fg = fg; self._active = active
        self._state = "normal"; self._font = font; self._text = text; self._radius = radius
        self._padx = padx; self._pady = pady
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", self._click); self.bind("<Enter>", self._enter); self.bind("<Leave>", self._leave)
        self._draw()

    def _round_rect(self, x1, y1, x2, y2, r, fill, outline=None, width=1):
        pts=[x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
        return self.create_polygon(pts, smooth=True, splinesteps=18, fill=fill, outline=outline, width=width)

    def _draw(self):
        self.delete("all")
        w=max(40,self.winfo_width()); h=max(34,self.winfo_height())
        fill=self._bg if self._state!="disabled" else "#151B24"
        fg=self._fg if self._state!="disabled" else FAINT
        self._round_rect(1,1,w-1,h-1,min(self._radius,h//2),fill,BORDER if self._state!="disabled" else "#1B222D",1)
        self.create_text(w/2,h/2,text=self._text,fill=fg,font=self._font,justify="center")

    def _click(self,_=None):
        if self._state!="disabled" and self._command: self._command()
    def _enter(self,_=None):
        if self._state!="disabled": self._bg=self._active; self._draw()
    def _leave(self,_=None):
        if self._state!="disabled":
            # active color is only hover state; recover original from stored base
            self._bg=getattr(self,"_base_bg",self._bg); self._draw()
    def config(self, cnf=None, **kwargs):
        if cnf: kwargs.update(cnf)
        state=kwargs.pop("state",None)
        if "text" in kwargs: self._text=kwargs.pop("text")
        if "bg" in kwargs: self._bg=kwargs.pop("bg"); self._base_bg=self._bg
        if "fg" in kwargs: self._fg=kwargs.pop("fg")
        if "activebackground" in kwargs: self._active=kwargs.pop("activebackground")
        if "font" in kwargs: self._font=kwargs.pop("font")
        if state is not None: self._state=state
        if kwargs: super().config(**kwargs)
        self._draw()
    def cget(self,key):
        if key=="text": return self._text
        if key=="state": return self._state
        return super().cget(key)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP} {VERSION}")
        self.geometry("1260x860")
        self.minsize(1080, 760)
        self.configure(bg=BG)
        self.cfg = load_cfg()
        self.proc = None
        self.preview_proc = None
        self.preview_stop = False
        self.preview_photo = None
        self.started = None
        self.stop_flag = False
        self.q = queue.Queue()
        self.video = tk.StringVar(value=self.cfg.get("video", ""))
        self.platform = tk.StringVar(value="YouTube")
        self.rtmp = tk.StringVar(value="rtmp://a.rtmp.youtube.com/live2")
        self.key = tk.StringVar()
        self.quality = tk.StringVar(value=self.cfg.get("quality", "720p"))
        self.loop = tk.BooleanVar(value=self.cfg.get("loop", True))
        self.reconnect = tk.BooleanVar(value=self.cfg.get("reconnect", True))
        self.short_boost = tk.BooleanVar(value=self.cfg.get("short_boost", False))
        self.license_key = tk.StringVar(value=self.cfg.get("license_key", ""))
        self.license_valid = bool(self.cfg.get("license_valid", False))
        self.license_expires_at = self.cfg.get("license_expires_at", "")
        self.device_id = self.get_device_id()
        self.license_gate = None
        self.status = tk.StringVar(value="READY")
        self.duration = tk.StringVar(value="00:00:00")
        self.bitrate = tk.StringVar(value="—")
        self.fps = tk.StringVar(value="—")
        self.dropped = tk.StringVar(value="0")
        self.video_name = tk.StringVar(value="No video selected")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.build()
        self.after(100, self.flush_log)
        self.after(1000, self.tick)
        if self.video.get() and os.path.isfile(self.video.get()):
            self.video_name.set(os.path.basename(self.video.get()))
            self.after(250, self.start_preview)
        self.after(350, self.enforce_license_gate)

    # ---------- visual helpers ----------
    def label(self, parent, text=None, fg=TEXT, size=10, bold=False, bg=None, **kw):
        return tk.Label(parent, text=text or "", fg=fg, bg=bg or parent.cget("bg"),
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kw)

    def button(self, parent, text, command, bg=SURFACE_3, fg=TEXT, active=None, padx=14, pady=8, size=9, bold=True):
        return ModernButton(parent, text=text, command=command, bg=bg, fg=fg,
                            active=active or bg, padx=padx, pady=pady,
                            font=("Segoe UI", size, "bold" if bold else "normal"))

    def card(self, parent, **pack):
        outer = tk.Frame(parent, bg="#0B0F15", bd=0, highlightbackground="#1C2532", highlightthickness=1)
        outer.pack(**pack)
        inner = tk.Frame(outer, bg=SURFACE, bd=0, highlightthickness=0)
        inner.pack(padx=1, pady=1, fill="both", expand=True)
        return inner

    def section_title(self, parent, title, subtitle=None):
        row = tk.Frame(parent, bg=SURFACE, height=38)
        row.pack(fill="x", padx=20, pady=(14, 8))
        row.pack_propagate(False)
        self.label(row, title.upper(), fg=TEXT, size=10, bold=True, bg=SURFACE).pack(side="left", pady=5)
        if subtitle:
            self.label(row, subtitle, fg=FAINT, size=8, bg=SURFACE).pack(side="right", pady=5)

    def pill(self, parent, text, fg=TEXT, bg=SURFACE_3):
        return tk.Label(parent, text=text, bg=bg, fg=fg, font=("Segoe UI", 8, "bold"), padx=10, pady=7)

    # ---------- build UI ----------
    def build(self):
        self.geometry("1500x920")
        self.minsize(1180, 760)
        self.configure(bg=BG)

        # ---------- Header ----------
        header = tk.Frame(self, bg=BG, height=72)
        header.pack(fill="x", padx=28, pady=(18, 10))
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left", fill="y")
        logo = tk.Canvas(brand, width=42, height=42, bg=BG, highlightthickness=0)
        logo.pack(side="left", pady=10, padx=(0, 12))
        logo.create_oval(2, 2, 40, 40, fill=RED, outline="")
        logo.create_oval(12, 12, 30, 30, fill=BG, outline="")
        self.label(brand, "VIRTUAL LIVE", size=18, bold=True, bg=BG).pack(side="left", pady=13)
        self.label(brand, "STREAMER", fg=RED, size=18, bold=True, bg=BG).pack(side="left", padx=(6, 0), pady=13)

        hr = tk.Frame(header, bg=BG)
        hr.pack(side="right", fill="y")
        self.pill(hr, "●  VERTICAL 9:16", fg=GREEN, bg="#10271F").pack(side="left", pady=13, padx=(0, 10))
        self.button(hr, f"{self.cfg.get('plan','Locked')}  ·  LICENSE", self.plans,
                    bg=SURFACE_2, fg=TEXT, active=SURFACE_3, padx=16, pady=8, size=8).pack(side="left", pady=10)

        # ---------- Workspace ----------
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 12))
        body.columnconfigure(0, weight=25, minsize=340)
        body.columnconfigure(1, weight=27, minsize=400)
        body.columnconfigure(2, weight=48, minsize=540)
        body.rowconfigure(0, weight=1)

        # SOURCE
        left = self.card(body, side="left", fill="both", expand=True, padx=(0, 9))
        self.section_title(left, "SOURCE", "VIDEO INPUT")

        add = tk.Frame(left, bg="#151B25", height=245, highlightbackground="#293445", highlightthickness=1)
        add.pack(fill="x", padx=18, pady=(0, 16))
        add.pack_propagate(False)
        self.label(add, "+", fg=RED, size=34, bold=True, bg="#151B25").pack(pady=(27, 0))
        self.label(add, "ADD VERTICAL VIDEO", fg=TEXT, size=11, bold=True, bg="#151B25").pack(pady=(1, 0))
        self.label(add, "Drop a video here or browse your computer", fg=MUTED, size=8, bg="#151B25").pack(pady=(7, 0))
        self.label(add, "MP4   ·   MOV   ·   MKV   ·   WEBM", fg=FAINT, size=8, bg="#151B25").pack(pady=(7, 14))
        self.button(add, "BROWSE VIDEO", self.browse, bg=RED, fg="#FFFFFF", active=RED_DARK,
                    padx=28, pady=9, size=9).pack(fill="x", padx=30)

        filebox = tk.Frame(left, bg="#0D1219", highlightbackground="#222C3A", highlightthickness=1)
        filebox.pack(fill="x", padx=18, pady=(0, 18))
        self.label(filebox, "SELECTED VIDEO", fg=FAINT, size=7, bold=True, bg="#0D1219").pack(anchor="w", padx=14, pady=(12, 5))
        self.label(filebox, textvariable=self.video_name, fg=TEXT, size=9, bold=True, bg="#0D1219",
                   anchor="w", wraplength=380, justify="left").pack(fill="x", padx=14, pady=(0, 14))

        self.label(left, "PLAYBACK", fg=FAINT, size=8, bold=True, bg=SURFACE).pack(anchor="w", padx=18, pady=(0, 8))
        self.loop_btn = self.toggle_button(left, "LOOP VIDEO", self.loop)
        self.loop_btn.pack(fill="x", padx=18, pady=(0, 8))
        self.reconnect_btn = self.toggle_button(left, "AUTO RECONNECT", self.reconnect)
        self.reconnect_btn.pack(fill="x", padx=18, pady=(0, 8))
        self.short_boost_btn = self.toggle_button(left, "VERTICAL LIVE BOOST", self.short_boost)
        self.short_boost_btn.pack(fill="x", padx=18, pady=(0, 8))

        info = tk.Frame(left, bg="#0D1219", highlightbackground="#222C3A", highlightthickness=1)
        info.pack(side="bottom", fill="x", padx=18, pady=18)
        self.label(info, "STREAM ENGINE", fg=FAINT, size=7, bold=True, bg="#0D1219").pack(anchor="w", padx=14, pady=(11, 0))
        self.label(info, "FFmpeg  ·  H.264 / AAC", fg=TEXT, size=8, bg="#0D1219").pack(anchor="w", padx=14, pady=(5, 0))
        self.label(info, "9:16 canvas  ·  30 FPS", fg=MUTED, size=8, bg="#0D1219").pack(anchor="w", padx=14, pady=(3, 11))

        # PREVIEW
        center = self.card(body, side="left", fill="both", expand=True, padx=9)
        top = tk.Frame(center, bg=SURFACE)
        top.pack(fill="x", padx=20, pady=(16, 10))
        self.label(top, "LIVE PREVIEW", size=10, bold=True, bg=SURFACE).pack(side="left")
        self.label(top, "VERTICAL CANVAS  ·  9:16", fg=FAINT, size=8, bold=True, bg=SURFACE).pack(side="right")

        stage = tk.Frame(center, bg="#0A0E14", highlightbackground="#1F2936", highlightthickness=1)
        stage.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        stage.bind("<Configure>", self._resize_preview_stage)

        self.preview_stage = stage
        self.phone_shadow = tk.Frame(stage, bg="#020304", highlightthickness=0)
        self.phone_outer = tk.Frame(stage, bg="#263141", highlightthickness=0)
        self.phone_inner = tk.Frame(self.phone_outer, bg="#10151D", highlightthickness=0)
        self.screen = tk.Frame(self.phone_inner, bg=BLACK, highlightthickness=0)
        self.screen.pack(expand=True, padx=12, pady=12)
        self.screen.pack_propagate(False)
        self.preview_label = tk.Label(self.screen, text="SELECT A VERTICAL VIDEO\n\n9 : 16", bg=BLACK, fg=MUTED,
                                      font=("Segoe UI", 10, "bold"), justify="center")
        self.preview_label.pack(fill="both", expand=True)
        self.live_badge = tk.Label(self.screen, text="● READY", bg="#1B2230", fg=MUTED,
                                   font=("Segoe UI", 8, "bold"), padx=11, pady=5)
        self.live_badge.place(relx=.5, rely=.025, anchor="n")
        self.notch = tk.Frame(self.phone_inner, bg="#05070A", height=9)
        self.notch.place(relx=.5, rely=.012, anchor="n", width=82)
        self._resize_preview_stage()
        self.label(center, "LOCAL SOURCE PREVIEW  ·  SAME 9:16 CANVAS SENT TO RTMP",
                   fg=FAINT, size=7, bold=True, bg=SURFACE).pack(pady=(0, 14))

        # RIGHT
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        dest = self.card(right, side="top", fill="x", expand=False, pady=(0, 9))
        self.section_title(dest, "DESTINATION", "RTMP OUTPUT")
        grid = tk.Frame(dest, bg=SURFACE)
        grid.pack(fill="x", padx=20, pady=(0, 16))
        grid.columnconfigure(1, weight=1)
        self.make_combo(grid, "PLATFORM", self.platform, ["YouTube", "Custom RTMP"], 0)
        self.make_entry(grid, "RTMP URL", self.rtmp, 1)
        self.make_entry(grid, "STREAM KEY", self.key, 2, secret=True)
        self.platform.trace_add("write", lambda *_: self.platform_changed())

        quality = self.card(right, side="top", fill="x", expand=False, pady=(0, 9))
        self.section_title(quality, "OUTPUT QUALITY", "VERTICAL")
        qrow = tk.Frame(quality, bg=SURFACE)
        qrow.pack(fill="x", padx=20, pady=(0, 16))
        self.quality_buttons = {}
        for q, desc in [("720p", "720 × 1280   ·   30 FPS"), ("1080p", "1080 × 1920   ·   30 FPS")]:
            b = self.button(qrow, f"{q}\n{desc}", lambda x=q: self.select_quality(x),
                            bg=SURFACE_2, fg=MUTED, active=SURFACE_3, padx=10, pady=10, size=9)
            b.pack(side="left", fill="x", expand=True, padx=(0 if q == "720p" else 10, 0))
            self.quality_buttons[q] = b
        self.select_quality(self.quality.get())

        control = self.card(right, side="top", fill="x", expand=False, pady=(0, 9))
        top2 = tk.Frame(control, bg=SURFACE)
        top2.pack(fill="x", padx=20, pady=(15, 8))
        self.status_lbl = self.label(top2, "●  READY", fg=MUTED, size=11, bold=True, bg=SURFACE)
        self.status_lbl.pack(side="left")
        self.label(top2, "LIVE CONTROL", fg=FAINT, size=8, bold=True, bg=SURFACE).pack(side="right")
        buttons = tk.Frame(control, bg=SURFACE)
        buttons.pack(fill="x", padx=20, pady=(2, 17))
        self.start_btn = self.button(buttons, "●  START LIVE", self.start_clicked, bg=RED, fg="#FFFFFF", active=RED_DARK,
                                     padx=18, pady=14, size=11)
        self.start_btn.pack(fill="x")
        self.stop_btn = self.button(buttons, "■  STOP STREAM", self.stop_clicked, bg="#202938", fg=MUTED,
                                    active="#293444", padx=18, pady=11, size=9)
        self.stop_btn.pack(fill="x", pady=(9, 0))
        self.stop_btn.config(state="disabled")

        log_card = self.card(right, side="top", fill="both", expand=True)
        self.section_title(log_card, "ACTIVITY", "FFMPEG")
        self.logbox = tk.Text(log_card, height=7, bg="#07090D", fg="#C9D1DD", insertbackground=TEXT,
                              relief="flat", bd=0, highlightthickness=1, highlightbackground="#1F2936",
                              font=("Menlo", 8), padx=12, pady=10)
        self.logbox.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.logbox.insert("end", "License required. Choose a plan and activate your license to unlock streaming.\n")

        # FOOTER
        footer = tk.Frame(self, bg="#0C1118", highlightthickness=1, highlightbackground="#18202C", height=56)
        footer.pack(fill="x", padx=28, pady=(0, 18))
        footer.pack_propagate(False)
        self.stat_chip(footer, "LIVE TIME", self.duration)
        self.stat_chip(footer, "BITRATE", self.bitrate)
        self.stat_chip(footer, "FPS", self.fps)
        self.stat_chip(footer, "DROPPED", self.dropped)
        self.label(footer, "VERTICAL LIVE ENGINE  ·  V11.1", fg=FAINT, size=8, bg="#0C1118").pack(side="right", padx=20)

    def _resize_preview_stage(self, _event=None):
        if not hasattr(self, "preview_stage"):
            return
        w = max(220, self.preview_stage.winfo_width())
        h = max(320, self.preview_stage.winfo_height())
        # Fit a 9:16 phone with comfortable breathing room; never crop the stage.
        pw = min(int(w * 0.68), int(h * 0.56))
        ph = int(pw * 16 / 9)
        if ph > int(h * 0.92):
            ph = int(h * 0.92)
            pw = int(ph * 9 / 16)
        pw = max(170, pw); ph = max(300, ph)
        outer_w, outer_h = pw + 24, ph + 24
        x = w // 2; y = h // 2
        self.phone_shadow.place(x=x+7, y=y+8, anchor="center", width=outer_w, height=outer_h)
        self.phone_outer.place(x=x, y=y, anchor="center", width=outer_w, height=outer_h)
        self.phone_inner.place(relx=.5, rely=.5, anchor="center", width=pw, height=ph)
        self.screen.config(width=max(120, pw-24), height=max(220, ph-24))
        self.notch.place(relx=.5, rely=.012, anchor="n", width=max(58, int(pw*.24)), height=8)

    def select_quality(self, q):
        self.quality.set(q)
        for name, b in self.quality_buttons.items():
            active = name == q
            b.config(bg=RED if active else SURFACE_2,
                      activebackground=RED_DARK if active else SURFACE_3,
                      fg=TEXT if active else MUTED)
        self.save_settings()

    def stat_chip(self, parent, title, var):
        f = tk.Frame(parent, bg="#0D1118")
        f.pack(side="left", padx=17)
        self.label(f, title, fg=FAINT, size=7, bold=True, bg="#0D1118").pack(side="left")
        self.label(f, textvariable=var, fg=TEXT, size=9, bold=True, bg="#0D1118").pack(side="left", padx=(7, 0))

    def toggle_button(self, parent, title, var):
        b = self.button(parent, "", lambda: self.refresh_toggle(b, var), bg=SURFACE_2, padx=12, pady=8, size=8)
        b._toggle_title = title
        b._toggle_var = var
        self.refresh_toggle(b, var, flip=False)
        return b

    def refresh_toggle(self, b, var, flip=True):
        if flip:
            var.set(not var.get())
        b.config(text=("✓  " if var.get() else "○  ") + b._toggle_title,
                 fg=GREEN if var.get() else MUTED,
                 )
        self.save_settings()

    def make_combo(self, p, label, var, values, row):
        self.label(p, label, fg=MUTED, size=8, bold=True, bg=SURFACE).grid(row=row, column=0, sticky="w", pady=6)
        holder = tk.Frame(p, bg="#0C1118", highlightbackground="#263243", highlightthickness=1)
        holder.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(16, 0), pady=5)
        holder.columnconfigure(0, weight=1)
        b = self.button(holder, var.get(), lambda: self.open_platform_menu(b, var, values),
                        bg="#0C1118", fg=TEXT, active="#131B27", padx=12, pady=7, size=9, bold=False)
        b.pack(fill="both", expand=True)
        b._var = var
        b._values = values
        b._label_text = label
        setattr(self, f"combo_{row}", b)

    def open_platform_menu(self, button, var, values):
        menu = tk.Menu(self, tearoff=0, bg="#121823", fg=TEXT, activebackground=RED,
                       activeforeground="#FFFFFF", bd=0, relief="flat", font=("Segoe UI", 9))
        for value in values:
            menu.add_command(label=value, command=lambda v=value: self._choose_platform(button, var, v))
        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _choose_platform(self, button, var, value):
        var.set(value)
        button.config(text=value)
        self.platform_changed()

    def make_entry(self, p, label, var, row, secret=False):
        self.label(p, label, fg=MUTED, size=8, bold=True, bg=SURFACE).grid(row=row, column=0, sticky="w", pady=6)
        holder = tk.Frame(p, bg="#0C1118", highlightbackground="#263243", highlightthickness=1)
        holder.grid(row=row, column=1, columnspan=2 if not secret else 1, sticky="ew", padx=(16, 0), pady=5)
        holder.columnconfigure(0, weight=1)
        e = tk.Entry(holder, textvariable=var, show="•" if secret else "", bg="#0C1118", fg=TEXT,
                     insertbackground=TEXT, relief="flat", highlightthickness=0,
                     font=("Segoe UI", 9), bd=0)
        e.pack(fill="both", expand=True, padx=11, ipady=7)
        if secret:
            show = self.button(p, "SHOW", lambda ent=e: self.toggle_secret(ent), bg="#151C27", fg=MUTED,
                               active="#202A39", padx=14, pady=7, size=7)
            show.grid(row=row, column=2, padx=(8, 0), pady=5, sticky="ew")

    def toggle_secret(self, e):
        e.config(show="" if e.cget("show") else "•")

    # ---------- app logic ----------
    def save_settings(self):
        self.cfg["video"] = self.video.get()
        self.cfg["quality"] = self.quality.get()
        self.cfg["loop"] = self.loop.get()
        self.cfg["reconnect"] = self.reconnect.get()
        self.cfg["short_boost"] = self.short_boost.get()
        save_cfg(self.cfg)

    def write(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass
        self.q.put(line)

    def flush_log(self):
        try:
            while True:
                self.logbox.insert("end", self.q.get_nowait())
                self.logbox.see("end")
        except queue.Empty:
            pass
        self.after(100, self.flush_log)

    def platform_changed(self):
        if self.platform.get() == "YouTube":
            self.rtmp.set("rtmp://a.rtmp.youtube.com/live2")

    def browse(self):
        f = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mov *.mkv *.webm *.avi *.m4v"), ("All files", "*.*")])
        if f:
            self.video.set(f)
            self.video_name.set(os.path.basename(f))
            self.write("✓ Video selected: " + f)
            self.save_settings()
            self.start_preview()

    def validate(self):
        if not self.video.get():
            return "Select a video file."
        if not os.path.isfile(self.video.get()):
            return "Selected video file does not exist."
        if not self.rtmp.get().strip():
            return "RTMP URL is empty."
        if not self.key.get().strip():
            return "Stream Key is empty."
        return None

    # ---------- preview ----------
    def start_preview(self):
        if not PIL_OK:
            self.preview_label.config(text="Preview needs Pillow\n(rebuild the app)", image="")
            return
        self.stop_preview()
        path = self.video.get().strip()
        if not path or not os.path.isfile(path):
            self.preview_label.config(text="SELECT A VERTICAL VIDEO", image="")
            return
        self.preview_stop = False
        threading.Thread(target=self.preview_worker, args=(path,), daemon=True).start()

    def stop_preview(self):
        self.preview_stop = True
        p = self.preview_proc
        self.preview_proc = None
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass

    def preview_worker(self, path):
        try:
            ff = get_ffmpeg()
            # Produce a small MJPEG stream. Parsing JPEG boundaries manually is much more
            # reliable than repeatedly calling PIL.Image.open() directly on a pipe.
            vf = "scale=300:533:force_original_aspect_ratio=decrease,pad=300:533:(ow-iw)/2:(oh-ih)/2,fps=10"
            cmd = [ff, "-hide_banner", "-loglevel", "error", "-stream_loop", "-1", "-i", path,
                   "-an", "-vf", vf, "-q:v", "6", "-f", "mjpeg", "pipe:1"]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
            self.preview_proc = p
            data = bytearray()
            while not self.preview_stop:
                chunk = p.stdout.read(8192)
                if not chunk:
                    break
                data.extend(chunk)
                while True:
                    start = data.find(b"\xff\xd8")
                    if start < 0:
                        if len(data) > 2_000_000:
                            data.clear()
                        break
                    end = data.find(b"\xff\xd9", start + 2)
                    if end < 0:
                        if start > 0:
                            del data[:start]
                        break
                    jpg = bytes(data[start:end + 2])
                    del data[:end + 2]
                    try:
                        im = Image.open(io.BytesIO(jpg)).convert("RGB")
                        photo = ImageTk.PhotoImage(im)
                        self.after(0, self.update_preview, photo)
                    except Exception:
                        pass
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        except Exception as e:
            self.after(0, lambda: self.preview_label.config(text="Preview unavailable", image=""))
        finally:
            self.preview_proc = None

    def update_preview(self, photo):
        if self.preview_stop:
            return
        self.preview_photo = photo
        self.preview_label.config(image=photo, text="")

    # ---------- streaming ----------
    def start_clicked(self):
        if self.proc and self.proc.poll() is None:
            return
        if not self.license_valid:
            self.plans()
            messagebox.showwarning("License Required", "Please activate a valid license before starting a live stream.")
            return
        err = self.validate()
        if err:
            self.set_status("NOT READY", RED)
            self.write("✗ " + err)
            messagebox.showerror("Cannot start", err)
            return
        self.save_settings()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.set_status("CONNECTING", AMBER)
        self.live_badge.config(text="● CONNECTING", fg=AMBER)
        threading.Thread(target=self.start_worker, daemon=True).start()

    def start_worker(self):
        try:
            ff = get_ffmpeg(self.write)
            q = self.quality.get()
            size = "720:1280" if q == "720p" else "1080:1920"
            br = "4500k" if q == "720p" else "6500k"
            loop = ["-stream_loop", "-1"] if self.loop.get() else []
            out = self.rtmp.get().rstrip("/") + "/" + self.key.get().strip()
            # Optional audio mapping: video-only files still stream instead of failing.
            cmd = [ff, "-hide_banner", "-loglevel", "info", "-re"] + loop + ["-i", self.video.get(),
                   "-map", "0:v:0", "-map", "0:a:0?", "-vf", f"scale={size}:force_original_aspect_ratio=decrease,pad={size}:(ow-iw)/2:(oh-ih)/2",
                   "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-b:v", br, "-maxrate", br,
                   "-bufsize", "9000k", "-pix_fmt", "yuv420p", "-g", "60", "-keyint_min", "60",
                   "-sc_threshold", "0", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-f", "flv", out]
            self.write("Starting vertical RTMP stream…")
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, bufsize=1)
            self.started = time.time()
            self.stop_flag = False
            threading.Thread(target=self.read_proc, daemon=True).start()
        except Exception as e:
            self.write("✗ START ERROR: " + str(e))
            self.after(0, self.failed_start)

    def read_proc(self):
        connected = False
        for raw in self.proc.stderr:
            line = raw.strip()
            if not line:
                continue
            self.write(line)
            low = line.lower()
            if "frame=" in low or "speed=" in low or "opening 'rtmp" in low or "streaming" in low:
                if not connected:
                    connected = True
                    self.after(0, lambda: self.set_live())
            m = re.search(r"bitrate=\s*([0-9.]+\s*\w*/s)", line, re.I)
            if m:
                self.after(0, lambda value=m.group(1): self.bitrate.set(value))
            m = re.search(r"fps=\s*([0-9.]+)", line, re.I)
            if m:
                self.after(0, lambda value=m.group(1): self.fps.set(value))
            m = re.search(r"drop(?:ped)?[=:]\s*(\d+)", line, re.I)
            if m:
                self.after(0, lambda value=m.group(1): self.dropped.set(value))
        rc = self.proc.poll()
        if not self.stop_flag:
            self.write(f"FFmpeg exited with code {rc}.")
            if self.reconnect.get():
                self.after(0, lambda: self.set_status("RECONNECTING", AMBER))
                time.sleep(5)
                if not self.stop_flag:
                    self.after(0, self.start_clicked)
            else:
                self.after(0, self.failed_start)

    def set_live(self):
        self.set_status("LIVE", GREEN)
        self.live_badge.config(text="● LIVE", fg=GREEN)

    def set_status(self, text, color):
        self.status.set(text)
        self.status_lbl.config(text="●  " + text, fg=color)

    def stop_clicked(self):
        self.stop_flag = True
        self.started = None
        if self.proc and self.proc.poll() is None:
            self.write("Stopping stream…")
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None
        self.set_status("READY", MUTED)
        self.live_badge.config(text="● READY", fg=MUTED)
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.duration.set("00:00:00")

    def tick(self):
        if self.started and self.proc and self.proc.poll() is None:
            self.duration.set(time.strftime("%H:%M:%S", time.gmtime(int(time.time() - self.started))))
        self.after(1000, self.tick)

    def test_setup(self):
        try:
            ff = get_ffmpeg(self.write)
            r = subprocess.run([ff, "-version"], capture_output=True, text=True, timeout=10)
            first = (r.stdout or r.stderr).splitlines()[0] if (r.stdout or r.stderr) else "FFmpeg OK"
            self.write("✓ " + first)
            messagebox.showinfo("Setup OK", "FFmpeg is ready and the streaming engine can use it.")
        except Exception as e:
            messagebox.showerror("Setup Error", str(e))

    def get_device_id(self):
        """Stable opaque device identifier. Never sends raw machine details."""
        raw = f"{platform.system()}|{platform.node()}|{uuid.getnode()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def enforce_license_gate(self):
        # Never trust the cached local license flag by itself. Re-check the server.
        if self.license_key.get().strip():
            if self.check_license(silent=True):
                return
        self.license_valid = False
        self.cfg["license_valid"] = False
        save_cfg(self.cfg)
        self.show_license_gate()

    def show_license_gate(self):
        if self.license_gate is not None and self.license_gate.winfo_exists():
            self.license_gate.lift()
            return

        w = tk.Toplevel(self)
        self.license_gate = w
        w.title("Activate Virtual Live Streamer")
        w.geometry("620x680")
        w.resizable(False, False)
        w.configure(bg=BG)
        w.transient(self)
        w.grab_set()
        w.protocol("WM_DELETE_WINDOW", self.on_close)

        self.label(w, "VIRTUAL LIVE STREAMER", fg=TEXT, size=19, bold=True, bg=BG).pack(pady=(28, 4))
        self.label(w, "Choose a plan to unlock the software", fg=MUTED, size=10, bg=BG).pack(pady=(0, 22))

        cards = tk.Frame(w, bg=BG)
        cards.pack(fill="x", padx=34)

        for title, price, duration, url in [
            ("WEEKLY", "₹299", "7 DAYS", WEEKLY_PAYMENT_URL),
            ("MONTHLY", "₹499", "30 DAYS", MONTHLY_PAYMENT_URL),
        ]:
            c = tk.Frame(cards, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
            c.pack(fill="x", pady=6)
            self.label(c, title, size=11, bold=True, bg=SURFACE).pack(side="left", padx=(18, 10), pady=18)
            self.label(c, price, fg=TEXT, size=15, bold=True, bg=SURFACE).pack(side="left", padx=5)
            self.label(c, duration, fg=MUTED, size=8, bold=True, bg=SURFACE).pack(side="left", padx=7)
            self.button(c, "BUY PLAN", lambda u=url: self.open_url(u), bg=RED, fg="#FFFFFF",
                        active=RED_DARK, padx=14, pady=8, size=8).pack(side="right", padx=14, pady=12)

        box = tk.Frame(w, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill="x", padx=34, pady=(20, 8))
        self.label(box, "ALREADY PAID? ACTIVATE YOUR LICENSE", size=10, bold=True, bg=SURFACE).pack(anchor="w", padx=18, pady=(16, 8))
        self.label(box, "Enter the License Key provided after activation", fg=MUTED, size=8, bg=SURFACE).pack(anchor="w", padx=18)
        entry = tk.Entry(box, textvariable=self.license_key, bg="#0C1118", fg=TEXT, insertbackground=TEXT,
                         relief="flat", highlightthickness=1, highlightbackground="#263243", font=("Segoe UI", 10))
        entry.pack(fill="x", padx=18, pady=(6, 10), ipady=9)
        self.label(box, "DEVICE ID", fg=FAINT, size=7, bold=True, bg=SURFACE).pack(anchor="w", padx=18)
        did = tk.Entry(box, bg="#0C1118", fg=MUTED, readonlybackground="#0C1118", relief="flat",
                       highlightthickness=1, highlightbackground="#263243", font=("Consolas", 8))
        did.insert(0, self.device_id); did.config(state="readonly")
        did.pack(fill="x", padx=18, pady=(5, 8), ipady=7)
        self.button(box, "UNLOCK SOFTWARE", lambda: self.check_license(w), bg=GREEN, fg=BLACK,
                    active="#20B873", padx=20, pady=10, size=9).pack(fill="x", padx=18, pady=(2, 16))

        self.label(w, "After payment, send your License Key + Device ID to support.\nActivation is manually approved before the software unlocks.",
                   fg=FAINT, size=8, bg=BG, justify="center").pack(pady=12)
        entry.focus_set()

    def license_status_text(self):
        if self.license_valid:
            exp = self.license_expires_at or "active"
            return f"LICENSE ACTIVE  ·  EXPIRES {exp[:10]}"
        return "LICENSE REQUIRED  ·  STREAMING LOCKED"

    def open_url(self, url):
        try:
            if platform.system() == "Windows":
                os.startfile(url)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", url])
            else:
                subprocess.Popen(["xdg-open", url])
        except Exception as e:
            messagebox.showerror("Open Link", str(e))

    def check_license(self, window=None, silent=False):
        key = self.license_key.get().strip()
        if not key:
            if not silent: messagebox.showwarning("License Key", "Enter your license key first.", parent=window)
            return False
        try:
            payload = json.dumps({"license_key": key, "device_id": self.device_id}).encode("utf-8")
            req = urllib.request.Request(
                SUPABASE_FUNCTION_URL,
                data=payload,
                headers={"Content-Type": "application/json", "apikey": SUPABASE_PUBLISHABLE_KEY},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as r:
                result = json.loads(r.read().decode("utf-8"))
            self.license_valid = bool(result.get("valid"))
            self.license_expires_at = result.get("expires_at", "") or ""
            if self.license_valid:
                self.cfg["license_key"] = key
                self.cfg["license_valid"] = True
                self.cfg["license_expires_at"] = self.license_expires_at
                self.cfg["plan"] = self.cfg.get("plan") if self.cfg.get("plan") not in (None, "Free", "Locked") else "Pro"
                save_cfg(self.cfg)
                self.set_status("LICENSE ACTIVE", GREEN)
                self.write("✓ License verified successfully")
                if window: window.destroy()
                if self.license_gate is not None and self.license_gate.winfo_exists():
                    self.license_gate.grab_release()
                    self.license_gate.destroy()
                    self.license_gate = None
                return True
            self.cfg["license_valid"] = False
            save_cfg(self.cfg)
            reason = result.get("reason", "invalid")
            self.write("✗ License check failed: " + reason)
            if not silent:
                messagebox.showerror("License Not Valid", self.pretty_license_reason(reason), parent=window)
            return False
        except Exception as e:
            if not silent:
                messagebox.showerror("License Check Failed", "Could not reach the license server. Check your internet connection and try again.", parent=window)
            self.write("✗ License server error")
            return False

    def pretty_license_reason(self, reason):
        return {
            "license_not_found": "License key was not found.",
            "not_active": "This license is not active yet.",
            "expired": "This license has expired.",
            "device_mismatch": "This license is already activated on another device.",
        }.get(reason, "The license could not be verified.")

    def plans(self):
        w = tk.Toplevel(self)
        w.title("Plans & License")
        w.geometry("590x560")
        w.resizable(False, False)
        w.configure(bg=BG)
        self.label(w, "Plans & License", size=20, bold=True, bg=BG).pack(pady=(20, 4))
        self.label(w, self.license_status_text(), fg=GREEN if self.license_valid else AMBER,
                   size=9, bold=True, bg=BG).pack(pady=(0, 14))

        for title, price, url in [("WEEKLY", "₹299  ·  7 DAYS", WEEKLY_PAYMENT_URL),
                                  ("MONTHLY", "₹499  ·  30 DAYS", MONTHLY_PAYMENT_URL)]:
            c = tk.Frame(w, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
            c.pack(fill="x", padx=28, pady=6)
            self.label(c, title, size=10, bold=True, bg=SURFACE).pack(side="left", padx=14, pady=(11, 0))
            self.label(c, price, fg=MUTED, size=9, bg=SURFACE).pack(side="left", padx=6, pady=(11, 0))
            self.button(c, "BUY", lambda u=url: self.open_url(u), bg=RED, fg="#FFFFFF", active=RED_DARK,
                        padx=14, pady=6, size=8).pack(side="right", padx=10, pady=8)

        box = tk.Frame(w, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill="x", padx=28, pady=(18, 8))
        self.label(box, "ACTIVATE LICENSE", size=10, bold=True, bg=SURFACE).pack(anchor="w", padx=16, pady=(14, 8))
        self.label(box, "License Key", fg=MUTED, size=8, bold=True, bg=SURFACE).pack(anchor="w", padx=16)
        entry = tk.Entry(box, textvariable=self.license_key, bg="#0C1118", fg=TEXT, insertbackground=TEXT,
                         relief="flat", highlightthickness=1, highlightbackground="#263243", font=("Segoe UI", 10))
        entry.pack(fill="x", padx=16, pady=(5, 9), ipady=8)
        self.label(box, "DEVICE ID  ·  send this ID to support after payment", fg=FAINT, size=7, bold=True, bg=SURFACE).pack(anchor="w", padx=16)
        did = tk.Entry(box, bg="#0C1118", fg=MUTED, readonlybackground="#0C1118", relief="flat",
                       highlightthickness=1, highlightbackground="#263243", font=("Consolas", 8))
        did.insert(0, self.device_id); did.config(state="readonly")
        did.pack(fill="x", padx=16, pady=(5, 12), ipady=7)
        self.button(box, "CHECK & ACTIVATE", lambda: self.check_license(w), bg=GREEN, fg=BLACK,
                    active="#20B873", padx=20, pady=9, size=9).pack(fill="x", padx=16, pady=(0, 16))
        self.label(w, "After payment, send your License Key + Device ID to support.\nActivation is manually approved from the license dashboard.",
                   fg=FAINT, size=8, bg=BG, justify="center").pack(pady=10)

    def demo(self, n, w):
        # Legacy compatibility; demo activation is intentionally disabled for production licensing.
        messagebox.showinfo("License", "Demo activation is disabled. Please purchase and activate a license.", parent=w)

    def on_close(self):
        self.stop_flag = True
        self.stop_preview()
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()